"""
Crusheart Agent OS — 会话启动预加载
每次新会话开始时执行，验证所有引擎可用性并确保状态文件最新
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

BEIJING_TZ = timezone(timedelta(hours=8))
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE") or os.path.expanduser("~/.openclaw/workspace")
ENGINE_STATE = os.path.join(WORKSPACE, ".state", ".engine_state.json")


def check_state():
    """检查引擎初始化状态，如果未初始化则执行初始化"""
    if not os.path.exists(ENGINE_STATE):
        print("⚠️ 引擎未初始化，执行 init_engines.py...")
        init_script = os.path.join(WORKSPACE, "core", "engines", "init", "init_engines.py")
        if os.path.exists(init_script):
            import subprocess
            result = subprocess.run([sys.executable, init_script], capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print(f"❌ 引擎初始化失败: {result.stderr}")
                return False
        return True
    
    with open(ENGINE_STATE) as f:
        state = json.load(f)
    
    if state["status"] != "ready":
        print(f"⚠️ 引擎状态异常: {state['status']}")
        return False
    
    print(f"✅ 引擎状态正常 ({state['success']}/{state['total']} 就绪)")
    
    # 打印每个引擎的详细状态
    for e in state["engines"]:
        icon = "✅" if e["status"] == "ready" else "❌"
        err = f" - {e['error']}" if e.get("error") else ""
        print(f"  {icon} {e['name']}{err}")
    
    return True


def verify_imports():
    """验证所有引擎模块可导入"""
    modules = [
        ("core.engines.hooks.dual_mode_classifier", "双模式分类器"),
        ("core.engines.init.init_engines", "引擎初始化"),
        ("core.engines.tools.mutex_engine", "互斥锁引擎"),
        ("core.engines.quality.anti_fake_validator", "防幻觉引擎"),
        ("core.engines.hooks.hook_engine", "钩子引擎"),
        ("core.engines.hooks.self_evolution_v3", "自进化引擎"),
        ("core.engines.memory.memory_layer_engine", "记忆层引擎"),
        ("core.engines.init.lazy_load_enforcer", "懒加载引擎"),
        ("core.engines.workflow.engine_orchestrator", "引擎编排路由"),
        ("core.engines.tools.enhancement_engine", "增强引擎"),
    ]
    
    if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)
    all_ok = True
    for module_path, name in modules:
        try:
            import importlib
            importlib.import_module(module_path)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            all_ok = False
    
    if all_ok:
        print(f"✅ 全部 {len(modules)} 个引擎模块可导入")
    return all_ok


def verify_cron():
    """检查关键cron任务是否存在"""
    expected_crons = {
        "统一维护": "统一维护+记忆维护",
        "引擎重初始化": "引擎重初始化",
    }
    try:
        import subprocess
        result = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        found = {}
        for key, name in expected_crons.items():
            if name in output:
                found[key] = True
            else:
                found[key] = False
                print(f"  ⚠️ 未找到cron: {name}")
        
        ok_count = sum(1 for v in found.values() if v)
        print(f"✅ Cron任务: {ok_count}/{len(found)} 正常")
        return ok_count == len(found)
    except Exception as e:
        print(f"  ⚠️ 检查cron失败: {e}")
        return False


def run_new_module_checks():
    """
    会话启动时运行新增模块的快速检查。
    1. 身份漂移检测 (identity_drift_guard)
    2. 会话恢复提示 (session_handoff)
    3. 用户动态画像状态 (user_dynamic_portrait_v2)
    """
    if WORKSPACE not in sys.path: sys.path.insert(0, WORKSPACE)

    # --- 1. 身份漂移检测 ---
    try:
        from core.engines.quality.identity_drift_guard import check_on_startup
        drift_result = check_on_startup()
        status = drift_result.get("status", "unknown")
        score = drift_result.get("drift_score", 0.0)
        if status == "safe":
            print(f"✅ 身份漂移检测: 安全（漂移分 {score:.3f}）")
        elif status == "baseline_created":
            print("✅ 身份基线已初始化")
        else:
            pass  # warn/alert/critical 已在 check_on_startup 内打印
    except Exception as e:
        print(f"  ⚠️ 身份漂移检测跳过: {e}")

    # --- 2. 会话恢复提示 ---
    try:
        from core.engines.init.session_manager import check_on_startup as handoff_check
        handoff_check()
    except Exception as e:
        print(f"  ⚠️ 会话交接加载跳过: {e}")

    # --- 3. 用户动态画像状态 ---
    try:
        from core.engines.memory.user_dynamic_portrait import get_portrait
        portrait = get_portrait()
        summary = portrait.get_context_summary()
        count = summary.get("message_count", 0)
        if count > 0:
            print(f"✅ 用户动态画像引擎: 已建模（共 {count} 条消息记录，风格:{summary.get('style','balanced')} / 风险:{summary.get('risk_tolerance','medium')}）")
        else:
            print("✅ 用户动态画像引擎: 初始化完毕（尚无历史消息）")
    except Exception as e:
        print(f"  ⚠️ 用户动态画像引擎加载跳过: {e}")

    # --- 4. 近期记忆预热（v4.3 新增） ---
    # 自动搜索近期核心记忆，写入 .handoff_state/last_memory_context.md
    # 提高新会话对话轮次对历史上下文的感知能力
    try:
        from core.engines.memory.auto_memory import AutoMemory
        am = AutoMemory()
        # 搜索近期重要内容（不限tag，查最近变更）
        recent = am.search("系统修改 引擎更新 bug修复 会话摘要")
        if recent:
            lines = []
            for item in recent[:6]:
                text = item.get("text", "") if isinstance(item, dict) else str(item)[:150]
                ts = item.get("timestamp", "") if isinstance(item, dict) else ""
                lines.append(f"- {'[' + ts + '] ' if ts else ''}{text[:200]}")
            memory_md = f"# 近期记忆预热\n\n> 搜索时间: {datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n> 命中: {len(recent)} 条\n\n" + "\n".join(lines[:8]) + "\n"
            mem_file = os.path.join(WORKSPACE, ".handoff_state", "last_memory_context.md")
            os.makedirs(os.path.dirname(mem_file), exist_ok=True)
            with open(mem_file, "w", encoding="utf-8") as f:
                f.write(memory_md)
            print(f"✅ 记忆预热: {len(recent)} 条近期记忆已缓存")
        else:
            print("   ℹ️ 记忆预热: 无近期记忆")
            # 清理过期文件
            mem_file = os.path.join(WORKSPACE, ".handoff_state", "last_memory_context.md")
            try:
                os.remove(mem_file)
            except OSError:
                pass
    except Exception as e:
        print(f"  ⚠️ 记忆预热跳过: {e}")


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

    ts = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] ===== Crusheart Agent OS 会话启动验证 =====")
    
    state_ok = check_state()
    import_ok = verify_imports()
    cron_ok = verify_cron()

    # 新增模块检查
    run_new_module_checks()
    
    if state_ok and import_ok:
        print(f"✅ 全部引擎就绪，Crusheart Agent OS 正常运行")
    else:
        print(f"⚠️ 部分组件异常，将继续启动自检...")

    # ── 启动自检 JSON 报告（#50） ──
    try:
        from core.engines.init.startup_health_check import run_startup_health_check
        health = run_startup_health_check()
        if health.get("summary", {}).get("fail", 0) > 0:
            print(f"⚠️ 健康自检发现 {health['summary']['fail']} 个问题")
    except Exception as e:
        print(f"  ⚠️ 健康报告生成失败: {e}")

    print(f"[{datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')}] ===== 验证完成 =====")
    sys.exit(0)
