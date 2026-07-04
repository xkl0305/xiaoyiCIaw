/**
 * 鸽子王人格视觉出图插件
 * 
 * Hook 接线：
 *   before_prompt_build → 识别用户意图 + 情绪分类
 *   agent_end → 按情绪+场景触发生图
 * 
 * 通过 child_process 调 Python helper 完成生图
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { resolve } from "node:path";

const execFileAsync = promisify(execFile);

// 七情→场景映射
const MOOD_TO_SCENE: Record<string, string> = {
  excited: "energy_burst_scene",
  angry: "incident_scene",
  sad: "comfort_scene",
  shy: "bashful_scene",
  curious: "curiosity_scene",
  success_moment: "approval_scene",
  calm: "daily_presence_scene",
};

// 情绪检测关键词
const MOOD_KEYWORDS: Record<string, string[]> = {
  excited: ["开心", "高兴", "哈哈", "笑", "nice", "太好了", "冲啊", "冲冲冲", "加油"],
  angry: ["生气", "火大", "无语", "忍不了", "烦", "🔥", "😡"],
  sad: ["伤心", "难过", "哭了", "失落", "低落", "😭", "💔"],
  shy: ["害羞", "尴尬", "不好意思", "社死", "丢人", "😳"],
  curious: ["好奇", "有趣", "什么情况", "这是什么", "有意思"],
  success_moment: ["搞定", "完成", "好了", "done", "ok", "成功", "通过", "全部"],
};

// 场景触发词（来自 PERSONA_VISUALIZATION_RULES.md）
const SCENE_TRIGGERS: Record<string, string[]> = {
  peek_scene: ["偷偷看看你", "瞅瞅", "瞄一眼", "看看你", "嘿嘿", "偷笑"],
  approval_scene: ["搞定了", "完毕", "完成", "好了", "done", "完事"],
  rest_scene: ["歇会儿", "休息", "累了", "歇歇", "放松", "躺平"],
  bashful_scene: ["害羞", "社死", "不好意思", "尴尬", "丢人"],
  curiosity_scene: ["这是什么", "什么情况", "好奇", "有趣", "有意思"],
};

export default definePluginEntry({
  id: "persona-visual",
  name: "Persona Visual",
  description: "鸽子王人格视觉出图",
  register(api) {
    // 运行时状态
    const requestState = new Map<string, { mood: string; scene: string }>();

    // ---------- pre-reply: before_prompt_build ----------
    api.on(
      "before_prompt_build",
      async (event) => {
        const cfg = event.context.pluginConfig as Record<string, unknown> ?? {};
        if (cfg.enabled === false) return;

        const userMessage = event.prompt ?? "";
        if (!userMessage) return;

        const sessionKey = event.context.sessionKey ?? "default";

        // 1) 判断是否是视觉请求
        const isVisualRequest = detectVisualRequest(userMessage);
        if (!isVisualRequest) return;

        // 2) 情绪分类
        const mood = classifyMood(userMessage);

        // 3) 场景匹配
        const scene = matchScene(userMessage, mood);

        // 存入状态
        requestState.set(sessionKey, { mood, scene });
      },
      { priority: 30 },
    );

    // ---------- post-reply: agent_end ----------
    api.on(
      "agent_end",
      async (event) => {
        const cfg = event.context.pluginConfig as Record<string, unknown> ?? {};
        if (cfg.enabled === false) return;

        const sessionKey = event.context.sessionKey ?? "default";
        const state = requestState.get(sessionKey);
        if (!state) return;

        // 冷却：同一 session 30 秒内不重复触发
        const now = Date.now();
        const cooldownKey = `cooldown_${sessionKey}`;
        const lastTrigger = (api as any).__cooldowns?.get?.(cooldownKey) ?? 0;
        if (now - lastTrigger < 30_000) return;

        const dryRun = cfg.dryRun === true;

        // 调用 Python helper 触发生图
        const workspacePath = (cfg.workspacePath as string) ?? "/home/sandbox/.openclaw/workspace";
        const helperScript = resolve(workspacePath, "xiaoyi_persona_visual/helpers/cli_generate.py");

        const replyText = event.context.assistantMessage ?? event.context.lastMessage ?? state.mood;
        const requestId = `pv_${sessionKey}_${now}`;

        try {
          const { stdout, stderr } = await execFileAsync("python3", [
            helperScript,
            "--text", replyText,
            "--mood", state.mood,
            "--scene", state.scene,
            dryRun ? "--dry-run" : "--no-dry-run",
            "--request-id", requestId,
          ]);

          // 更新冷却
          (api as any).__cooldowns = (api as any).__cooldowns ?? new Map();
          (api as any).__cooldowns.set(cooldownKey, now);
        } catch (err) {
          console.error(`[persona-visual] agent_end trigger failed:`, err);
        }

        // 清理状态
        requestState.delete(sessionKey);
      },
      { priority: 30 },
    );
  },
});

// ---------- helper functions ----------

function detectVisualRequest(text: string): boolean {
  // 显式触发词
  for (const [, triggers] of Object.entries(SCENE_TRIGGERS)) {
    for (const t of triggers) {
      if (text.includes(t)) return true;
    }
  }
  // 鸽子王关键词
  if (text.includes("鸽子王") || text.includes("看看")) return true;
  return false;
}

function classifyMood(text: string): string {
  for (const [mood, keywords] of Object.entries(MOOD_KEYWORDS)) {
    for (const kw of keywords) {
      if (text.includes(kw)) return mood;
    }
  }
  return "calm";
}

function matchScene(text: string, mood: string): string {
  // 优先按触发词匹配场景
  for (const [scene, triggers] of Object.entries(SCENE_TRIGGERS)) {
    for (const t of triggers) {
      if (text.includes(t)) return scene;
    }
  }
  // 降级到情绪映射
  return MOOD_TO_SCENE[mood] ?? "display_appearance_scene";
}
