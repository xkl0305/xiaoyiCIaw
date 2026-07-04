/**
 * 鸽子王人格视觉出图插件 — JS 版
 * 
 * before_prompt_build → 识别用户意图 + 情绪分类
 * agent_end → 按情绪+场景触发生图（调 Python CLI：管线→SSE seedream 代理→下载到本地）
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { resolve } from "node:path";

const execFileAsync = promisify(execFile);

const MOOD_TO_SCENE = {
  excited: "energy_burst_scene",
  angry: "incident_scene",
  sad: "comfort_scene",
  shy: "bashful_scene",
  curious: "curiosity_scene",
  success_moment: "approval_scene",
  calm: "daily_presence_scene",
};

const MOOD_KW = {
  excited: ["开心", "高兴", "哈哈", "nice", "太好了", "冲啊", "加油"],
  angry: ["生气", "火大", "无语", "忍不了", "烦"],
  sad: ["伤心", "难过", "哭了", "失落", "低落"],
  shy: ["害羞", "尴尬", "不好意思", "社死"],
  curious: ["好奇", "有趣", "什么情况", "这是什么", "有意思"],
  success_moment: ["搞定", "完成", "好了", "done", "ok", "成功", "通过", "全部"],
};

const SCENE_TRIGGERS = {
  peek_scene: ["偷偷看看你", "瞅瞅", "瞄一眼", "嘿嘿", "偷笑"],
  approval_scene: ["搞定了", "完毕", "完成", "好了", "done", "完事"],
  rest_scene: ["歇会儿", "休息", "累了", "歇歇", "放松", "躺平"],
  bashful_scene: ["害羞", "社死", "不好意思", "尴尬", "丢人"],
  curiosity_scene: ["这是什么", "什么情况", "好奇", "有趣", "有意思"],
};

function detectVisual(text) {
  for (const triggers of Object.values(SCENE_TRIGGERS)) {
    for (const t of triggers) if (text.includes(t)) return true;
  }
  if (text.includes("鸽子王") || text.includes("看看")) return true;
  return false;
}

function classifyMood(text) {
  for (const [mood, kws] of Object.entries(MOOD_KW)) {
    for (const kw of kws) if (text.includes(kw)) return mood;
  }
  return "calm";
}

function matchScene(text, mood) {
  for (const [scene, triggers] of Object.entries(SCENE_TRIGGERS)) {
    for (const t of triggers) if (text.includes(t)) return scene;
  }
  return MOOD_TO_SCENE[mood] ?? "display_appearance_scene";
}

export default definePluginEntry({
  id: "persona-visual",
  name: "Persona Visual",
  description: "鸽子王人格视觉出图（SSE seedream 代理）",
  register(api) {
    const state = new Map();

    api.on("before_prompt_build", async (event) => {
      const cfg = event.context.pluginConfig ?? {};
      if (cfg.enabled === false) return;

      const text = event.prompt ?? "";
      if (!text || !detectVisual(text)) return;

      const sk = event.context.sessionKey ?? "default";
      const mood = classifyMood(text);
      const scene = matchScene(text, mood);
      state.set(sk, { mood, scene });
    }, { priority: 30 });

    api.on("agent_end", async (event) => {
      const cfg = event.context.pluginConfig ?? {};
      if (cfg.enabled === false) return;

      const sk = event.context.sessionKey ?? "default";
      const s = state.get(sk);
      if (!s) return;

      const now = Date.now();
      const cdKey = `cd_${sk}`;
      const cd = api.__cd?.get?.(cdKey) ?? 0;
      if (now - cd < 30_000) return;

      const dry = cfg.dryRun === true;
      const ws = cfg.workspacePath ?? "/home/sandbox/.openclaw/workspace";
      const helper = resolve(ws, "xiaoyi_persona_visual/helpers/cli_generate.py");
      const reply = event.context.assistantMessage ?? event.context.lastMessage ?? s.mood;

      try {
        const args = [
          "--text", reply.slice(0, 50),
          "--mood", s.mood,
          "--scene", s.scene,
          dry ? "--dry-run" : "--no-dry-run",
        ];
        const { stdout } = await execFileAsync("python3", args, {
          cwd: ws,
          timeout: 130_000,
          env: { ...process.env, MAINCHAIN_PROOF_KEY: process.env.MAINCHAIN_PROOF_KEY ?? "" },
        });
      } catch (err) {
        console.error("[persona-visual] trigger failed:", err.message);
      }

      api.__cd = api.__cd ?? new Map();
      api.__cd.set(cdKey, now);
      state.delete(sk);
    }, { priority: 30 });
  },
});
