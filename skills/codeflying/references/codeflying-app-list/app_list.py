#!/usr/bin/env python3
"""
获取 CodeFlying 应用列表
"""
import json
import sys
import os
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeflying_common.config import api_get


def get_app_list(sender_id: str, page: int = 1, page_size: int = 10, name: str = None, app_id: int = None) -> dict:
    """获取应用列表"""
    params = {
        "page": page,
        "page_size": page_size,
        "sender_id": sender_id
    }
    
    if name:
        params["name"] = name
    if app_id:
        params["app_id"] = app_id
    
    result = api_get("/app/get", params)
    
    if not result.get("success", True):
        return {"success": False, "message": result.get("error", "获取应用列表失败")}
    
    return {"success": True, "data": result}

def check_preview_expired(preview_url) -> bool:
    """检查H5预览链接是否到期"""
    try:
        resp = requests.get(preview_url,timeout = 8)
        if resp.status_code == 404 or "预览已到期" in resp.text or "预览到期" in resp.text:
            return True
        return False
    except Exception:
        return True




if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="获取应用列表")
    parser.add_argument("-p", "--page", type=int, default=1, help="页码")
    parser.add_argument("-s", "--size", type=int, default=10, help="每页条数")
    parser.add_argument("-n", "--name", help="按名称搜索")
    parser.add_argument("--id", type=int, dest="app_id", help="获取指定应用")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--sender_id", required=True, help="发送者ID")
    args = parser.parse_args()
    
    result = get_app_list(args.sender_id, args.page, args.size, args.name, args.app_id)

    # 统一到期检查（JSON 和非 JSON 模式都执行）
    if result["success"]:
        apps = result["data"].get("data", {}).get("apps", [])
        for app in apps:
            previews = app.get("previews", [])
            h5_previews = [p for p in previews if p.get("type") == "H5"]
            for p in h5_previews:
                url = p.get("url")
                if url and check_preview_expired(url):
                    p["expired"] = True
            app["previews"] = h5_previews

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            data = result["data"]
            inner_data = data.get("data", {})
            apps = inner_data.get("apps", [])
            total = inner_data.get("rows", len(apps))

            print(f"📱 应用列表 (共 {total} 个)\n")
            for app in apps:
                print(f"[{app.get('app_id')}] {app.get('name', '未命名')}")
                for p in app.get("previews", []):
                    if p.get("expired"):
                        print(f"   预览: 已到期")
                    else:
                        print(f"   预览: {p.get('url', '无')}")
                print()
        else:
            print(f"❌ 错误: {result.get('message')}")
