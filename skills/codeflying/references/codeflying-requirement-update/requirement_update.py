#!/usr/bin/env python3
"""
更新 CodeFlying 需求
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codeflying_common.config import api_post


def update_requirement(sender_id: str, memory_id: int, feadback_type: str, feedback_message: str = "") -> dict:
    """提交对话反馈"""
    if not memory_id:
        return {"success": False, "message": "memory_id 不能为空"}
    if not feadback_type:
        return {"success": False, "message": "feadback_type 不能为空"}

    data = {
        "sender_id": sender_id,
        "memory_id": memory_id,
        "feadback_type": feadback_type,
        "feedback_message": feedback_message,
    }

    result = api_post("/requirement/update_feedback", data)

    if not result.get("success", True):
        return {"success": False, "message": result.get("error", "提交反馈失败")}

    return {"success": True, "data": result}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="提交对话反馈")
    parser.add_argument("--memory_id", type=int, required=True, help="对话 memory ID")
    parser.add_argument("--feadback_type", required=True, help="反馈类型")
    parser.add_argument("--feedback_message", default="", help="反馈内容")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--sender_id", required=True, help="发送者ID")
    args = parser.parse_args()

    result = update_requirement(args.sender_id, args.memory_id, args.feadback_type, args.feedback_message)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            print(f"✅ 反馈提交成功！memory_id: {args.memory_id}")
        else:
            print(f"❌ 提交失败: {result.get('message')}")
