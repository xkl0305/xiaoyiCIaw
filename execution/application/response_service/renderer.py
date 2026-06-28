#!/usr/bin/env python3
"""响应渲染器 - 将内部结构化结果渲染成可读回答"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .evidence_formatter import EvidenceFormatter, EvidenceType


@dataclass
class RenderedResponse:
    """渲染后的响应"""
    status: str
    summary: str
    completed_items: List[str]
    incomplete_items: List[str]
    evidences: List[Dict[str, Any]]
    next_steps: List[str]
    raw_data: Optional[Dict[str, Any]] = None


class ResponseRenderer:
    """响应渲染器"""

    def __init__(self):
        self.evidence_formatter = EvidenceFormatter()

    def render(
        self,
        execution_trace: List[Dict[str, Any]],
        subtasks: List[Dict[str, Any]],
        results: Dict[str, Any],
        intent: str,
    ) -> RenderedResponse:
        completed = []
        incomplete = []
        has_error = False

        for subtask in subtasks:
            subtask_id = subtask.get('id', '')
            status = subtask.get('status', 'pending')
            skill = subtask.get('skill')
            error = subtask.get('error')

            if status == 'success' and skill:
                completed.append(f'✅ {subtask_id}: {skill}')
            elif status == 'failed':
                has_error = True
                incomplete.append(f"❌ {subtask_id}: {error or '执行失败'}")
            elif status == 'pending':
                incomplete.append(f'⏳ {subtask_id}: 未执行')

        evidences = self._extract_evidences(results, execution_trace)

        if not completed and not incomplete:
            status = 'failed'
        elif has_error and not completed:
            status = 'failed'
        elif incomplete:
            status = 'partial'
        else:
            status = 'success'

        next_steps = self._suggest_next_steps(status, intent, incomplete)
        summary = self._generate_summary(status, intent, completed, incomplete, evidences)

        return RenderedResponse(
            status=status,
            summary=summary,
            completed_items=completed,
            incomplete_items=incomplete,
            evidences=evidences,
            next_steps=next_steps,
            raw_data={'execution_trace': execution_trace, 'results': results},
        )

    def _extract_evidences(self, results: Dict[str, Any], execution_trace: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        evidences = []
        for task_id, result in results.items():
            if not isinstance(result, dict):
                continue
            if 'file_path' in result or 'output_file' in result:
                path = result.get('file_path') or result.get('output_file')
                evidences.append({'type': 'file', 'description': f'文件: {path}', 'verified': True, 'value': path})
            if 'record_id' in result or 'task_id' in result:
                record_id = result.get('record_id') or result.get('task_id')
                evidences.append({'type': 'db_record', 'description': f'记录ID: {record_id}', 'verified': True, 'value': record_id})
            if 'message_id' in result:
                evidences.append({'type': 'message', 'description': f"消息ID: {result['message_id']}", 'verified': True, 'value': result['message_id']})
            if 'content' in result or 'text' in result:
                content = result.get('content') or result.get('text', '')
                evidences.append({'type': 'content', 'description': f'生成内容: {len(content)}字', 'verified': len(content) > 0, 'value': content[:200] if content else None})
        if execution_trace:
            evidences.append({'type': 'trace', 'description': f'执行轨迹: {len(execution_trace)}步', 'verified': True, 'value': execution_trace})
        return evidences

    def _generate_summary(self, status: str, intent: str, completed: List[str], incomplete: List[str], evidences: List[Dict[str, Any]]) -> str:
        lines = []
        if status == 'success':
            lines.append(f'✅ {intent} 完成')
        elif status == 'partial':
            lines.append(f'⚠️ {intent} 部分完成')
        else:
            lines.append(f'❌ {intent} 失败')

        if completed:
            lines.append(f'\n【完成项】({len(completed)})')
            for item in completed:
                lines.append(f'  {item}')

        if incomplete:
            lines.append(f'\n【未完成项】({len(incomplete)})')
            for item in incomplete:
                lines.append(f'  {item}')

        verified_evidences = [e for e in evidences if e.get('verified')]
        if verified_evidences:
            lines.append(f'\n【证据】({len(verified_evidences)})')
            for e in verified_evidences:
                lines.append(f"  - {e['description']}")
        return '\n'.join(lines)

    def _suggest_next_steps(self, status: str, intent: str, incomplete: List[str]) -> List[str]:
        steps = []
        if status == 'failed':
            steps.append('检查错误信息，确认失败原因')
            steps.append('修正后重试')
        elif status == 'partial':
            steps.append('检查未完成项')
            for item in incomplete:
                if '未执行' in item:
                    steps.append(f'执行: {item}')
        else:
            steps.append('任务已完成，可以进行下一步操作')
        return steps

    def to_dict(self, response: RenderedResponse) -> Dict[str, Any]:
        return {
            'status': response.status,
            'summary': response.summary,
            'completed_items': response.completed_items,
            'incomplete_items': response.incomplete_items,
            'evidences': response.evidences,
            'next_steps': response.next_steps,
        }

    def to_user_message(self, response: RenderedResponse) -> str:
        from infrastructure.persona_visual_reply_outlet import finalize_visible_reply
        return finalize_visible_reply(response.summary, source='ResponseRenderer.to_user_message')
