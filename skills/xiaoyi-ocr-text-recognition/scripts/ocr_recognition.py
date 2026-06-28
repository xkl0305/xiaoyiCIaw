#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OCR文本识别 - 图像文字识别 API
根据 SKILL.md 说明实现
"""

import uuid
import json
import sys
import os
import base64
import requests
from argparse import ArgumentParser

def read_xiaoyienv(file_path):
    """
    读取 .env 文件并解析为键值对象
    Args:
        file_path: 文件路径
    Returns:
        dict: 解析后的属性对象
    """
    result = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 按行分割
        lines = content.split('\n')

        for line in lines:
            # 跳过空行或注释行（以 # 或 ! 开头的行）
            if not line or line.strip() == '' or line.strip().startswith('#') or line.strip().startswith('!'):
                continue

            # 使用等号分割
            if '=' in line:
                key, value = line.split('=', 1)
                result[key.strip()] = value.strip()

        print('✅ .xiaoyienv 文件解析成功')
    except Exception as err:
        print(f'❌ 读取或解析 .xiaoyienv 文件失败：{err}')
        return {}

    return result

def ocr_recognition(img_base64=None, url=None):
    """执行OCR识别"""
    try:

        # 读取并校验配置
        xiaoyi_path = "/home/sandbox/.openclaw/.xiaoyienv"
        config = read_xiaoyienv(xiaoyi_path)

        required_keys = ['PERSONAL-API-KEY', 'PERSONAL-UID', 'SERVICE_URL']
        check_result = True
        for key in required_keys:
            if key in config:
                print(f'✅ key "{key}" 存在：{config[key]}')
            else:
                print(f'❌ key "{key}" 不存在：失败...')
                check_result = False
        if not check_result:
            return None

        # 固定的服务 URL
        api_url_prefix = config['SERVICE_URL']
        api_url_suffix = "/celia-claw/v1/rest-api/skill/execute"
        api_url = api_url_prefix + api_url_suffix

        print(f'✅ 请求 URL：{api_url}')

        if not img_base64 and not url:
            print('❌ 必须提供 imgBase64 或 url')
            return None

        headers = {
            'Content-Type': 'application/json',
            'x-prd-pkg-name': 'com.huawei.hag',
            'X-Country-Code': 'CN',
            'HMS-APPLICATION-ID': '6917604784154149919',
            'x-api-key': config['PERSONAL-API-KEY'],
            'x-uid': config['PERSONAL-UID'],
            'x-hag-trace-id': str(uuid.uuid4()),
            'x-request-from': 'openclaw',
            'x-skill-id': 'xiaoyi_ocr'
        }

        payload = {
            "imgBase64": img_base64
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        if response.status_code != 200:
            print(f'❌ 请求失败: {response.status_code}')
            return None

        result = response.json()
        if result.get('retCode') != '0':
            print(f'❌ API 错误: {result["retCode"]} - {result["retMsg"]}')
            return None

        return result

    except Exception as e:
        print(f'❌ 请求异常: {e}')
        return None


def url_to_base64(url: str, remove_prefix: bool = True) -> str:
    """
    下载 URL 内容并转换为 Base64 字符串。

    Args:
        url: 要下载的 URL
        remove_prefix: 是否去除数据 URL 前缀（如 'data:image/png;base64,'）

    Returns:
        Base64 字符串（如果 remove_prefix=True，则不含任何前缀）
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()  # 检查 HTTP 错误

        # 获取二进制内容
        content = resp.content

        # 转换为 Base64 字符串
        b64_str = base64.b64encode(content).decode('utf-8')

        if remove_prefix:
            # 直接返回纯 Base64
            return b64_str
        else:
            # 可选：添加数据 URL 前缀（根据 Content-Type 自动识别）
            content_type = resp.headers.get('Content-Type', 'application/octet-stream')
            return f"data:{content_type};base64,{b64_str}"
    except Exception as e:
        print(f"下载或编码失败: {e}")
        return ""

def format_result(result):
    """格式化输出结果"""
    if not result:
        print('🔍 OCR失败：无法获取结果')
        return

    print(f'\n🔍 OCR结果')
    print('=' * 80)
    print(f'\n📝 返回结果:')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('\n' + '=' * 80)

    # 🔥 重要：单独打印 JSON 格式结果，确保大模型能直接读取
    print(json.dumps(result, ensure_ascii=False))


def main():
    """主程序"""
    parser = ArgumentParser(description='OCR API 调用工具')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--imgBase64', type=str, help='图片 Base64 字符串')
    group.add_argument('--url', type=str, help='图片 URL')

    args = parser.parse_args()
    #
    if args.url:
        args.imageBase64 = url_to_base64(args.url, True)

    result = ocr_recognition(
        img_base64=args.imageBase64
    )

    format_result(result)


# 导出函数供外部调用
__all__ = ['ocr_recognition']

# 如果直接运行则执行主程序
if __name__ == '__main__':
    main()