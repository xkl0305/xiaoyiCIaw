#!/usr/bin/env bash
# prepare-project.sh - vlog 技能第4步：项目准备
# 用法：prepare-project.sh <output_dir> <template_dir>
# 示例：prepare-project.sh ~/.openclaw/workspace/generated-vlog/20260506_090200 ~/.openclaw/workspace/generated-vlog/template
#
# 前置条件（由 agent 在调用脚本前完成）：
#   - 创建输出目录及 images/audio/out 子目录
#   - 复制用户图片到 <output_dir>/images/
#   - 复制 BGM 到 <output_dir>/audio/（如有）
#   - 写入 script.json 到 <output_dir>/script.json
#
# 脚本功能：
#   1. 检查模板项目是否已初始化（未初始化则提示并退出）
#   2. 检查核心脚本文件与骨架一致性，不一致则同步
#   3. 清空模板 public/ 旧素材，从输出目录复制当前素材
#   4. 检测图片横竖比例，自动写入 script.json 的 resolution 字段

set -euo pipefail

# ─── 参数解析 ───
if [ $# -lt 2 ]; then
  echo "用法: prepare-project.sh <output_dir> <template_dir>"
  echo ""
  echo "参数："
  echo "  output_dir    已创建的输出目录（含 images/audio/out + script.json）"
  echo "  template_dir  模板项目目录"
  exit 1
fi

OUTPUT_DIR="$1"
TEMPLATE_DIR="$2"

# ─── 验证 ───
if [ ! -d "$OUTPUT_DIR" ]; then
  echo "❌ 输出目录不存在: $OUTPUT_DIR"
  exit 1
fi

if [ ! -f "$OUTPUT_DIR/script.json" ]; then
  echo "❌ script.json 不存在: $OUTPUT_DIR/script.json"
  exit 1
fi

if [ ! -d "$OUTPUT_DIR/images" ]; then
  echo "❌ images 目录不存在: $OUTPUT_DIR/images"
  exit 1
fi

# ─── 步骤1：检查模板项目是否已初始化 ───
echo "🔍 检查模板项目初始化状态..."
CHECK_SCRIPT="$HOME/.openclaw/workspace/skills/xiaoyi-vlog-gen/scripts/check-init.sh"
if [ -f "$CHECK_SCRIPT" ]; then
  bash "$CHECK_SCRIPT"
  CHECK_EXIT=$?
else
  # 兼容：脚本不存在时回退到简单检查
  if [ ! -f "$TEMPLATE_DIR/node_modules/remotion/package.json" ]; then
    echo "❌ 模板项目未初始化！"
    exit 1
  fi
  CHECK_EXIT=0
fi

if [ "$CHECK_EXIT" -ne 0 ]; then
  echo "❌ 请先执行 docs/setup.md 完成初始化"
  exit 1
fi

# ─── 步骤2：检查核心脚本文件一致性 ───
SKEL_DIR="$HOME/.openclaw/workspace/skills/xiaoyi-vlog-gen/assets/template-skeleton"
CORE_FILES=(
  "src/MainComposition.tsx"
  "src/Root.tsx"
  "package.json"
)

echo "🔍 检查核心脚本文件一致性..."
MISMATCH=()
for f in "${CORE_FILES[@]}"; do
  skel_file="$SKEL_DIR/$f"
  tmpl_file="$TEMPLATE_DIR/$f"
  # 骨架中不存在的文件跳过
  [ ! -f "$skel_file" ] && continue
  # 模板中缺失则视为不一致
  if [ ! -f "$tmpl_file" ]; then
    MISMATCH+=("$f [缺失]")
    continue
  fi
  # 内容不一致
  if ! diff -q "$skel_file" "$tmpl_file" &>/dev/null; then
    MISMATCH+=("$f [内容不同]")
  fi
done

NEED_NPM_INSTALL=false

if [ ${#MISMATCH[@]} -gt 0 ]; then
  echo "⚠️  检测到核心文件不一致，将从骨架重新拷贝："
  for m in "${MISMATCH[@]}"; do
    echo "  - $m"
  done
  for f in "${CORE_FILES[@]}"; do
    skel_file="$SKEL_DIR/$f"
    [ ! -f "$skel_file" ] && continue
    cp "$skel_file" "$TEMPLATE_DIR/$f"
    echo "  ✅ 已更新: $f"
    # package.json 变更需要重新安装依赖
    [ "$f" = "package.json" ] && NEED_NPM_INSTALL=true
  done
  echo "✅ 核心文件已同步"
else
  echo "✅ 核心脚本文件一致"
fi

if [ "$NEED_NPM_INSTALL" = true ]; then
  echo "📦 package.json 已更新，重新安装依赖..."
  cd "$TEMPLATE_DIR"
  npm install
  echo "✅ 依赖安装完成"
fi

# ─── 步骤3：检测分辨率───
# 如果 script.json 中没有 resolution 字段，根据所有图片的横竖比例多数投票判断
if ! grep -q '"resolution"' "$OUTPUT_DIR/script.json" 2>/dev/null; then
  LANDSCAPE=0
  PORTRAIT=0
  for img in "$OUTPUT_DIR/images/"*.{jpg,jpeg,png,webp,gif,bmp}; do
    [ ! -f "$img" ] && continue
    dims=$(file "$img" | grep -oP '\d{3,}x\d{3,}' | head -1)
    if [ -n "$dims" ]; then
      w=$(echo "$dims" | cut -dx -f1)
      h=$(echo "$dims" | cut -dx -f2)
      [ "$w" -ge "$h" ] && LANDSCAPE=$((LANDSCAPE+1)) || PORTRAIT=$((PORTRAIT+1))
    else
      LANDSCAPE=$((LANDSCAPE+1))  # 无法检测时默认算横图
    fi
  done

  RESOLUTION=$([ "$LANDSCAPE" -ge "$PORTRAIT" ] && echo "landscape" || echo "portrait")

  cd "$OUTPUT_DIR"
  node -e "
    const fs = require('fs');
    const data = JSON.parse(fs.readFileSync('script.json', 'utf8'));
    data.resolution = '$RESOLUTION';
    fs.writeFileSync('script.json', JSON.stringify(data, null, 2));
  "
  echo "📐 检测分辨率: $RESOLUTION (横图${LANDSCAPE}张 / 竖图${PORTRAIT}张)"
else
  echo "📐 resolution 已设置，跳过检测"
fi

# ─── 步骤4：清空模板 public/ 旧素材，复制当前素材 ───
echo "🧹 清空模板旧素材..."
rm -rf "$TEMPLATE_DIR/public/images/"* "$TEMPLATE_DIR/public/audio/"*

echo "📦 复制素材到模板 public/..."
for ext in jpg jpeg png webp gif bmp; do
  cp "$OUTPUT_DIR/images/"*.$ext "$TEMPLATE_DIR/public/images/" 2>/dev/null || true
done
# 也处理大写后缀
for ext in JPG JPEG PNG WEBP GIF BMP; do
  cp "$OUTPUT_DIR/images/"*.$ext "$TEMPLATE_DIR/public/images/" 2>/dev/null || true
done
cp "$OUTPUT_DIR/audio/"* "$TEMPLATE_DIR/public/audio/" 2>/dev/null || true
# 复制含 resolution 字段的 script.json 到模板
cp "$OUTPUT_DIR/script.json" "$TEMPLATE_DIR/public/script.json"

# ─── 完成 ───
echo ""
echo "═══════════════════════════════════════"
echo "✅ 项目准备完成！"
echo ""
echo "  输出目录: $OUTPUT_DIR"
echo "  模板目录: $TEMPLATE_DIR"
echo "═══════════════════════════════════════"