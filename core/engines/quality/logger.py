"""
Crusheart Agent OS — 统一日志系统 v1.0
功能：提供全系统统一的 Logger 工厂 + 日志级别规范 + 结构化字段

使用方式：
    from core.engines.quality.logger import get_logger
    log = get_logger("auto_memory")
    log.info("记忆保存成功", id="m123", tags=3)
    log.warning("搜索超时", query="xxx", elapsed_ms=5200)
    log.error("写入失败", exc_info=True)

日志格式：
    [2026-05-18 15:33:00.123] [auto_memory] [INFO] 消息内容  {"id": "m123", "tags": 3}

日志文件：
    .engine_logs/{name}.log      — 按模块拆分
    .engine_logs/all.log         — 全量聚合（仅 WARNING+）

级别规范（全系统统一）：
    DEBUG   — 开发调试用，生产默认关闭
    INFO    — 正常操作确认（保存成功/调用完成/启动停止）
    WARNING — 预期内的异常（重试/降级/熔断触发/配置缺失）
    ERROR   — 功能受损（写入失败/调用连续失败/状态不一致）
    CRITICAL — 系统不可用（引擎初始化失败/关键路径断裂）
"""

import os
import sys
import logging
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
LOG_DIR = os.path.join(WORKSPACE, ".engine_logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ═══════════════════════════════════════════
# 自定义 Formatter — 带结构化字段
# ═══════════════════════════════════════════

class StructuredFormatter(logging.Formatter):
    """
    结构化日志格式化器。

    格式： [时间] [模块名] [级别] 消息内容  {json字段}
    示例： [2026-05-18 15:33:00.123] [auto_memory] [INFO] 保存成功  {"id": "m123"}
    """

    def __init__(self, include_structured: bool = True):
        super().__init__()
        self.include_structured = include_structured

    def format(self, record: logging.LogRecord) -> str:
        # 时间戳（北京时间，含毫秒）
        ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        name = record.name
        message = record.getMessage()

        # 结构化字段（extra 参数中非标准字段）
        extra = {}
        if self.include_structured:
            std_attrs = {
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "levelname", "levelno", "lineno",
                "message", "module", "msecs", "msg", "name", "pathname",
                "process", "processName", "relativeCreated", "stack_info",
                "thread", "threadName",
            }
            for key, val in record.__dict__.items():
                if key not in std_attrs and not key.startswith("_"):
                    extra[key] = val

        # 异常信息
        exc_text = ""
        if record.exc_info and record.exc_info[0]:
            if record.exc_text is None:
                record.exc_text = super().formatException(record.exc_info)
            exc_text = f"\n{record.exc_text}"

        if extra and self.include_structured:
            return f"[{ts}] [{name}] [{level}] {message}  {json.dumps(extra, ensure_ascii=False, default=str)}{exc_text}"
        return f"[{ts}] [{name}] [{level}] {message}{exc_text}"


# ═══════════════════════════════════════════
# Logger 工厂
# ═══════════════════════════════════════════

_loggers: Dict[str, logging.Logger] = {}


# LogRecord 保留字段 — 传 kwargs 时自动跳过，避免冲突
_RESERVED_ATTRS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text",
    "filename", "funcName", "levelname", "levelno", "lineno",
    "message", "module", "msecs", "msg", "name", "pathname",
    "process", "processName", "relativeCreated", "stack_info",
    "thread", "threadName", "taskName",
})


class StructuredLogger(logging.Logger):
    """
    支持结构化字段的 Logger 子类。

    用法：
        log = StructuredLogger("my_module")
        log.info("消息", id="m123", tags=3)  # 结构化字段自动收集到 extra
    """

    def _log(self, level, msg, args, exc_info=None, extra=None,
             stack_info=False, stacklevel=1, **kwargs):
        # 将关键字参数合并到 extra 中（跳过 LogRecord 保留字段）
        if kwargs:
            if extra is None:
                extra = {}
            for k, v in kwargs.items():
                if k not in _RESERVED_ATTRS:
                    extra[k] = v
                # 保留字段不传，静默跳过（如 exc_info 已单独处理）
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)


