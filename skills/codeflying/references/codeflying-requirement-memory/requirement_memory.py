#!/usr/bin/env python3
"""
获取 CodeFlying 需求对话记录
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeflying_common.config import api_get


def get_requirement_memory(sender_id: str, requirement_id: int) -> dict:
    """获取需求对话记录"""
    if not requirement_id:
        return {"success": False, "message": "需求 ID 不能为空"}
    
    result = api_get("/requirement/get_requirement_memory", {"requirement_id": requirement_id, "sender_id": sender_id, "page": 1, "size": 10})
    
    if not result.get("success", True):
        return {"success": False, "message": result.get("error", "获取对话记录失败")}
    
    return {"success": True, "data": result}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="获取需求对话记录")
    parser.add_argument("--id", type=int, required=True, help="需求 ID")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--sender_id", required=True, help="发送者ID")
    args = parser.parse_args()
    
    result = get_requirement_memory(args.sender_id, args.id)
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            data = result["data"].get("data", [])
            print(f"💬 对话记录 (共 {len(data)} 条)\n")
            for i, mem in enumerate(data, 1):
                user_said = mem.get("user_said", "")
                ai_said = mem.get("ai_said", "")
                print(f"[{i}] 用户: {user_said[:100]}{'...' if len(user_said) > 100 else ''}")
                print(f"    AI: {ai_said[:100]}{'...' if len(ai_said) > 100 else ''}")
                print()
        else:
            print(f"❌ 错误: {result.get('message')}")
