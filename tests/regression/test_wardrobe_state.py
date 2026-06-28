from __future__ import annotations

def test_wardrobe_state_module_present():
    from xiaoyi_persona_visual.wardrobe.wardrobe_loader import choose_outfit
    r=choose_outfit(text='看看你的样子', semantic_scene='display_appearance_scene')
    assert r.get('outfit_id')
