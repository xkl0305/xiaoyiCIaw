#!/usr/bin/env python3
"""
获取 CodeFlying 需求列表
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeflying_common.config import api_get


def get_requirement_list(sender_id: str, app_id: int = None) -> dict:
    """获取需求列表"""
    params = {"sender_id": sender_id, "page": 1, "size": 10}
    if app_id:
        params["app_id"] = app_id
    
    result = api_get("/requirement/get", params)
    
    if not result.get("success", True):
        return {"success": False, "message": result.get("error", "获取需求列表失败")}
    
    return {"success": True, "data": result}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="获取需求列表")
    parser.add_argument("--app-id", type=int, help="按应用 ID 筛选")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--sender_id", required=True, help="发送者ID")
    args = parser.parse_args()
    
    result = get_requirement_list(args.sender_id, args.app_id)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            data = result["data"]
            requirements = data.get("data", [])
            print(f"📋 需求列表 (共 {len(requirements)} 个)\n")
            for req in requirements:
                print(f"[{req.get('requirement_id')}] {req.get('original_requirement', '无标题')[:50]}")
                print(f"    应用ID: {req.get('app_id')} | 状态: {req.get('status')}")
                print()
        else:
            print(f"❌ 错误: {result.get('message')}")
