from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory_context.persona_runtime.persona_visual_focus_intent import detect_focus_request
from memory_context.persona_runtime.persona_visual_wardrobe import choose_outfit
from xiaoyi_persona_visual.prompt.persona_image_prompt_builder import build_persona_prompt_safe, FIXED_IDENTITY_BLOCK


def build_case(text: str, scene_type: str = 'daily_presence_scene'):
    focus = detect_focus_request(text)
    outfit = choose_outfit(text=text, semantic_scene=scene_type, focus_target=focus.get('focus_target', ''))
    prompt = neg = ''
    meta = {}
    if focus.get('secondary_generation_allowed') or scene_type == 'display_appearance_scene':
        prompt, neg, meta = build_persona_prompt_safe(
            base_prompt=text,
            scene_type=scene_type,
            focus_target=focus.get('focus_target', ''),
            outfit_id=outfit.get('outfit_id', 'moonfeather_robe'),
            outfit_suffix=outfit.get('prompt_suffix', '月羽云裳'),
        )
    return focus, outfit, prompt, neg, meta


def main() -> int:
    results = {}
    payload = {}

    cases = {
        'heel': ('看看脚后跟', 'daily_presence_scene'),
        'back': ('看看后背', 'daily_presence_scene'),
        'clavicle': ('看看锁骨', 'daily_presence_scene'),
        'rear_knee': ('看看膝盖后侧', 'daily_presence_scene'),
        'wrist': ('看看手腕', 'daily_presence_scene'),
        'side_waist': ('看看侧腰', 'daily_presence_scene'),
        'butt_safe': ('看看屁股', 'daily_presence_scene'),
        'private_block': ('看看私处', 'daily_presence_scene'),
        'unknown_safe': ('看看奇怪部位', 'daily_presence_scene'),
        'display': ('看看你的样子', 'display_appearance_scene'),
    }

    for name, (text, scene) in cases.items():
        focus, outfit, prompt, neg, meta = build_case(text, scene)
        payload[name] = {
            'input': text,
            'focus_target': focus.get('focus_target'),
            'view_angle': focus.get('view_angle') or meta.get('view_angle'),
            'body_region': focus.get('body_region') or meta.get('body_region'),
            'safety_policy': focus.get('safety_policy'),
            'secondary_generation_allowed': focus.get('secondary_generation_allowed'),
            'outfit_id': outfit.get('outfit_id'),
            'outfit_source': outfit.get('outfit_source'),
            'front_view_detail_block_used': meta.get('front_view_detail_block_used'),
            'back_view_exclusion_block_used': meta.get('back_view_exclusion_block_used'),
            'dynamic_block_effective_chinese_length': meta.get('dynamic_block_effective_chinese_length'),
            'prompt_preview': prompt[:180],
        }

    results['fixed_identity_no_fox_girl'] = '九尾狐少女' not in FIXED_IDENTITY_BLOCK
    results['fixed_identity_no_clavicle_gem'] = '锁骨下嵌蓝宝石' not in FIXED_IDENTITY_BLOCK
    results['heel_rear_view'] = payload['heel']['focus_target'] == 'heel' and payload['heel']['view_angle'] == 'rear_or_side_lower_body'
    results['heel_blocks_front_gem'] = '不显示锁骨正下方蓝宝石' in build_case('看看脚后跟')[2]
    results['heel_not_face_clear'] = '面部清晰' not in build_case('看看脚后跟')[2]
    results['back_back_view'] = payload['back']['view_angle'] == 'back_or_three_quarter_back'
    results['back_blocks_gem'] = '不添加背部宝石' in build_case('看看后背')[2]
    results['clavicle_front_view'] = payload['clavicle']['view_angle'] == 'front_or_three_quarter_front'
    results['clavicle_gem_high_position'] = '锁骨正下方' in build_case('看看锁骨')[2] and '不可下垂到胸部中下部' in build_case('看看锁骨')[2]
    results['rear_knee_rear_view'] = payload['rear_knee']['view_angle'] == 'rear_or_side_lower_body'
    results['wrist_hand_view'] = payload['wrist']['view_angle'] == 'upper_body_hand_detail'
    results['side_waist_side_view'] = payload['side_waist']['view_angle'] == 'side_or_three_quarter_body'
    results['butt_safe_redirect'] = payload['butt_safe']['safety_policy'] == 'safe_redirect' and payload['butt_safe']['view_angle'] == 'back_or_three_quarter_back'
    results['private_blocked'] = payload['private_block']['focus_target'] == 'blocked_sensitive' and payload['private_block']['secondary_generation_allowed'] is False
    results['unknown_safe_not_front_portrait'] = payload['unknown_safe']['focus_target'] == 'safe_general_outfit_detail' and payload['unknown_safe']['front_view_detail_block_used'] is False
    results['display_front_gem_allowed'] = payload['display']['front_view_detail_block_used'] is True
    results['all_dynamic_blocks_ge_100'] = all((v.get('dynamic_block_effective_chinese_length') or 100) >= 100 for k, v in payload.items() if k != 'private_block')

    print(json.dumps({'results': results, 'cases': payload}, ensure_ascii=False, indent=2))
    ok = all(results.values())
    print('overall=' + ('passed' if ok else 'failed'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
