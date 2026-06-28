#!/usr/bin/env python3
"""
🦊 V111 全维诊断系统
升级版巡检 —— 不是跑个 ls，而是逐层验证代码、逻辑、数据、配置、运行时。
设计为可扩展模块体系，每个 check_xxx 独立，返回 (status, detail)。
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ============================================================
# 定义层级体系
# ============================================================

# 每个 check 返回: (level, status, detail)
# level: "critical" | "warning" | "info"
# status: "✅ pass" | "⚠️  warn" | "❌ fail" | "⛔ skip"
LEVEL_ORDER = {"critical": 0, "warning": 1, "info": 2}

CheckResult = Tuple[str, str, str]  # (level, status, detail)
CheckFn = Callable[[], CheckResult]

_checks: List[Tuple[str, str, CheckFn]] = []


def check(domain: str, name: str):
    """Decorator to register a check function."""

    def decorator(fn: CheckFn):
        _checks.append((domain, name, fn))
        return fn
    return decorator


def _print_banner(text: str, char: str = "="):
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}")


def _print_result(domain: str, name: str, level: str, status: str, detail: str):
    emoji_map = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    print(f"  {emoji_map.get(level, '⚪')} [{domain:<16}] {name:<28} {status}")
    if detail and status != "✅ pass":
        for ln in detail.split("\n")[:3]:
            print(f"      {ln}")


def run_all():
    total = len(_checks)
    prints: List[Dict] = []
    errors = 0
    warnings = 0

    print(f"\n{'=' * 70}")
    print(f"  🦊 V111 全维诊断系统 | {total} 项检查")
    print(f"{'=' * 70}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  工作区: {ROOT}")

    # Group by domain
    domains: Dict[str, List] = {}
    for domain, name, fn in _checks:
        domains.setdefault(domain, []).append((name, fn))

    for domain, items in sorted(domains.items()):
        _print_banner(domain)
        for name, fn in items:
            try:
                level, status, detail = fn()
            except Exception as e:
                level, status = "critical", "❌ crash"
                detail = f"{e}\n{traceback.format_exc()[:300]}"
            _print_result(domain, name, level, status, detail)
            if status in ("❌ fail", "❌ crash"):
                errors += 1
            if status == "⚠️  warn":
                warnings += 1

    print(f"\n{'=' * 70}")
    print(f"  诊断完成 | {'❌' if errors else '✅'} {errors} 错误, {'⚠️ ' if warnings else ''}{warnings} 警告, {total} 总检查")
    print(f"{'=' * 70}\n")

    return errors


# ============================================================
# 1. 文件系统完整性
# ============================================================

@check("文件系统", "核心文件清单")
def _check_core_files():
    required = [
        "memory_context/persona_runtime/persona_visual_focus_intent.py",
        "memory_context/persona_runtime/persona_visual_auto_generation_bridge.py",
        "memory_context/persona_runtime/persona_visual_wardrobe.py",
        "memory_context/persona_runtime/visual_wardrobe_profiles.json",
        "memory_context/persona_runtime/visual_persona_renderer.py",
        "assets/persona/seed_avatar.jpg",
    ]
    missing = [f for f in required if not (ROOT / f).exists()]
    if missing:
        return ("critical", "❌ fail", f"缺失文件: {', '.join(missing)}")
    return ("critical", "✅ pass", "全部 {len(required)} 个核心文件存在")


@check("文件系统", "测试文件清单")
def _check_test_files():
    required = [
        "tests/test_persona_visual_v111_48.py",
        "tests/test_persona_visual_v111_47.py",
        "tests/test_persona_visual_v111_45.py",
        "tests/test_persona_visual_v111_44.py",
        "tests/test_persona_visual_v111_43.py",
        "tests/test_persona_visual_v111_42.py",
    ]
    missing = [f for f in required if not (ROOT / f).exists()]
    if missing:
        return ("warning", "⚠️  warn", f"缺失测试文件: {', '.join(missing)}")
    return ("info", "✅ pass", f"全部 {len(required)} 个测试文件存在")


@check("文件系统", "审计脚本")
def _check_audit_scripts():
    required = [
        "scripts/audit_persona_visual_v111_48.py",
        "scripts/audit_persona_visual_v111_47.py",
        "scripts/diagnose_v111.py",  # 自己
    ]
    missing = [f for f in required if not (ROOT / f).exists()]
    if missing:
        return ("warning", "⚠️  warn", f"缺失: {', '.join(missing)}")
    return ("info", "✅ pass", f"全部 {len(required)} 个审计脚本存在")


@check("文件系统", "场景默认图索引")
def _check_scene_defaults():
    config_path = ROOT / "assets/persona/scene_defaults/scene_default_config.json"
    if not config_path.exists():
        return ("warning", "❌ fail", "scene_default_config.json 不存在")
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
        scenes = config.get("scenes", {})
        if not scenes:
            return ("warning", "⚠️  warn", "场景默认图配置为空")
        missing_imgs = []
        for scene_name, scene_cfg in scenes.items():
            for img in scene_cfg.get("default_images", []):
                fp = img.get("file_path", "")
                if fp and not (ROOT / fp).exists():
                    missing_imgs.append(f"{scene_name}:{fp}")
        if missing_imgs:
            return ("warning", "⚠️  warn", f"引用图片文件不存在: {'; '.join(missing_imgs[:5])}")
        return ("info", "✅ pass", f"{len(scenes)} 个场景, 全部图片存在")
    except Exception as e:
        return ("warning", "⚠️  warn", f"解析失败: {e}")


@check("文件系统", "衣柜图片完整性")
def _check_outfit_images():
    wardrobe_profiles = ROOT / "memory_context/persona_runtime/visual_wardrobe_profiles.json"
    if not wardrobe_profiles.exists():
        return ("warning", "⚠️  warn", "wardrobe profiles 不存在")
    try:
        profiles = json.loads(wardrobe_profiles.read_text(encoding='utf-8'))
        outfits = profiles.get("outfits", {})
        missing_refs = []
        missing_files = []
        for oid, info in outfits.items():
            ref = info.get("reference_image", "")
            if ref and not (ROOT / ref).exists():
                missing_refs.append(f"{oid}: {ref}")
            generated = info.get("generated_image_path", "")
            if generated and not (ROOT / generated).exists():
                missing_files.append(f"{oid}: {generated}")
        issues = []
        if missing_refs:
            issues.append(f"参考图缺失: {len(missing_refs)}")
        if missing_files:
            issues.append(f"生成图缺失: {len(missing_files)}")
        if issues:
            return ("warning", "⚠️  warn", "; ".join(issues))
        return ("info", "✅ pass", f"{len(outfits)} 套衣服, 引用图片全部存在")
    except Exception as e:
        return ("warning", "⚠️  warn", f"解析失败: {e}")


@check("文件系统", "运行时状态文件")
def _check_runtime_state():
    state_file = ROOT / ".persona_visual/runtime_wardrobe_state.json"
    if not state_file.exists():
        return ("info", "✅ pass", "运行时状态文件不存在 (首次运行)")
    try:
        state = json.loads(state_file.read_text(encoding='utf-8'))
        if state.get("current_outfit"):
            return ("info", "✅ pass", f"当前服装: {state['current_outfit']}")
        return ("info", "⚠️  warn", "运行时状态文件存在但 current_outfit 为空")
    except Exception as e:
        return ("warning", "⚠️  warn", f"解析失败: {e}")


@check("文件系统", "已生成图片数量")
def _check_generated_images():
    generated_dir = ROOT / "generated-images"
    if not generated_dir.exists():
        return ("info", "⛔ skip", "generated-images/ 不存在")
    images = list(generated_dir.glob("*.jpg")) + list(generated_dir.glob("*.png"))
    total_size = sum(f.stat().st_size for f in images) / (1024 * 1024)
    return ("info", "✅ pass", f"{len(images)} 张图片, 总计 {total_size:.1f} MB")


# ============================================================
# 2. 代码语法与导入
# ============================================================

@check("代码质量", "Python 语法检查")
def _check_python_syntax():
    all_py = list(ROOT.glob("**/*.py"))
    exclude_dirs = {".git", "__pycache__", "node_modules", ".openclaw"}
    errors = []
    for pyf in all_py:
        if any(part in exclude_dirs for part in pyf.parts):
            continue
        if pyf.name == "backup.py":
            continue
        try:
            compile(pyf.read_text(encoding='utf-8'), str(pyf), 'exec')
        except SyntaxError as e:
            errors.append(f"{pyf.relative_to(ROOT)}: {e}")
    if errors:
        return ("critical", "❌ fail", "\n".join(errors[:5]))
    return ("info", "✅ pass", f"{len(all_py)} 个文件语法正确")


@check("代码质量", "焦点识别模块导入")
def _check_focus_import():
    try:
        from memory_context.persona_runtime.persona_visual_focus_intent import (
            detect_focus_request, build_focus_enhanced_prompt, _FOCUS_ENHANCEMENT_TABLE
        )
        assert callable(detect_focus_request)
        assert callable(build_focus_enhanced_prompt)
        assert isinstance(_FOCUS_ENHANCEMENT_TABLE, dict) and len(_FOCUS_ENHANCEMENT_TABLE) >= 12
        return ("critical", "✅ pass", f"导入成功, {len(_FOCUS_ENHANCEMENT_TABLE)} 个焦点目标")
    except Exception as e:
        return ("critical", "❌ fail", str(e))


@check("代码质量", "衣柜模块导入")
def test_wardrobe_import():
    try:
        from memory_context.persona_runtime.persona_visual_wardrobe import (
            choose_outfit, current_outfit, save_current_outfit, _state
        )
        assert callable(choose_outfit)
        assert callable(current_outfit)
        return ("critical", "✅ pass", "导入成功")
    except Exception as e:
        return ("critical", "❌ fail", str(e))


@check("代码质量", "自动生成桥导入")
def test_bridge_import():
    try:
        from memory_context.persona_runtime.persona_visual_auto_generation_bridge import (
            prepare_generation_context, generate_from_prediction
        )
        assert callable(prepare_generation_context)
        assert callable(generate_from_prediction)
        return ("critical", "✅ pass", "导入成功, 含 prepare + generate 双入口")
    except Exception as e:
        return ("critical", "❌ fail", str(e))


@check("代码质量", "Seedream Provider 导入")
def test_provider_import():
    try:
        from memory_context.persona_runtime.providers.seedream_provider import (
            provider_ready, provider_env, generate_image
        )
        ready = provider_ready()
        env = provider_env()
        return ("critical", f"{'✅' if ready else '⚠️'} pass" if ready else "warning",
                f"provider_ready={ready}, url={env.get('url', '?')}, key={'✅' if env.get('api_key') else '❌'}")
    except Exception as e:
        return ("critical", "❌ fail", str(e))


# ============================================================
# 3. 功能逻辑验证
# ============================================================

@check("功能逻辑", "焦点识别 - 看看腿")
def test_focus_legs():
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
    r = detect_focus_request("看看腿")
    if r.get("focus_target") != "legs":
        return ("critical", "❌ fail", f"期待 legs, 得到 {r['focus_target']}")
    return ("critical", "✅ pass", f"target={r['focus_target']}, mode={r['focus_match_mode']}, has_enhanced={r.get('focus_prompt_enhanced', False)}")


@check("功能逻辑", "焦点识别 - 所有目标")
def test_focus_all_targets():
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
    test_cases = [
        ("看看腿", "legs"), ("看尾巴", "tail"), ("看看耳朵", "ears"),
        ("摸摸头", "headpat"), ("看腰", "waist"), ("摆个pose", "pose"),
        ("看看衣服", "outfit"), ("看翅膀", "wings"), ("看看脸", "face"),
        ("看看眼睛", "eyes"), ("看鞋子", "shoes"), ("看头发", "hair"),
    ]
    failures = []
    for text, expected in test_cases:
        r = detect_focus_request(text)
        if r.get("focus_target") != expected:
            failures.append(f"'{text}' -> {r['focus_target']} (期待 {expected})")
    if failures:
        return ("critical", "❌ fail", "; ".join(failures))
    return ("critical", "✅ pass", f"全部 {len(test_cases)} 个焦点正确")


@check("功能逻辑", "焦点识别 - 无焦点")
def test_focus_none():
    from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
    texts = ["你好呀", "早上好", "今天天气不错", "我想问个问题", "好的"]
    failures = [t for t in texts if detect_focus_request(t).get("focus_target")]
    if failures:
        return ("warning", "⚠️  warn", f"无焦点文本触发了焦点识别: {failures}")
    return ("info", "✅ pass", f"全部 {len(texts)} 个无焦点文本未误触发")


@check("功能逻辑", "衣柜选择 - 看看腿")
def test_wardrobe_legs():
    from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
    o = choose_outfit(text="看看腿", mood="shy", semantic_scene="bashful_scene", focus_target="legs", auto_mode=True)
    if o.get("choice_source") != "focus_recommend":
        return ("critical", "❌ fail", f"期待 focus_recommend, 得到 {o['choice_source']}, outfit={o['outfit_id']}")
    return ("critical", "✅ pass", f"outfit={o['outfit_id']}, source={o['choice_source']}")


@check("功能逻辑", "衣柜选择 - 显式指定")
def test_wardrobe_explicit():
    from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
    o = choose_outfit(text="穿星尘织梦看看腿", mood="shy", semantic_scene="bashful_scene", focus_target="legs", auto_mode=True)
    if o.get("choice_source") != "explicit_text":
        return ("critical", "❌ fail", f"期待 explicit_text, 得到 {o['choice_source']}, outfit={o['outfit_id']}")
    return ("critical", "✅ pass", f"outfit={o['outfit_id']}, source={o['choice_source']}")


@check("功能逻辑", "衣柜选择 - 运行时当前")
def test_wardrobe_current():
    from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit, save_current_outfit, _state
    import json
    save_current_outfit("moonfeather_robe")
    try:
        o = choose_outfit(text="看看尾巴尖", mood="shy", semantic_scene="bashful_scene", focus_target="tail", auto_mode=True)
        result = (o.get("choice_source") in ("current_outfit", "scene_recommend", "focus_recommend"),
                  f"outfit={o['outfit_id']}, source={o['choice_source']}")
    finally:
        state = ROOT / ".persona_visual/runtime_wardrobe_state.json"
        json.dump({}, state.open('w'))
    
    if result[0]:
        return ("critical", "✅ pass", result[1])
    return ("critical", "⚠️  warn", result[1])


@check("功能逻辑", "衣柜选择 - focus_outfit_map 完整性")
def test_focus_map_integrity():
    from memory_context.persona_runtime.persona_visual_focus_intent import _FOCUS_ENHANCEMENT_TABLE
    from memory_context.persona_runtime.persona_visual_wardrobe import _profiles
    profiles = _profiles()
    focus_map = profiles.get("focus_outfit_map", {})
    if not focus_map:
        return ("critical", "❌ fail", "focus_outfit_map 为空")
    # Check all enhancement table targets exist in focus_outfit_map
    missing = []
    for target in _FOCUS_ENHANCEMENT_TABLE:
        if target not in focus_map:
            missing.append(target)
    if missing:
        return ("warning", "⚠️  warn", f"增强表有但映射表缺失: {missing}")
    # Check mapping entries reference valid outfits
    cfg = json.loads((ROOT / "memory_context/persona_runtime/visual_wardrobe_profiles.json").read_text())
    valid_outfits = set(cfg.get("outfits", {}).keys())
    bad_refs = []
    for target, candidates in focus_map.items():
        for c in candidates:
            if c not in valid_outfits:
                bad_refs.append(f"{target}:{c}")
    if bad_refs:
        return ("warning", "⚠️  warn", f"映射引用了不存在的衣服: {bad_refs}")
    return ("info", "✅ pass", f"{len(focus_map)} 个目标映射, 全部引用有效")


@check("功能逻辑", "焦点增强提示词完整性")
def test_enhancement_table():
    from memory_context.persona_runtime.persona_visual_focus_intent import _FOCUS_ENHANCEMENT_TABLE
    required_keys = {"action", "expression", "composition", "atmosphere"}
    incomplete = []
    for target, data in _FOCUS_ENHANCEMENT_TABLE.items():
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            incomplete.append(f"{target}: 缺失 {missing_keys}")
    if incomplete:
        return ("warning", "⚠️  warn", "; ".join(incomplete))
    return ("info", "✅ pass", f"{len(_FOCUS_ENHANCEMENT_TABLE)} 个目标, 全部 4 个维度完整")


@check("功能逻辑", "自动生成桥 - dry run 验证")
def test_bridge_dry_run():
    from memory_context.persona_runtime.persona_visual_auto_generation_bridge import generate_from_prediction
    pred = {
        'auto_generation_candidate': True, 'should_auto_generate': True,
        'visual_scope': 'persona_scene_auto_only', 'purpose': 'persona_visualization',
        'mood': 'shy', 'semantic_scene': 'bashful_scene',
        'emotion_signature': ['害羞'], 'expression_hints': ['脸红']
    }
    result = generate_from_prediction(dict(pred), user_message='看看腿', dry_run=True)
    if result.get("focus_prompt_enhanced") is not True:
        return ("critical", "❌ fail", f"focus_prompt_enhanced 应为 True")
    if result.get("outfit", {}).get("choice_source") != "focus_recommend":
        return ("critical", "❌ fail", f"choice_source not focus_recommend: {result.get('outfit', {}).get('choice_source')}")
    return ("critical", "✅ pass", f"focus={result['focus_target']}, outfit={result['outfit']['outfit_id']}, source={result['outfit']['choice_source']}")


# ============================================================
# 4. 配置与数据验证
# ============================================================

@check("配置验证", "visual_wardrobe_profiles.json 结构")
def test_profile_schema():
    path = ROOT / "memory_context/persona_runtime/visual_wardrobe_profiles.json"
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        return ("critical", "❌ fail", f"JSON 解析失败: {e}")
    
    issues = []
    for key in ("scene_outfit_map", "mood_outfit_map", "focus_outfit_map", "outfits"):
        if key not in data:
            issues.append(f"缺少顶级键: {key}")
    if data.get("version") is None:
        issues.append("缺少 version 字段")
    outfits = data.get("outfits", {})
    for oid, info in outfits.items():
        if not isinstance(info, dict):
            issues.append(f"outfit '{oid}' 不是 dict")
        else:
            if "prompt_suffix" not in info:
                issues.append(f"outfit '{oid}' 缺少 prompt_suffix")
    if issues:
        return ("warning", "⚠️  warn", "; ".join(issues))
    return ("info", "✅ pass", f"{len(outfits)} 套衣服, 3 个映射表, 结构完整")


@check("配置验证", "scene_default_config.json 结构")
def test_scene_config():
    path = ROOT / "assets/persona/scene_defaults/scene_default_config.json"
    if not path.exists():
        return ("info", "⛔ skip", "文件不存在")
    try:
        data = json.loads(path.read_text())
    except:
        return ("warning", "⚠️  warn", "JSON 解析失败")
    if "scenes" not in data:
        return ("warning", "⚠️  warn", "缺少 scenes 顶级键")
    for name, scene in data["scenes"].items():
        imgs = scene.get("default_images", [])
        for img in imgs:
            fp = img.get("file_path", "")
            if fp and not (ROOT / fp).exists():
                return ("warning", "⚠️  warn", f"{name} -> {fp} 文件不存在")
    return ("info", "✅ pass", f"{len(data['scenes'])} 个场景, 全部有效")


@check("配置验证", "环境变量检查")
def test_env_vars():
    env_path = os.path.expanduser("~/.openclaw/.xiaoyienv")
    if not os.path.exists(env_path):
        return ("critical", "❌ fail", ".xiaoyienv 文件不存在")
    required_vars = {"PERSONAL-UID", "PERSONAL-API-KEY", "SERVICE_URL"}
    found = set()
    for line in open(env_path):
        if "=" in line:
            k = line.split("=", 1)[0].strip()
            found.add(k)
    missing = required_vars - found
    if missing:
        return ("critical", "❌ fail", f"缺失环境变量: {missing}")
    return ("critical", "✅ pass", f"关键环境变量已设置 ({len(found)} 个)")


# ============================================================
# 5. 安全验证
# ============================================================

@check("安全检查", "敏感文件保护")
def test_sensitive_files():
    # Known test files that intentionally use fake secrets for testing redactors/security
    # Exclude these directories/files from false positive detection
    EXCLUDED_PATTERNS = [
        "test_v107", "test_v167",  # Security function test data (fake secrets for testing PrivacyRedactor etc.)
        "v94_mainline_trigger_gate",  # Governance evaluation test data
        "sitecustomize",  # Environment setup script referencing environment variables
    ]
    py_files = list(ROOT.glob("*.py")) + list(ROOT.glob("**/*.py"))
    issues = []
    for pf in py_files:
        if "__pycache__" in str(pf) or ".git" in str(pf):
            continue
        if any(excl in pf.name for excl in EXCLUDED_PATTERNS):
            continue
        try:
            content = pf.read_text()
            for pattern in ["PERSONAL-API-KEY", "PERSONAL-UID", "password=", "api_key="]:
                if pattern.lower() in content.lower() and pattern.lower() not in ("persona_api_user", "persona_api_password"):
                    if f'"{pattern.lower()}"' not in content.lower() and f"'{pattern.lower()}'" not in content.lower():
                        issues.append(f"{pf.name}: 可能泄露 {pattern}")
        except:
            pass
    if issues:
        return ("warning", "⚠️  warn", "; ".join(issues[:5]))
    return ("info", "✅ pass", "无硬编码密钥")


@check("安全检查", "AUTO_SAFE_FORBIDDEN 检查")
def test_auto_safe():
    from memory_context.persona_runtime.persona_visual_wardrobe import AUTO_SAFE_FORBIDDEN
    from memory_context.persona_runtime.persona_visual_wardrobe import _profiles
    profiles = _profiles()
    forbidden = set(AUTO_SAFE_FORBIDDEN)
    focus_map = profiles.get("focus_outfit_map", {})
    issues = []
    for target, candidates in focus_map.items():
        for c in candidates:
            if c in forbidden:
                issues.append(f"focus_outfit_map[{target}] 引用了 forbidden 衣服 {c}")
    if issues:
        return ("warning", "⚠️  warn", "; ".join(issues))
    return ("info", "✅ pass", f"焦点映射未引用禁选衣服")


# ============================================================
# 6. 性能与维护
# ============================================================

@check("性能维护", "临时备份文件数量")
def test_backup_count():
    tmp_dir = Path("/tmp")
    backups = list(tmp_dir.glob("workspace*.tar.gz"))
    if len(backups) > 10:
        return ("info", "⚠️  warn", f"/tmp 下有 {len(backups)} 个备份文件, 建议清理")
    return ("info", "✅ pass", f"{len(backups)} 个备份文件")


@check("性能维护", "生成图片目录大小")
def test_image_dir_size():
    img_dir = ROOT / "generated-images"
    if not img_dir.exists():
        return ("info", "⛔ skip", "目录不存在")
    total = sum(f.stat().st_size for f in img_dir.glob("*.*") if f.is_file())
    total_mb = total / (1024 * 1024)
    if total_mb > 20:
        return ("info", "⚠️  warn", f"{total_mb:.1f} MB, 建议定期清理")
    return ("info", "✅ pass", f"{total_mb:.1f} MB")


# ============================================================
# 7. 新增能力：代码覆盖率分析
# ============================================================

@check("代码结构", "函数导出完整性")
def test_all_exports():
    from memory_context.persona_runtime import persona_visual_focus_intent as fi
    from memory_context.persona_runtime import persona_visual_wardrobe as wd
    
    expected_fi = ["detect_focus_request", "build_focus_enhanced_prompt"]
    expected_wd = ["choose_outfit", "current_outfit", "save_current_outfit"]
    
    missing_fi = [name for name in expected_fi if not hasattr(fi, name)]
    missing_wd = [name for name in expected_wd if not hasattr(wd, name)]
    all_missing = missing_fi + missing_wd
    if all_missing:
        return ("critical", "❌ fail", f"缺失函数: {all_missing}")
    return ("info", "✅ pass", f"{len(expected_fi + expected_wd)} 个关键函数均可调用")


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    error_count = run_all()
    sys.exit(error_count)
