/**
 * hooks/capture-meta.ts — Metadata building + dedup for capture pipeline.
 *
 * Extracted from capture-pipeline.ts to keep it under 200 lines.
 * This module handles the heavy imports: temporal, verify, identity,
 * upgrader, L1 extraction, chunker, memory-types.
 *
 * v1.8.0: Added source (channel/device), deviceInteractions, skillSource metadata.
 */
import { classifyTemporal, inferExpiry } from "../utils/temporal-classifier.js";
import { detectSpeculative, detectCorrection } from "../core/verify/verify.js";
import { extractIdentityCandidates } from "../utils/identity-addressing.js";
import { enrichMetadata } from "../core/upgrader/index.js";
import { extractFacts } from "../utils/l1-extractor.js";
import { classifyMemoryType } from "../core/memory-types.js";
import { computeValueFactors, computeMemoryValue } from "../core/value/memory-value.js";
import { isDuplicateOfRecent } from "../utils/batch-dedup.js";
// ── 简单交叉验证模式（轻量版 hallucination_guard）──
// 检测 AI 回复中的常见幻觉模式：
// 1. 自我声称（"我记得"、"之前说过"）但实际可能不存在
// 2. 引用不存在的外部源
// 3. 肯定句中的模糊范围词
const HALLUCINATION_PATTERNS = [
    // 自我声称无证据
    { re: /我记得\s*(?:你|我|他|她|它)/i, tag: "自称记忆不可查" },
    { re: /之前说过\s*(?:你|我|他|她|它)/i, tag: "自称记忆不可查" },
    { re: /据我所知\s*[,，]?\s*[^，。]{0,10}(?:是|有|在)/i, tag: "模糊声称" },
    // 无来源断言
    { re: /(?:研究|论文|报告)\s*(?:表明|指出|显示|证明)/i, tag: "无来源断言" },
    { re: /(?:专家|学者|业内)\s*(?:认为|指出|表示|分析)/i, tag: "无来源断言" },
    // 具体数字/日期无上下文
    { re: /(?:增长|下降|提升)\s*\d+(?:\.\d+)?%\s*(?:左右|以上|以下)?(?!\s*(?:数据|统计|根据|基于|来源))/, tag: "无数据源数字" },
];

export function runAntiHallucination(userContent, asstContent, verifyActive) {
    let riskTag = "";
    let specCheck = { isSpeculative: false, markers: [], confidence: "high" };
    let corrCheck = { isCorrection: false, markers: [] };
    if (verifyActive) {
        try {
            specCheck = detectSpeculative(asstContent);
            corrCheck = detectCorrection(userContent);
        }
        catch { /* best-effort */ }
        // 增强：交叉验证模式检测
        const halMarkers = [];
        for (const pattern of HALLUCINATION_PATTERNS) {
            if (pattern.re.test(asstContent)) {
                halMarkers.push(pattern.tag);
            }
        }
        if (halMarkers.length > 0) {
            specCheck.markers.push(...halMarkers);
            if (!specCheck.isSpeculative) specCheck.isSpeculative = true;
            specCheck.confidence = halMarkers.length >= 2 ? "high" : "medium";
        }
    }
    if (specCheck.isSpeculative)
        riskTag = ` [⚠️ 推测性: ${specCheck.markers.join(", ")}]`;
    if (corrCheck.isCorrection)
        riskTag += ` [🚫 用户纠正]`;
    return { riskTag, specCheck, corrCheck };
}
export async function buildMetaObj(userContent, asstContent, scopeManager, agentId, specCheck, corrCheck, enableL1, skipL1, brainMode, llmClient, logger, maxMemories, config, extras) {
    // v1.8.0: If device interactions include time-sensitive tools, force dynamic temporal
    const hasTimeSensitive = extras?.deviceInteractions?.some(i => ["create_calendar_event", "search_calendar_event", "create_alarm", "modify_alarm", "delete_alarm"].includes(i.tool)) ?? false;
    const combinedText = userContent + " " + asstContent;
    let temporalType = classifyTemporal(combinedText);
    if (hasTimeSensitive && temporalType !== "dynamic") {
        temporalType = "dynamic";
    }
    const expiryAt = temporalType === "dynamic"
        ? (hasTimeSensitive ? _shortExpiry() : inferExpiry(combinedText))
        : undefined;
    const memoryTag = classifyMemoryType(userContent, asstContent);
    // v1.8.2: Seven-factor memory value function (replaces single importance)
    // Paper: "Learning What to Remember" (arXiv:2606.12945) — V(m) = Σ wᵢfᵢ(m)
    const valueFactors = computeValueFactors(userContent, asstContent, {
        speculative: specCheck.isSpeculative,
        correction: corrCheck.isCorrection,
        memoryType: memoryTag.type,
    });
    const memoryValue = computeMemoryValue(valueFactors);
    const metaObj = {
        temporal: temporalType,
        memoryType: memoryTag.type,
        importance: memoryValue,
        valueFactors,
    };
    if (scopeManager)
        metaObj.scope = scopeManager.getDefaultScope(agentId);
    const identities = extractIdentityCandidates(combinedText);
    if (identities.length > 0)
        metaObj.identities = identities;
    if (expiryAt)
        metaObj.expiryAt = expiryAt;
    if (specCheck.isSpeculative) {
        metaObj.speculative = true;
        metaObj.confidence = specCheck.confidence;
    }
    if (corrCheck.isCorrection) {
        metaObj.correction = true;
    }
    if (memoryTag.tags.length > 0) {
        metaObj.tags = memoryTag.tags;
    }
    // v1.8.0: Channel/device source metadata
    if (extras?.channelInfo) {
        const ci = extras.channelInfo;
        const sourceObj = {};
        if (ci.channel !== "unknown")
            sourceObj.channel = ci.channel;
        if (ci.deviceType !== "unknown")
            sourceObj.deviceType = ci.deviceType;
        if (Object.keys(sourceObj).length > 0)
            metaObj.source = sourceObj;
    }
    // v1.8.0: Device interactions (tool calls)
    if (extras?.deviceInteractions && extras.deviceInteractions.length > 0) {
        metaObj.deviceInteractions = extras.deviceInteractions.slice(0, 10);
    }
    // v1.8.0: Skill source
    if (extras?.skillSource) {
        metaObj.skillSource = extras.skillSource;
    }
    if (enableL1 && !skipL1) {
        try {
            const facts = await extractFacts(userContent, asstContent, { brainMode, llmClient, logger });
            if (facts.length > 0)
                metaObj.l1Facts = facts.slice(0, maxMemories);
        }
        catch { /* best effort */ }
    }
    enrichMetadata(metaObj, combinedText);
    const meta = Object.keys(metaObj).length > 1 ? JSON.stringify(metaObj) : undefined;
    return { metaObj, meta, memoryTag };
}
/** Shortened expiry for time-sensitive device interactions (2 hours) */
function _shortExpiry() {
    const dt = new Date(Date.now() + 2 * 60 * 60 * 1000);
    return dt.toISOString();
}
export function checkDedup(db, texts, config) {
    if (!config.enableDedup)
        return false;
    try {
        const recent = db.getLatestMemory(config.dedupLookback);
        return isDuplicateOfRecent(texts, recent, config.dedupThreshold);
    }
    catch {
        return false;
    }
}
