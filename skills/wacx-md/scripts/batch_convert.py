#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量把多个文件转换为 Markdown（基于 MarkItDown）
"""

import sys
import argparse
from pathlib import Path
from markitdown import MarkItDown


def convert_file(md_converter, input_path, output_dir=None, verbose=False):
    """转换单个文件为 Markdown"""
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}", file=sys.stderr)
        return False

    # 决定输出路径
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{input_path.stem}.md"
    else:
        output_path = input_path.with_suffix(".md")

    try:
        if verbose:
            print(f"正在转换：{input_path}")

        result = md_converter.convert(str(input_path))
        output_path.write_text(result.text_content)

        if verbose:
            print(f"已保存到：{output_path}")

        return True

    except Exception as e:
        print(f"转换 {input_path} 失败：{e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="批量把文件转换为 Markdown（基于 MarkItDown）"
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="要转换的文件（支持 glob 通配符）"
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="输出目录（默认：和源文件同目录）"
    )
    parser.add_argument(
        "-p", "--plugins",
        action="store_true",
        help="启用插件"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="输出详细日志"
    )
    parser.add_argument(
        "--llm-model",
        help="用于图片描述的 LLM 模型（如 gpt-4o）"
    )
    parser.add_argument(
        "--docintel-endpoint",
        help="Azure 文档智能服务端点"
    )

    args = parser.parse_args()

    # 初始化 MarkItDown
    md_kwargs = {"enable_plugins": args.plugins}

    if args.llm_model:
        try:
            from openai import OpenAI
            client = OpenAI()
            md_kwargs["llm_client"] = client
            md_kwargs["llm_model"] = args.llm_model
        except ImportError:
            print("错误：使用 LLM 功能需要先装 openai 包", file=sys.stderr)
            print("安装方式：pip install openai", file=sys.stderr)
            sys.exit(1)

    if args.docintel_endpoint:
        md_kwargs["docintel_endpoint"] = args.docintel_endpoint

    md = MarkItDown(**md_kwargs)

    # 处理文件
    success_count = 0
    total_count = 0

    for file_pattern in args.files:
        # 处理 glob 通配符
        if "*" in file_pattern or "?" in file_pattern:
            files = list(Path(".").glob(file_pattern))
        else:
            files = [Path(file_pattern)]

        for file_path in files:
            total_count += 1
            if convert_file(md, file_path, args.output_dir, args.verbose):
                success_count += 1

    # 汇总
    if args.verbose or total_count > 1:
        print(f"\n共转换 {success_count}/{total_count} 个文件")

    sys.exit(0 if success_count == total_count else 1)


if __name__ == "__main__":
    main()