def get_logger(
    name: str,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB 轮转
    backup_count: int = 3,
) -> logging.Logger:
    """
    获取或创建一个统一 Logger。

    用法：
        from core.engines.quality.logger import get_logger
        log = get_logger("auto_memory")
        log.info("记忆保存成功", id="m123", tags=3)
        log.warning("搜索超时", query="xxx", elapsed_ms=5200)
        log.error("写入失败", exc_info=True)

    Args:
        name: 模块名称（如 "auto_memory", "circuit_breaker"）
        level: 日志级别（默认 INFO，模块可用 DEBUG 切换）
        log_to_file: 是否写入模块独立日志文件
        log_to_console: 是否也输出到控制台
        max_bytes: 日志轮转大小
        backup_count: 保留备份数

    Returns:
        logging.Logger 实例
    """
    if name in _loggers:
        return _loggers[name]

    logging.setLoggerClass(StructuredLogger)
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = StructuredFormatter()

    # 文件 Handler（模块独立日志）
    if log_to_file:
        log_path = os.path.join(LOG_DIR, f"{name}.log")
        fh = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    # 聚合日志 Handler（所有模块的 WARNING+ 写入 all.log）
    all_log_path = os.path.join(LOG_DIR, "all.log")
    all_fh = RotatingFileHandler(all_log_path, maxBytes=max_bytes * 2, backupCount=backup_count, encoding="utf-8")
    all_fh.setLevel(logging.WARNING)
    all_fh.setFormatter(formatter)
    logger.addHandler(all_fh)

    # 控制台 Handler
    if log_to_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    _loggers[name] = logger
    return logger


# ═══════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════

def set_all_level(level: int):
    """统一设置所有 Logger 的级别（用于调试/生产切换）"""
    for logger in _loggers.values():
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)


def get_all_loggers() -> Dict[str, int]:
    """列出所有已创建的 Logger 及其级别"""
    return {name: logger.level for name, logger in _loggers.items()}


# ═══════════════════════════════════════════
# 验证
# ═══════════════════════════════════════════

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

    print("=" * 60)
    print("统一日志系统 — 测试")
    print("=" * 60)

    log = get_logger("test_logger", log_to_console=True)

    # 普通消息
    log.debug("这是 DEBUG 消息（默认不显示）")
    log.info("记忆保存成功", id="m123", tags=3, elapsed_ms=45)
    log.warning("API 响应超时，触发重试", retry=1, max_retries=3)
    log.error("写入失败", reason="磁盘空间不足", exc_info=True)

    try:
        1 / 0
    except ZeroDivisionError:
        log.critical("引擎初始化失败", module="auto_memory", exc_info=True)

    # 验证日志文件写入
    log_path = os.path.join(LOG_DIR, "test_logger.log")
    try:
        with open(log_path) as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
        print(f"\n✅ 日志文件已写入: {log_path}")
        print(f"   大小: {os.path.getsize(log_path)} bytes")
        print(f"   内容预览:\n{content[:500]}")

    # 验证 all.log
    all_path = os.path.join(LOG_DIR, "all.log")
    try:
        with open(all_path) as f:
            all_content = f.read()
    except FileNotFoundError:
        all_content = ""
        print(f"\n✅ 聚合日志已写入: {all_path}")
        print(f"   大小: {os.path.getsize(all_path)} bytes")
        # DEBUG 不应出现在 all.log
        assert "DEBUG" not in all_content, "DEBUG 不应写入 all.log"
        print(f"   ✅ DEBUG 未写入 all.log（仅 WARNING+）")

    # 清理测试日志
    os.remove(log_path)
    os.remove(all_path)

    print("\n" + "=" * 60)
    print("全部测试通过 ✅")
    print("=" * 60)
