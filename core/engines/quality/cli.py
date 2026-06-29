"""
cli.py — #46: Judge Engine & Quality Dashboard 统一命令行入口

从 judge_engine.py 和 quality_dashboard.py 中提取的 CLI 层，
所有子命令归口管理，保持与原有行为完全一致。

用法：
  python3 cli.py score --query "xxx" --response "xxx"
  python3 cli.py replay --query "xxx"
  python3 cli.py reflect --query "xxx" --response "xxx" [--faithfulness N] [--relevance N] [--completeness N]
  python3 cli.py reflexion-stats
  python3 cli.py stats
  python3 cli.py correction-detect --msg "xxx"
  python3 cli.py correction-list [--type TYPE] [--limit N]
  python3 cli.py correction-distill [--min-occ N]
  python3 cli.py quality-brief     # quality_dashboard init() 快捷
"""

import argparse
import json
import sys
import os

# 将工作区加入 sys.path（兼容引擎独立运行）
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from core.engines.quality.judge_engine import (
    JudgeEngine,
    REFLEXION_PATTERNS,
)


def cmd_score(args):
    """score 子命令"""
    engine = JudgeEngine()
    scores = engine.score(args.query, args.response, args.context)
    engine.store_verified(args.query, args.response, scores)
    status = "\u2705 PASS" if scores["passed"] else "\u274c FAIL"
    print(f"\u8bc4\u5206\u7ed3\u679c [{status}]:")
    print(f"  \u5fe0\u5b9e\u5ea6: {scores['faithfulness']}/10")
    print(f"  \u76f8\u5173\u6027: {scores['relevance']}/10")
    print(f"  \u5b8c\u6574\u6027: {scores['completeness']}/10")


def cmd_replay(args):
    """replay 子命令"""
    engine = JudgeEngine()
    records = engine.replay(args.query)
    if records:
        print(f"\u627e\u5230 {len(records)} \u6761\u5339\u914d\u8bb0\u5fc6:")
        for i, r in enumerate(records, 1):
            score_str = f"{r.get('faithfulness',0)}/{r.get('relevance',0)}/{r.get('completeness',0)}"
            print(f"  [{i}] {r['query'][:60]} | \u5206:{score_str}")
    else:
        print("\u672a\u627e\u5230\u5339\u914d\u8bb0\u5fc6")


def cmd_stats(args):
    """stats 子命令"""
    engine = JudgeEngine()
    s = engine.stats()
    print(f"\u5df2\u9a8c\u8bc1\u8bb0\u5fc6: {s['total']} \u6761")
    if s['total'] > 0:
        print(f"\u5e73\u5747\u5206: {s['avg_faithfulness']}(\u5fe0\u5b9e) / {s['avg_relevance']}(\u76f8\u5173) / {s['avg_completeness']}(\u5b8c\u6574)")
        print(f"\u7efc\u5408\u5747\u5206: {s['avg_total']}")


def cmd_reflect(args):
    """reflect 子命令"""
    engine = JudgeEngine()
    scores = {"faithfulness": args.faithfulness, "relevance": args.relevance,
               "completeness": args.completeness, "passed": False}
    result = engine.reflect(args.query, args.response, scores)
    if result["reflected"]:
        print(f"\u2705 \u53cd\u601d\u5df2\u8bb0\u5f55:")
        print(f"  \u5931\u8d25\u6a21\u5f0f: {', '.join(result['patterns']) if result['patterns'] else '\u672a\u8bc6\u522b'}")
    else:
        print("\u2139\ufe0f  \u65e0\u9700\u53cd\u601d")
    if result.get("reflexion_id"):
        print(f"  ID: {result['reflexion_id']}")


def cmd_reflexion_stats(args):
    """reflexion-stats 子命令"""
    engine = JudgeEngine()
    s = engine.reflexion_stats()
    print(f"\u53cd\u601d\u8bb0\u5f55\u603b\u6570: {s['total']} \u6761")
    if s.get("pattern_counts"):
        print(f"\u5931\u8d25\u6a21\u5f0f\u5206\u5e03:")
        for pattern, count in s["pattern_counts"].items():
            desc = REFLEXION_PATTERNS.get(pattern, pattern)
            print(f"  {pattern}: {count}\u6b21 \u2014 {desc[:30]}")


