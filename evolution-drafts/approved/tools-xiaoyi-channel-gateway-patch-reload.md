# 进化提案：xiaoyi-channel dist 补丁需 gateway 彻底重启才生效

- 状态：**已确认（approved，2026-09-25）**
- 修改文件：TOOLS.md

## 背景
2026-09-25 空行反复，根因非执行懈怠单一因素：❄ 归一补丁 08:54 已落盘 reply-dispatcher.js，但 gateway 进程 pid 一直为 01:16 启动的 1624，SIGUSR1 优雅重载未重新 require 已缓存的 dist 模块，补丁在文件里"躺"着未加载 → 端侧空行照旧。

## 经验规则
1. 改 xiaoyi-channel 等插件 dist 编译产物后，**必须 `supervisorctl restart openclaw-gateway` 彻底重启（换 pid）才生效**；`SIGUSR1`/优雅重载不重新 require 已缓存模块。
2. **补丁在文件 ≠ 运行时已加载**：patch_autoheal 只查文件层 marker（在就跳过、不触发重启），文件有归一但运行网关可能是旧代码。
3. **判定生效**：对比 gateway 进程启动时间与补丁 mtime（进程早于补丁=未加载）；彻底重启后 pid 变化即加载成功。
4. daemon 自动补回只解决"插件更新冲掉补丁"，不负责"热加载已落盘补丁"，两者分开看待。

## 关联
- 已归档 tools-patch-autoheal-writegate-restore.md（write-gate 纳入守护 + restore 型目标）
- write-gate 存在 python open().write() 可绕过盲区（已在前提案记录为待办）
