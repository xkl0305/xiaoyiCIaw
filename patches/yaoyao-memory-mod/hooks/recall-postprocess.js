import { scoreConfidenceSupport } from "../utils/confidence-scorer.js";
import { INTENT_WEIGHTS } from "../core/search/intent.js";
import { applyTimeDecay, applyScoring, applyDiversitySampling, applyMmrDiversity, filterByScope, accumulateKeywords, runRecallFilter, checkRepeatQuery, recordRecentQuery, } from "./recall-utils.js";
import { buildRecallContext, buildHookResult, makeSimpleTrace } from "./recall-formatter.js";
export async function doPostProcess(results, mode, userText, cfg, scopeManager, agentId, intent, resultCache, stats, startMs, audit, sessionKey, logger, db, recentQueries) {
    let processed = filterByScope(results, scopeManager, agentId);
    processed = applyTimeDecay(processed, cfg.halfLife, cfg.decayMode, cfg.fadeMemAccessFactor);
    processed = applyScoring(processed, userText, cfg.enableFourSignal, cfg.fourSignalWeights);
    processed.sort((a, b) => b.score - a.score);
    if (cfg.enableIntentDriven && intent) {
        const weights = INTENT_WEIGHTS[intent];
        for (const r of processed) {
            const vecScore = typeof r.vectorScore === "number"
                ? r.vectorScore
                : r.score;
            const ts = r.timestamp;
            const tempScore = ts ? Math.pow(0.5, (Date.now() - ts) / (30 * 24 * 60 * 60 * 1000)) : 0.5;
            r.score = weights.fts * r.score + weights.vector * vecScore + weights.temporal * tempScore;
        }
        processed.sort((a, b) => b.score - a.score);
    }
    if (cfg.enableMmr) {
        processed = applyMmrDiversity(processed, cfg.mmrLambda, cfg.maxResults);
    }
    else {
        processed = applyDiversitySampling(processed, cfg.jaccardBase, cfg.jaccardMin);
    }
    const limited = processed.slice(0, cfg.maxResults);
    // v1.8.1 (MemX): Low-confidence rejection. If the best score is below rejectThreshold,
    // reject ALL results rather than injecting potentially misleading memories.
    // Paper: MemX (arXiv:2603.16171) — strict quality gate on top result.
    if (cfg.rejectThreshold > 0 && limited.length > 0) {
        const topScore = limited[0].score;
        if (topScore < cfg.rejectThreshold) {
            logger.debug?.(`[yaoyao-memory:recall] MemX rejection: top score ${topScore.toFixed(3)} < rejectThreshold ${cfg.rejectThreshold}`);
            stats.recordQuery(makeSimpleTrace(userText, mode, startMs, results.length, 0));
            return;
        }
    }
    const memoryTexts = limited.map(r => (r.snippet || r.asst_text || "")).join("\n");
    const confidence = scoreConfidenceSupport(memoryTexts, userText);
    if (confidence.score < cfg.scoreThreshold) {
        logger.debug?.(`[yaoyao-memory:recall] Confidence ${confidence.score.toFixed(2)} < threshold ${cfg.scoreThreshold}`);
        return;
    }
    // ── Conflict detection (GalaxyOS memory_consolidation derived) ──
    // Detect contradictory memories via negation token overlap.
    // If memory A says "X is true" and memory B says "X is not true",
    // one of them is likely stale or incorrect. Flag and downgrade.
    const NEGATIONS = new Set(["不","不是","没有","不对","没","错误","no","not","never","false"]);
    function _tokenize(t) {
        const words = t.replace(/[，。！？、；：""''（）【】《》.,!?;:"'()\[\]{}<>]/g, " ").split(/\s+/);
        return words.filter(w => w.length > 1);
    }
    for (const mem of limited) {
        const content = (mem.snippet || mem.asst_text || "").toLowerCase();
        const memTokens = _tokenize(content);
        if (memTokens.length < 2) continue;
        const memSet = new Set(memTokens);
        let conflictScore = 0;
        for (const other of limited) {
            if (other === mem) continue;
            const otherText = (other.snippet || other.asst_text || "").toLowerCase();
            const otherSet = new Set(_tokenize(otherText));
            const common = [...memSet].filter(w => otherSet.has(w));
            if (common.length < 2) continue;
            if (mem.content && other.content && mem.content === other.content) continue;
            const hasNegMem = [...memSet].some(w => NEGATIONS.has(w));
            const hasNegOther = [...otherSet].some(w => NEGATIONS.has(w));
            if (hasNegMem !== hasNegOther) {
                conflictScore += 0.3 * Math.min(common.length, 3) / 3;
            }
        }
        if (conflictScore > 0.3) {
            const penalty = Math.min(conflictScore * 0.2, 0.3);
            mem.score = Math.max(0.01, mem.score - penalty);
            mem.needs_verification = true;
            logger.debug?.(`[yaoyao-memory:conflict] Conflict (${conflictScore.toFixed(2)}) in "${content.slice(0, 60)}" → score ${mem.score.toFixed(3)}`);
        }
    }
    const filtered = await runRecallFilter(limited, userText, cfg);
    // Caller owns the recent-queries array so repeat detection persists across
    // hook invocations. Creating a fresh array here (the old behavior) made the
    // repeat-query check dead code.
    const recentQueriesRef = recentQueries ?? [];
    const repeatNote = checkRepeatQuery(userText, cfg.maxResults, cfg.scoreThreshold, recentQueriesRef);
    if (repeatNote) {
        logger.debug?.(`[yaoyao-memory:recall] ${repeatNote}`);
    }
    recordRecentQuery(userText, cfg.maxResults, cfg.scoreThreshold, filtered.length, recentQueriesRef);
    accumulateKeywords(sessionKey, userText, cfg.maxContextKeywords);
    if (filtered.length > 0) {
        resultCache.set(`${agentId || "default"}:${userText.slice(0, 120)}`, filtered);
    }
    stats.recordQuery(makeSimpleTrace(userText, mode, startMs, results.length, filtered.length));
    // v1.8.1 (FadeMem): Increment access_count for recalled memories.
    // This feeds back into applyTimeDecay on future recalls — frequently
    // recalled memories get slower decay (longer effective half-life).
    if (db && filtered.length > 0) {
        for (const r of filtered) {
            if (r.id != null) {
                try {
                    db
                        .incrementAccessCount?.(r.id);
                }
                catch { /* best effort */ }
            }
        }
    }
    if (audit && filtered.length > 0) {
        audit.record("recall", {
            query: userText, agentId, mode, results: filtered.length,
            durationMs: Date.now() - startMs, ...(repeatNote ? { repeatNote } : {}),
        });
    }
    if (filtered.length > 0) {
        return buildHookResult(buildRecallContext(filtered, cfg.maxContextChars), cfg.position);
    }
}
