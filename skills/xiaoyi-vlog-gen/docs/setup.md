# 技能初始化（安装后必须执行一次）

技能安装后，必须初始化模板项目，后续一键成片才能正常工作。

## 检查是否已初始化

```bash
bash ~/.openclaw/workspace/skills/xiaoyi-vlog-gen/scripts/check-init.sh
```

退出码 0 → 已初始化，跳过。
退出码 1/2 → 执行下方步骤重新初始化。

## 步骤1：拷贝预制模板

拷贝预制模板骨架：

```bash
SKEL=~/.openclaw/workspace/skills/xiaoyi-vlog-gen/assets/template-skeleton
TARGET=~/.openclaw/workspace/generated-vlog/template

mkdir -p $TARGET
cp -r $SKEL/* $TARGET/
cp $SKEL/.npmrc $TARGET/
```

## 步骤2：配置 Chrome 路径

Remotion 需要无头浏览器渲染，必须在 `remotion.config.ts` 中指定 Chrome 路径。

**自动检测并写入：**

```bash
TEMPLATE=~/.openclaw/workspace/generated-vlog/template

# 优先级：环境变量 > 系统 PATH > Remotion 缓存
# 逐个尝试，验证可执行后才采用
find_chrome() {
  [ -n "$CHROME_PATH" ] && "$CHROME_PATH" --version &>/dev/null && return
  CHROME_PATH=""
  for cmd in chromium-browser google-chrome chromium /opt/google/chrome/google-chrome /opt/chromium/chromium /opt/chrome-linux/chrome; do
    p=$(which $cmd 2>/dev/null) && [ -n "$p" ] && "$p" --version &>/dev/null && { CHROME_PATH="$p"; return; }
  done
  CACHED="$HOME/.cache/remotion/chrome-headless-shell/chrome-headless-shell-linux64/chrome-headless-shell"
  [ -x "$CACHED" ] && "$CACHED" --version &>/dev/null && { CHROME_PATH="$CACHED"; return; }
}
find_chrome

if [ -z "$CHROME_PATH" ]; then
  echo '❌ 未找到 Chrome/Chromium，请手动设置 CHROME_PATH 环境变量后重试'
  echo '   下载方式：'
  echo '   1. 从 https://googlechromelabs.github.io/chrome-for-testing/ 下载 chrome-headless-shell'
  echo '   2. 放到 ~/.cache/remotion/chrome-headless-shell/ 下'
  echo '   3. 设置 CHROME_PATH 后重新执行'
  exit 1
fi

echo "✅ 检测到 Chrome: $CHROME_PATH"

# 重写 remotion.config.ts（含 Chrome 路径）
cat > $TEMPLATE/remotion.config.ts << CONF
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setChromeMode("chrome-for-testing");
Config.setBrowserExecutable("$CHROME_PATH");
CONF
```

## 步骤3：安装依赖

```bash
cd ~/.openclaw/workspace/generated-vlog/template

# 安装所有依赖
npm install
```


## 步骤4：环境检查

初始化完成后，运行以下检查确认环境正常：

```bash
TEMPLATE=~/.openclaw/workspace/generated-vlog/template
cd $TEMPLATE

# 渲染单帧测试（验证 Chrome + 依赖 + 组件 + props 完整链路）
cat > /tmp/vlog-test.json << 'EOF'
{"title":"Test","subtitle":"Check","endText":"OK","scenes":[{"image":"test.jpg","animation":"zoom-in","transition":"fade"}],"sceneDurations":[120]}
EOF
npx remotion still src/index.ts MainComposition /tmp/vlog-preview.png \
  --frame=30 --scale=0.25 --props=/tmp/vlog-test.json && echo '✅ 环境正常' || echo '❌ 渲染失败'
```

渲染失败常见原因：Chrome 路径、图片路径、props 格式，查看 Remotion 错误日志排查。

## 步骤5：前置技能检查

本技能依赖以下技能，缺少则无法正常工作。请检测是否已安装，未安装则提示用户先安装。

- **图像理解** — 分析图片内容，为每张图匹配最佳动画和转场
- **音乐生成** — 根据视频风格生成 BGM 背景音乐

## 初始化完成后的目录结构

```
~/.openclaw/workspace/generated-vlog/
├── template/                           # 模板项目（共享 node_modules）
│   ├── package.json
│   ├── tsconfig.json
│   ├── .npmrc
│   ├── remotion.config.ts
│   ├── node_modules/                   # 只装一次
│   ├── public/                         # 当前项目的 images/audio（每次渲染前复制）
│   │   ├── images/
│   │   └── audio/
│   └── src/
│       ├── index.ts                    # 入口
│       ├── Root.tsx                    # Composition 定义
│       └── MainComposition.tsx         # 主组件
└── YYYYMMDD_HHMMSS/                   # 每次一键成片的输出目录
    ├── images/                         # 输入图片
    ├── audio/                          # BGM 背景音乐
    ├── script.json                     # 编排表 + BGM 信息
    └── out/                            # 最终渲染输出
```