# Evolution Proposal: sherpa-onnx TTS 安装经验 + 镜像加速

- Created-At: 2026-08-16 12:25
- Target-File: TOOLS.md
- Trigger-Type: struggle

## Why This Matters
- 本地 TTS 安装是通用、可复用的工程场景；sherpa-onnx 中文模型缺 phontab 是高频踩坑，避免未来重复下载多个模型空耗
- GitHub/HuggingFace 直连慢或失败是沙箱环境的常态，镜像加速法通用有效

## Evidence
- 下载了 4 个中文模型（zh-baker / vits-zh-aishell3 / xiao_ya / vits-zh-hf）、翻遍 GitHub release/代码/HuggingFace 官方源，均缺 phontab
- GitHub 直连下载慢/失败，用 ghfast.top 镜像稳定拉完整文件
- HuggingFace 直连不通，用 hf-mirror.com 镜像成功列出/访问文件
- 英文 piper lessac 模型自带 espeak-ng-data，开箱即用；中文 pinyin 模型需 phontab 而公开渠道拿不到

## Conflict Points
- None

## Plan
1. 在 TOOLS.md 末尾追加「本地 TTS (sherpa-onnx) 经验」与「GitHub/HuggingFace 镜像加速」两条规则
2. 追加文本见下，直接 append 到 TOOLS.md 末尾

### 追加内容
```
### 本地 TTS (sherpa-onnx) 安装经验（2026-08-16）
- runtime/模型下载后解压到 `~/.openclaw/tools/sherpa-onnx-tts/{runtime,models}`，env 配到 `~/.openclaw/.env`（SHERPA_ONNX_RUNTIME_DIR / SHERPA_ONNX_MODEL_DIR）
- **英文 piper 模型（如 en_US-lessac-high）自带 espeak-ng-data → 开箱即用**，wrapper 直接可跑
- **中文 pinyin 模型（xiao_ya/aishell3/zh-hf 等）统一缺 `phontab` 文件**（中文拼音音素表），且公开渠道（GitHub release/代码搜索/HuggingFace 官方源）均无法获取 → 别在这上面反复下载模型空耗
- 实测命令：`{runtime}/bin/...` 或技能 wrapper `sherpa-onnx-tts -o out.wav "文本"`（wrapper 对多 onnx 模型需 `--model-file/--tokens-file/--data-dir`）

### GitHub / HuggingFace 镜像加速（2026-08-16）
- GitHub 直连慢/失败时，加前缀代理：`https://ghfast.top/<原github.com URL>`（实测可完整拉大文件）
- HuggingFace 直连不通/卡死时，换国内镜像：`https://hf-mirror.com/<原huggingface.co URL>`（含 API：`https://hf-mirror.com/api/...`）
- 备选 GitHub 镜像：gh-proxy.com（亦可用）
```
