#!/usr/bin/env python3
"""
通用采访总结报告生成器 — 辅助脚本

功能：
1. 读取多个访谈逐字稿文件（支持 .docx、.txt、.md）
2. 使用 markitdown 解析 docx 文件
3. 提供内容输出供LLM分析师处理

使用方法：
python3 generate.py --input <访谈稿目录或文件> --output <输出文件>
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path


def read_file(filepath):
    """读取文件内容"""
    ext = Path(filepath).suffix.lower()
    
    if ext == '.docx':
        # 使用 markitdown 转换 docx 为文本
        try:
            result = subprocess.run(
                ['python3', '-m', 'markitdown', filepath],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"[WARN] markitdown 解析失败: {result.stderr}", file=sys.stderr)
                return None
        except FileNotFoundError:
            print("[WARN] markitdown 未安装，尝试备用方案", file=sys.stderr)
            return _read_docx_fallback(filepath)
        except subprocess.TimeoutExpired:
            print(f"[WARN] 解析超时: {filepath}", file=sys.stderr)
            return None
    elif ext in ['.txt', '.md']:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        print(f"[WARN] 不支持的文件格式: {ext}", file=sys.stderr)
        return None


def _read_docx_fallback(filepath):
    """备用方案：尝试使用 python-docx 读取 docx"""
    try:
        from docx import Document
        doc = Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return '\n'.join(paragraphs)
    except ImportError:
        print("[ERROR] 需要安装 python-docx 或 markitdown 来读取 docx 文件", file=sys.stderr)
        return None


def collect_interviews(input_path):
    """收集所有访谈稿内容"""
    path = Path(input_path)
    interviews = []
    
    if path.is_dir():
        for file in sorted(path.iterdir()):
            if file.suffix.lower() in ['.docx', '.txt', '.md']:
                content = read_file(str(file))
                if content:
                    interviews.append({
                        'filename': file.name,
                        'content': content.strip()
                    })
                    print(f"  ✓ {file.name}", file=sys.stderr)
    else:
        content = read_file(str(path))
        if content:
            interviews.append({
                'filename': path.name,
                'content': content.strip()
            })
            print(f"  ✓ {path.name}", file=sys.stderr)
    
    return interviews


def format_interviews_for_llm(interviews):
    """将访谈内容格式化为易于LLM分析的结构"""
    parts = []
    for i, iv in enumerate(interviews, 1):
        parts.append(f"=== 受访者{i} ===\n文件名：{iv['filename']}\n\n{iv['content']}")
    return '\n\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description='通用采访总结报告生成器')
    parser.add_argument('--input', '-i', required=True, help='访谈稿目录或文件路径')
    parser.add_argument('--output', '-o', default='', help='输出纯文本文件路径（可选）')
    parser.add_argument('--list', '-l', action='store_true', help='仅列出访谈稿信息，不输出内容')
    
    args = parser.parse_args()
    
    print("📖 读取访谈稿...", file=sys.stderr)
    interviews = collect_interviews(args.input)
    
    if not interviews:
        print("❌ 未读取到任何访谈内容", file=sys.stderr)
        sys.exit(1)
    
    print(f"\n✅ 共读取 {len(interviews)} 份访谈稿", file=sys.stderr)
    
    if args.list:
        print(f"\n文件列表：", file=sys.stderr)
        for iv in interviews:
            print(f"  {iv['filename']} ({len(iv['content'])} 字符)", file=sys.stderr)
        return
    
    # 输出格式化的访谈内容
    output = format_interviews_for_llm(interviews)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n✅ 已输出到: {args.output}", file=sys.stderr)
    else:
        # 直接输出到 stdout，供管道使用
        print(output)


if __name__ == '__main__':
    main()
