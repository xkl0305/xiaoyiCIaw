/**
 * core/search/intent.ts — Query intent classification.
 *
 * Analyzes a search query to determine what kind of information
 * the user is looking for, enabling intent-aware search strategies.
 *
 * Ported from Cortex Memory's QueryIntentType + weight_model concepts.
 */
// ── Intent classifiers ──
/** Time-related patterns (Chinese + English) */
const TEMPORAL_PATTERNS = [
    /昨天|前天|后天|上周|上个月|下个月|去年|明年|\d+月\d+日|\d+月|\d+号|星期[一二三四五六日天]|周[一二三四五六日天]|最近|近期|以前|之前|刚才|刚刚|早上|下午|晚上|昨晚/i,
    /today|yesterday|tomorrow|last\s+(week|month|year)|next\s+(week|month|year)|recent|lately|ago|earlier/i,
    /\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}/,
];
/** Named entity patterns */
const ENTITY_PATTERNS = [
    /^who|^什么人|^哪个|^谁|^谁.*(?:是|有|开发|负责|创建|写)|找.*(?:人|公司|组织)/i,
    /^what.*(?:is|are|叫|是|有)/i,
];
/** Comparative / relational patterns */
const RELATIONAL_PATTERNS = [
    /和.*(?:区别|对比|比较|关系|相同|不同|哪个好|谁好)/i,
    /difference|compare|vs|versus|relation(ship)?|similar|better.*than|vs\./i,
    /(?:A|B)和(?:B|A)/i,
];
/** Broad exploration patterns */
const EXPLORATORY_PATTERNS = [
    /^(?:关于|有关|有没有|帮我找|搜索|查一下|看看|有什么|哪些|列举|列出|总结|概述|汇总|回顾)/i,
    /^(?:about|find|search|list|show|tell|look\s+up|any|summarize|overview)/i,
];

// === Chinese-Query Enhancements (ported from GalaxyOS adaptive_rrf) ===

/** CJK character range */
function _isCJK(ch) {
    const code = ch.charCodeAt(0);
    return (code >= 0x4E00 && code <= 0x9FFF) ||
           (code >= 0x3040 && code <= 0x30FF) ||
           (code >= 0xAC00 && code <= 0xD7AF);
}

/** CJK ratio of a string */
function _cjkRatio(s) {
    let count = 0;
    for (const ch of s) {
        if (_isCJK(ch)) count++;
    }
    return count / Math.max(s.length, 1);
}

/** Check if query looks like a version number or exact reference */
function _isExactMatch(query) {
    // Version patterns: "3.11", "v8.6.0", "2.0.1"
    if (/^v?\d+(\.\d+)+$/.test(query)) return true;
    // Quote-wrapped: '"xxx"'
    if (/^["'].+["']$/.test(query)) return true;
    // Year: "2026", "2024"
    if (/^\d{4}$/.test(query)) return true;
    // Acronyms: "RRF", "MMR", "CJK"
    if (/^[A-Z]{2,}$/.test(query)) return true;
    // Short query with number (Chinese): "3.11", "v2"
    if (/\d/.test(query) && query.replace(/\s/g,'').length < 15) return true;
    return false;
}

/** Check if query is keyword-heavy (short, specific terms) */
function _isKeywordHeavy(query) {
    const stripped = query.replace(/\s/g, '');
    // Very short: less than 8 chars = keyword lookup
    if (stripped.length < 8 && stripped.length > 0) return true;
    // Short CJK: less than 10 chars = likely keyword
    if (stripped.length < 10 && _cjkRatio(query) > 0.3) return true;
    // Has special characters (punctuation, symbols) ≈ keyword-oriented
    if (/[\[\]{}()<>!@#$%^&*+=|\\:;"'~`]/.test(query)) return true;
    // CJK query with exact-match indicators
    if (_cjkRatio(query) > 0.3) {
        if (/具体|精确|准确|定位|指定|某个/.test(query)) return true;
    }
    return false;
}

// ── Intent weight profiles ──
/**
 * Dynamic weight profiles per intent type.
 * Entity lookups favour vector (semantic), temporal favours recency,
 * relational favours FTS (keyword overlap), exploratory stays balanced.
 * exact_match favours FTS heavily, keyword_heavy favours FTS moderately.
 */
export const INTENT_WEIGHTS = {
    entity_lookup: { fts: 0.25, vector: 0.65, temporal: 0.10 },
    factual: { fts: 0.35, vector: 0.50, temporal: 0.15 },
    temporal: { fts: 0.25, vector: 0.25, temporal: 0.50 },
    relational: { fts: 0.55, vector: 0.35, temporal: 0.10 },
    exploratory: { fts: 0.40, vector: 0.35, temporal: 0.25 },
    // GalaxyOS adaptive_rrf inspired:
    exact_match: { fts: 0.70, vector: 0.20, temporal: 0.10 },   // 精确数字/版本 → 靠FTS
    keyword_heavy: { fts: 0.60, vector: 0.25, temporal: 0.15 }, // 短关键词 → 靠FTS
    general: { fts: 0.33, vector: 0.34, temporal: 0.33 },
};
// ── Public API ──
/**
 * Classify a search query into an intent type.
 * Uses pattern matching (no LLM call needed for this).
 *
 * Priority order:
 *   1. exact_match (version/numbers) — most specific
 *   2. temporal (time-based queries)
 *   3. keyword_heavy (short/Chinese specific) — catches short queries not matched above
 *   4. relational (comparisons)
 *   5. entity_lookup (who/which/找人)
 *   6. exploratory (summarize/search/find)
 *   7. general (fallback)
 */
export function classifyIntent(query) {
    if (typeof query !== "string" || query.length === 0)
        return "general";

    // 1. Exact match check (highest priority — version numbers, acronyms, quoted)
    if (_isExactMatch(query)) {
        return "exact_match";
    }

    // 2. Relational (most specific semantic patterns)
    for (const p of RELATIONAL_PATTERNS) {
        if (p.test(query))
            return "relational";
    }
    // 3. Entity lookup
    for (const p of ENTITY_PATTERNS) {
        if (p.test(query))
            return "entity_lookup";
    }
    // 4. Temporal (time-based queries)
    for (const p of TEMPORAL_PATTERNS) {
        if (p.test(query))
            return "temporal";
    }
    // 5. Exploratory
    for (const p of EXPLORATORY_PATTERNS) {
        if (p.test(query))
            return "exploratory";
    }
    // 6. Keyword heavy — catches short/Chinese queries not matched by any pattern above
    if (_isKeywordHeavy(query)) {
        return "keyword_heavy";
    }
    return "general";
}
/**
 * Get the weight profile for a query intent.
 * Falls back to general weights for unknown intents.
 */
export function weightsForIntent(intent) {
    return INTENT_WEIGHTS[intent] ?? INTENT_WEIGHTS.general;
}
/**
 * Get weights by directly classifying a query string.
 * Convenience wrapper for classifyIntent + weightsForIntent.
 */
export function intentWeightsForQuery(query) {
    return weightsForIntent(classifyIntent(query));
}
