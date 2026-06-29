"""
Crusheart Agent OS — RuntimeProbe v4.0
运行时探针：环境检测 + 关键指标 + 能力扫描
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
import logging
import os
import sys
import json

logger = logging.getLogger(__name__)

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")


class RuntimeProbe:
    """
    运行时探针
    
    检测当前运行环境的关键信息，供决策引擎参考。
    """

    @staticmethod
    def detect_environment() -> Dict[str, Any]:
        """检测运行时环境"""
        python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        no_ext = os.environ.get("NO_EXTERNAL_API", "true").lower() == "true"
        no_send = os.environ.get("NO_REAL_SEND", "true").lower() == "true"
        no_payment = os.environ.get("NO_REAL_PAYMENT", "true").lower() == "true"
        no_device = os.environ.get("NO_REAL_DEVICE", "true").lower() == "true"

        return {
            "python_version": python_ver,
            "runtime_mode": "sandbox" if no_ext else "production",
            "sandbox_flags": {
                "no_external_api": no_ext,
                "no_real_send": no_send,
                "no_real_payment": no_payment,
                "no_real_device": no_device,
            },
        }

    @staticmethod
    def detect_capabilities() -> List[str]:
        """扫描当前环境可用的能力"""
        available = []

        # 手机端工具
        try:
            from .serial_lanes import SerialLane
            available.append("device_ops")
        except (ImportError, ModuleNotFoundError):
            pass

        # 备忘录
        try:
            from device_toolkit import create_note
            available.append("note")
        except (ImportError, ModuleNotFoundError):
            pass

        # 日程
        try:
            from device_toolkit import create_event
            available.append("calendar")
        except (ImportError, ModuleNotFoundError):
            pass

        # 闹钟
        try:
            from device_toolkit import create_alarm
            available.append("alarm")
        except (ImportError, ModuleNotFoundError):
            pass

        # 文件系统
        try:
            from device_toolkit import manage_file
            available.append("file")
        except (ImportError, ModuleNotFoundError):
            pass

        # 联网搜索
        try:
            from device_toolkit import web_search
            available.append("web_search")
        except (ImportError, ModuleNotFoundError):
            pass

        return available

    @staticmethod
    def probe_device_connection(assume_session_connected: bool = False) -> Dict[str, Any]:
        """检测设备连接状态"""
        return {
            "session_connected": assume_session_connected,
            "can_direct_invoke": False,
            "can_queue_or_fallback": True,
            "adapter_status": "active" if assume_session_connected else "probe",
        }

    @staticmethod
    def full_probe() -> Dict[str, Any]:
        """完整探针报告"""
        env = RuntimeProbe.detect_environment()
        caps = RuntimeProbe.detect_capabilities()
        device = RuntimeProbe.probe_device_connection()

        return {
            "environment": env,
            "capabilities": caps,
            "device": device,
            "probed_at": datetime.now(BEIJING_TZ).isoformat(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return RuntimeProbe.full_probe()


# 验证
if __name__ == "__main__":

    # --test/--self-check: 基础自检（#48）
    if "--test" in sys.argv or "--self-check" in sys.argv:
        try:
            from core.engines.init.self_check import run_self_check
        except ImportError:
            print("❌ self_check 模块不可用")
            sys.exit(1)

        checks = [("import self", lambda: None)]
        sys.exit(run_self_check(__name__, __file__,
            custom_checks=checks, verbose=True))

    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("RuntimeProbe — 测试")
    print("=" * 60)
    probe = RuntimeProbe.full_probe()
    print(f"  mode: {probe['environment']['runtime_mode']}")
    print(f"  caps: {probe['capabilities']}")
    print(f"  device: {probe['device']}")
    print("  ✅ 通过")