def cmd_correction_detect(args):
    """correction-detect 子命令"""
    from core.engines.quality.judge_engine import ReplayBuffer
    rb = ReplayBuffer()
    result = rb.detect(args.msg)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_correction_list(args):
    """correction-list 子命令"""
    from core.engines.quality.judge_engine import ReplayBuffer
    rb = ReplayBuffer()
    records = rb.list_corrections(type_filter=args.type, limit=args.limit)
    print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_correction_distill(args):
    """correction-distill 子命令"""
    from core.engines.quality.judge_engine import ReplayBuffer
    rb = ReplayBuffer()
    result = rb.distill(min_occurrences=args.min_occ)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_quality_brief(args):
    """quality-brief 子命令 — quality_dashboard 快捷"""
    from core.engines.quality.quality_dashboard import QualityScoreDashboard
    dashboard = QualityScoreDashboard()
    overview = dashboard.get_overview()
    overall = overview["overall_score"]
    health = overview["health_summary"]
    alerts = overview["active_alerts"]
    print(f"  \U0001f4ca Quality Score Dashboard: \u603b\u4f53\u8bc4\u5206 {overall:.1%} | "
          f"{health.get('HEALTHY', 0)} \u5065\u5eb7 | "
          f"{health.get('DEGRADED', 0)} \u964d\u7ea7 | "
          f"{health.get('CRITICAL', 0)} \u5371\u6025 | "
          f"{health.get('POOR', 0)} \u5dee\u52b2 | "
          f"\u544a\u8b66 {alerts}")
    result = {
        "status": "ready",
        "overview": overview,
        "ranking": dashboard.get_ranking(),
        "initialized_at": __import__('datetime').datetime.now(
            __import__('datetime').timezone(__import__('datetime').timedelta(hours=8))
        ).isoformat()
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Judge Engine & Quality Dashboard: LLM-as-Judge \u81ea\u8bc4\u5206 & \u91cd\u653e\u7f13\u51b2\u533a"
    )
    sub = parser.add_subparsers(dest="cmd")

    # score
    p_score = sub.add_parser("score")
    p_score.add_argument("--query", required=True)
    p_score.add_argument("--response", required=True)
    p_score.add_argument("--context", default="")

    # replay
    p_replay = sub.add_parser("replay")
    p_replay.add_argument("--query", required=True)

    # reflect
    p_reflect = sub.add_parser("reflect")
    p_reflect.add_argument("--query", required=True)
    p_reflect.add_argument("--response", required=True)
    p_reflect.add_argument("--faithfulness", type=int, default=4)
    p_reflect.add_argument("--relevance", type=int, default=5)
    p_reflect.add_argument("--completeness", type=int, default=5)

    # reflexion-stats
    sub.add_parser("reflexion-stats")

    # stats
    sub.add_parser("stats")

    # correction-detect
    p_cd = sub.add_parser("correction-detect")
    p_cd.add_argument("--msg", required=True)

    # correction-list
    p_cl = sub.add_parser("correction-list")
    p_cl.add_argument("--type", default=None)
    p_cl.add_argument("--limit", type=int, default=20)

    # correction-distill
    p_cdist = sub.add_parser("correction-distill")
    p_cdist.add_argument("--min-occ", type=int, default=3)

    # quality-brief (from quality_dashboard)
    sub.add_parser("quality-brief")

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        return

    cmds = {
        "score": cmd_score,
        "replay": cmd_replay,
        "stats": cmd_stats,
        "reflect": cmd_reflect,
        "reflexion-stats": cmd_reflexion_stats,
        "correction-detect": cmd_correction_detect,
        "correction-list": cmd_correction_list,
        "correction-distill": cmd_correction_distill,
        "quality-brief": cmd_quality_brief,
    }

    handler = cmds.get(args.cmd)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
