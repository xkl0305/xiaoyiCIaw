#!/usr/bin/env python3
"""
generate_maintenance_report.py
根据车型+里程，生成保养/故障分析报告（支持燃油车 + 新能源车双轨）
"""
import json, os, sys, glob
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
KNOW = os.path.join(BASE, "..", "knowledge")

# ═══════════════════════════════════════════
# 品牌识别
# ═══════════════════════════════════════════
EV_BRANDS = {
    "tesla":   ["tesla", "特斯拉", "model 3", "model y", "model s", "model x"],
    "byd":      ["byd", "比亚迪", "汉", "海豹", "宋", "秦", "元", "唐", "海豚"],
    "li_auto":  ["理想", "li auto", "l6", "l7", "l8", "l9", "mega"],
    "aito":     ["问界", "aito", "m5", "m7", "m8", "m9"],
    "xpeng":    ["小鹏", "xpeng", "p7", "g6", "g9", "x9", "mona"],
    "nio":      ["蔚来", "nio", "et5", "et7", "es6", "es8", "ec6", "et9"],
    "xiaomi":   ["小米", "xiaomi", "su7", "yu7", "ultra"],
}

def is_ev_brand(brand_str: str) -> bool:
    s = brand_str.lower()
    for keys in EV_BRANDS.values():
        for k in keys:
            if k in s:
                return True
    return False

def detect_brand(model_str: str) -> str | None:
    s = model_str.lower()
    for brand, keys in EV_BRANDS.items():
        for k in keys:
            if k in s:
                return brand
    return None

# ═══════════════════════════════════════════
# 加载知识库
# ═══════════════════════════════════════════
def load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def find_faults(brand: str, model: str) -> list:
    """按 brand + model 查找 common_faults.json，匹配 meta.model 字段"""
    model_lower = model.lower()
    exact = None
    fallback = None
    patterns = [
        os.path.join(KNOW, brand, "*", "common_faults.json"),
    ]
    for pat in patterns:
        for fp in sorted(glob.glob(pat)):
            d = load_json(fp)
            faults = d.get("faults", [])
            if not faults:
                continue
            meta_model = d.get("meta", {}).get("model", "").lower()
            if not fallback:
                fallback = faults
            # 精确匹配：meta.model 包含 model 字符串，或反过来
            if model_lower in meta_model or meta_model in model_lower:
                exact = faults
                break
        if exact:
            break
    return exact or fallback or []

def load_schedule() -> dict:
    return load_json(os.path.join(KNOW, "general", "maintenance_schedule.json"))

# ═══════════════════════════════════════════
# 保养周期逻辑
# ═══════════════════════════════════════════
def get_active_schedule(is_ev: bool) -> list:
    d = load_schedule()
    if is_ev:
        return d.get("ev_schedule", [])
    return d.get("schedule", [])

def get_brand_overrides(brand: str, is_ev: bool) -> dict:
    d = load_schedule()
    brand_map = {
        "tesla":   "Tesla",
        "byd":     "BYD",
        "li_auto": "Li Auto",
        "aito":    "AITO",
        "xpeng":   "XPeng",
        "nio":     "NIO",
        "xiaomi":  "Xiaomi EV",
        "audi":    "Audi",
    }
    key = brand_map.get(brand)
    overrides = d.get("brand_specific", {})
    return overrides.get(key, {}) if key else {}

def calc_status(current_km: int, schedule_item: dict, last_km: int | None) -> dict:
    km = schedule_item["km"]
    item = schedule_item["item"]
    notes = schedule_item.get("notes", "")
    diff = current_km - km
    # 上次保养里程
    if last_km is not None:
        diff_last = current_km - last_km
        overdue_km = max(0, diff_last - 1000)  # 给1k缓冲
    else:
        overdue_km = max(0, current_km - km)
    if current_km < km:
        status = "✅ 未到期"
        urgency = "low"
    elif current_km < km * 1.1:
        status = "⚠️ 即将到期"
        urgency = "medium"
    else:
        status = "🔴 已逾期"
        urgency = "high"
    return {
        "km": km, "item": item, "notes": notes,
        "status": status, "urgency": urgency,
        "overdue_km": overdue_km,
        "diff": diff,
    }

# ═══════════════════════════════════════════
# 报告生成
# ═══════════════════════════════════════════
def generate_text_report(brand: str, model: str, current_km: int,
                        last_km: int | None = None,
                        purchase_date: str = "", is_ev: bool | None = None) -> str:
    if is_ev is None:
        is_ev = is_ev_brand(brand)
    ev_tag = "⚡ 新能源" if is_ev else "⛽ 燃油车"
    schedule = get_active_schedule(is_ev)
    brand_overrides = get_brand_overrides(detect_brand(brand) or brand, is_ev)
    faults = find_faults(detect_brand(brand) or brand, model)

    lines = []
    lines.append("=" * 52)
    lines.append(f"  保养/故障分析报告")
    lines.append("=" * 52)
    lines.append(f"车型: {brand} {model}")
    lines.append(f"类型: {ev_tag}")
    lines.append(f"当前里程: {current_km:,} km")
    if last_km:
        lines.append(f"上次保养里程: {last_km:,} km")
    if purchase_date:
        lines.append(f"购车日期: {purchase_date}")
    lines.append("")

    # ── 保养周期 ──
    lines.append("─" * 52)
    lines.append("  📋 保养周期建议")
    lines.append("─" * 52)
    for item in schedule:
        r = calc_status(current_km, item, last_km)
        marker = "🔴" if r["urgency"] == "high" else "⚠️" if r["urgency"] == "medium" else "✅"
        lines.append(f"  {marker} {r['km']:>6,}km  {r['item']:<30}  {r['status']}")
        if r["notes"]:
            lines.append(f"           💬 {r['notes']}")
    lines.append("")

    # ── 品牌特有项目 ──
    if brand_overrides:
        lines.append("─" * 52)
        lines.append("  🔧 品牌特有保养项目")
        lines.append("─" * 52)
        for k, v in brand_overrides.items():
            km = v.get("km", 0)
            notes = v.get("notes", "")
            lines.append(f"  • {k}  ({km:,}km)  {notes}")
        lines.append("")

    # ── 常见故障 ──
    if faults:
        lines.append("─" * 52)
        lines.append("  🔍 本车型常见故障（知识库）")
        lines.append("─" * 52)
        for f in faults[:6]:
            lines.append(f"  • [{f.get('id','?')}] {f['symptom']}")
            lines.append(f"    原因: {f['root_cause']}")
            if f.get("prevention"):
                lines.append(f"    预防: {f['prevention']}")
            lines.append("")

    lines.append("=" * 52)
    lines.append("  ⚠️  本报告仅供参考，具体以4S店/维修厂检测为准")
    lines.append("=" * 52)
    return "\n".join(lines)

# ═══════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════
if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3:
        print("用法: python3 generate_maintenance_report.py <品牌> <车型> <里程> [上次保养里程] [购车日期]")
        print("示例: python3 generate_maintenance_report.py 比亚迪 汉 25000 15000 2024-06")
        sys.exit(1)
    brand = args[0]
    model = args[1]
    try:
        current_km = int(args[2])
    except ValueError:
        print("里程必须是整数")
        sys.exit(1)
    last_km = int(args[3]) if len(args) > 3 else None
    purchase_date = args[4] if len(args) > 4 else ""
    report = generate_text_report(brand, model, current_km, last_km, purchase_date)
    print(report)
