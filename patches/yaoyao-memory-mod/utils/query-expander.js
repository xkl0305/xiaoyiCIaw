/**
 * Query Expander — 轻量级中文查询扩展 + 拼写纠正
 * 从 GalaxyOS rewriter 学习：静态拼写纠正字典 + 标点标准化
 *
 * 解决中文口语化搜索词与技术术语不匹配的问题。
 * 例如：用户搜"挂了" → 扩展为"崩溃 crash error 报错 宕机 失败"
 *
 * 匹配策略：
 * - 中文触发：子串匹配（中文无单词边界）
 * - 英文触发：单词边界正则（避免 false positive）
 */

// ── 拼写纠正表（从 GalaxyOS rewriter 移植）──
const SPELLING_CORRECTIONS = {
    "配置": ["配制", "配值"],
    "推送规则": ["推送规责", "推送归则"],
    "用户偏好": ["用户偏号", "用户偏号设置"],
    "记忆系统": ["记忆体系", "记忆系通"],
    "向量搜索": ["向量搜所", "向量收索"],
    "LLM": ["llm", "Llm"],
    "Embedding": ["embedding", "embeding"],
    "API": ["api", "Api"],
};

/**
 * 拼写纠正预处理 — 在扩展前纠正常见拼写错误
 * 返回纠正后的查询字符串
 */
function correctSpelling(query) {
    let corrected = query;
    for (const [correct, wrongs] of Object.entries(SPELLING_CORRECTIONS)) {
        for (const wrong of wrongs) {
            if (corrected.includes(wrong)) {
                corrected = corrected.replaceAll(wrong, correct);
            }
        }
    }
    return corrected;
}

/**
 * 标点符号标准化
 */
function normalizePunctuation(query) {
    return query
        .replace(/，/g, ' ')
        .replace(/、/g, ' ')
        .replace(/；/g, ' ')
        .replace(/？/g, ' ')
        .replace(/！/g, ' ')
        .replace(/：/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}
/** 最多追加的扩展词数量 */
const MAX_EXPANSION_TERMS = 5;
const SYNONYM_MAP = [
    // --- Status / Failure ---
    {
        cn: ["挂了", "挂掉", "宕机"],
        en: ["shutdown", "crashed"],
        expansions: ["崩溃", "crash", "error", "报错", "宕机", "失败"],
    },
    {
        cn: ["卡住", "卡死", "没反应"],
        en: ["hung", "frozen"],
        expansions: ["hang", "timeout", "超时", "无响应", "stuck"],
    },
    {
        cn: ["炸了", "爆了"],
        en: ["oom"],
        expansions: ["崩溃", "crash", "OOM", "内存溢出", "error"],
    },
    // --- Config / Deploy ---
    {
        cn: ["配置", "设置"],
        en: ["config", "configuration"],
        expansions: ["配置", "config", "configuration", "settings", "设置"],
    },
    {
        cn: ["部署", "上线"],
        en: ["deploy", "deployment"],
        expansions: ["deploy", "部署", "上线", "发布", "release"],
    },
    {
        cn: ["容器"],
        en: ["docker", "container"],
        expansions: ["Docker", "容器", "container", "docker-compose"],
    },
    // --- Code / Debug ---
    {
        cn: ["报错", "出错", "错误"],
        en: ["error", "exception"],
        expansions: ["error", "报错", "exception", "错误", "失败", "bug"],
    },
    {
        cn: ["修复", "修了", "修好"],
        en: ["bugfix", "hotfix"],
        expansions: ["fix", "修复", "patch", "解决"],
    },
    {
        cn: ["踩坑"],
        en: ["troubleshoot"],
        expansions: ["踩坑", "bug", "问题", "教训", "排查", "troubleshoot"],
    },
    // --- Search / Memory ---
    {
        cn: ["记忆", "记忆系统"],
        en: ["memory"],
        expansions: ["记忆", "memory", "记忆系统", "索引"],
    },
    {
        cn: ["搜索", "查找", "找不到"],
        en: ["search", "retrieval"],
        expansions: ["搜索", "search", "retrieval", "检索", "查找"],
    },
    // --- Infrastructure ---
    {
        cn: ["推送"],
        en: ["git push"],
        expansions: ["push", "推送", "git push", "commit"],
    },
    {
        cn: ["日志"],
        en: ["logfile", "logging"],
        expansions: ["日志", "log", "logging", "输出", "打印"],
    },
    {
        cn: ["权限"],
        en: ["permission", "authorization"],
        expansions: ["权限", "permission", "access", "授权", "认证"],
    },
];
/** Build a word-boundary regex for an English trigger */
function buildWordBoundaryRegex(term) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`\\b${escaped}\\b`, "i");
}
/**
 * Expand a query by appending synonym terms from the dictionary.
 * Returns the original query with additional terms appended.
 * Idempotent — already-precise queries pass through unchanged.
 */
export function expandQuery(query) {
    if (!query || query.trim().length < 2)
        return query;

    // Step 0: 拼写纠正 + 标点标准化
    query = correctSpelling(query);
    query = normalizePunctuation(query);
    const lower = query.toLowerCase();
    const additions = new Set();
    for (const entry of SYNONYM_MAP) {
        // Check Chinese triggers via substring (Chinese has no word boundaries)
        const cnMatch = entry.cn.some((t) => lower.includes(t.toLowerCase()));
        // Check English triggers via word-boundary regex
        const enMatch = entry.en.some((t) => buildWordBoundaryRegex(t).test(query));
        if (cnMatch || enMatch) {
            for (const exp of entry.expansions) {
                if (!lower.includes(exp.toLowerCase())) {
                    additions.add(exp);
                }
                if (additions.size >= MAX_EXPANSION_TERMS)
                    break;
            }
        }
        if (additions.size >= MAX_EXPANSION_TERMS)
            break;
    }
    if (additions.size === 0)
        return query;
    return `${query} ${[...additions].join(" ")}`;
}
