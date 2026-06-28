# V111.52 非人格基础融合覆盖包

本覆盖包只处理“非人格视觉”的基础问题，不改人格视觉规则、不改 PersonaVisualController 链路。

## 修复范围

1. no-skills 包兼容：保留无物理 `skills/` 目录，同时提供 `skills.py + infrastructure.no_skills_compat`，让旧导入 `skills.registry / skills.runtime.*` 不再失败。
2. application 根入口兼容：新增 `application -> execution.application` facade，修复旧入口 `application.task_service.scheduler`。
3. 主入口补齐：恢复 `scripts/message_server.py` 安全 facade。
4. 自动化配置补齐：新增 `config/crontab.example`、`config/systemd.example`。
5. 在线连接策略归一：`openclaw.json` 统一为 `online_connected`，关闭 `ZERO_EXTERNAL_MODE/NO_EXTERNAL_API/OFFLINE_MODE`，端侧与小艺能力默认 always connected；真实副作用仍走强确认。
6. 工作流真源补齐：新增 `orchestration/workflows/WORKFLOW_REGISTRY.json`。
7. 路由检查器补齐：`scripts.check_route_registry.RouteRegistryChecker` 支持虚拟 device handler。
8. 技能扫描兼容 no-skills：`core.skill_asset_registry.SkillScanner` 在没有物理 `skills/` 时从逻辑注册表扫描。
9. TaskSpec 反序列化稳态：`sqlite_repo._row_to_task` 改为用 dict 构建嵌套 Pydantic 模型，避免全量测试 import 顺序导致模型身份漂移。
10. V85 provider guard 白名单修正：允许 `core/llm_gateway/` 作为统一模型网关，不误报直接业务调用。

## 覆盖后运行

```bash
python scripts/apply_v111_52_non_persona_foundation_patch.py
python scripts/audit_v111_52_non_persona_foundation.py
pytest -q tests/integration/test_minimum_loop.py tests/integration/test_skill_platform.py tests/integration/test_skill_platform_main_chain.py tests/regression/test_no_regression.py tests/test_automation_scripts.py tests/test_path_unification.py tests/test_route_virtual_device_handler.py tests/test_skill_scan_coverage.py tests/test_v85_model_module_total.py tests/test_v111_46_skills_fusion.py tests/test_v111_52_non_persona_foundation.py -ra
```

## 本地验证结果

- `python scripts/audit_v111_52_non_persona_foundation.py`：OK
- 非人格基础回归集：66 passed, 2 skipped

## 未处理范围

人格视觉相关测试与旧入口封禁不在本包范围内；用户已另行发送人格视觉强制新路径命令。
