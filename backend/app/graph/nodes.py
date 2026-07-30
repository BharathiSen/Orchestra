from __future__ import annotations

import re
from typing import Any

from app.graph.state import GraphState
from app.prompts.system import graph_reviewer_prompt


class PlannerNode:
    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: GraphState) -> GraphState:
        # Heuristic guardrail: for generic writing/explanation prompts,
        # skip tools to avoid low-value search calls.
        if not self._should_use_tools(state):
            summary = 'No tools needed; direct answer path.'
            return {
                'llm_messages': list(state['llm_messages']),
                'plan_text': '',
                'tool_calls': [],
                'graph_events': [
                    {'node': 'planner', 'status': 'done', 'summary': summary}
                ],
            }

        result = self.llm.complete_chat(
            messages=state['llm_messages'],
            model=state['model'],
            temperature=state['temperature'],
            tools=state.get('tools') if state.get('enable_tools') else None,
            tool_choice='auto',
        )

        tool_calls: list[dict[str, Any]] = []
        for tc in result.tool_calls:
            tool_calls.append(
                {
                    'id': tc.id,
                    'name': tc.name,
                    'arguments': tc.arguments,
                }
            )

        assistant_msg: dict[str, Any] = {
            'role': 'assistant',
            'content': result.content,
        }
        if tool_calls:
            assistant_msg['tool_calls'] = [
                {
                    'id': call['id'],
                    'type': 'function',
                    'function': {
                        'name': call['name'],
                        'arguments': call['arguments'],
                    },
                }
                for call in tool_calls
            ]

        next_messages = list(state['llm_messages'])
        next_messages.append(assistant_msg)

        summary = (
            f"Planned {len(tool_calls)} tool call(s)."
            if tool_calls
            else 'No tools needed; direct answer path.'
        )

        return {
            'llm_messages': next_messages,
            'plan_text': result.content or '',
            'tool_calls': tool_calls,
            'graph_events': [
                {'node': 'planner', 'status': 'done', 'summary': summary}
            ],
        }

    def _should_use_tools(self, state: GraphState) -> bool:
        if not state.get('enable_tools'):
            return False

        last_user = ''
        for msg in reversed(state.get('llm_messages') or []):
            if msg.get('role') == 'user':
                last_user = str(msg.get('content') or '').strip().lower()
                break
        if not last_user:
            return False

        # Strong tool intent
        if re.search(r'\b(weather|temperature|forecast|rain|humidity)\b', last_user):
            return True
        if re.search(r'\b(search|find|look up|lookup)\b', last_user):
            return True
        if re.search(r'[\d\)\(]+\s*[\+\-\*/%]\s*[\d\)\(]+', last_user):
            return True
        if re.search(r'\b(calculate|math|sum|multiply|divide|subtract)\b', last_user):
            return True

        # Generic writing/explanation prompts: better direct LLM answer
        if re.search(r'\b(write|explain|describe|summari[sz]e|tell me)\b', last_user):
            return False

        return False


class ToolNode:
    def __init__(self, registry: Any, max_tool_calls: int = 3) -> None:
        self.registry = registry
        self.max_tool_calls = max_tool_calls

    def __call__(self, state: GraphState) -> GraphState:
        if not state.get('enable_tools'):
            return {
                'graph_events': [
                    {
                        'node': 'tool',
                        'status': 'done',
                        'summary': 'Tools disabled for this request.',
                    }
                ]
            }

        calls = list(state.get('tool_calls') or [])[: self.max_tool_calls]
        if not calls:
            return {
                'graph_events': [
                    {
                        'node': 'tool',
                        'status': 'done',
                        'summary': 'Planner requested no tools.',
                    }
                ]
            }

        tool_events: list[dict[str, Any]] = []
        next_messages = list(state['llm_messages'])
        completed = 0

        for call in calls:
            start_evt = {
                'type': 'tool_start',
                'tool_call_id': call['id'],
                'tool_name': call['name'],
                'arguments': call['arguments'],
                'status': 'running',
            }
            tool_events.append(start_evt)

            try:
                output = self.registry.execute(call['name'], call['arguments'])
                status = 'complete'
            except Exception as exc:  # noqa: BLE001
                output = f'Tool execution failed: {exc}'
                status = 'error'

            result_evt = {
                'type': 'tool_result',
                'tool_call_id': call['id'],
                'tool_name': call['name'],
                'status': status,
                'result': str(output),
            }
            tool_events.append(result_evt)

            next_messages.append(
                {
                    'role': 'tool',
                    'tool_call_id': call['id'],
                    'name': call['name'],
                    'content': str(output),
                }
            )
            completed += 1

        return {
            'llm_messages': next_messages,
            'tool_events': tool_events,
            'graph_events': [
                {
                    'node': 'tool',
                    'status': 'done',
                    'summary': f'Executed {completed} tool call(s).',
                }
            ],
        }


class ReviewerNode:
    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: GraphState) -> GraphState:
        tool_results = [
            evt
            for evt in (state.get('tool_events') or [])
            if evt.get('type') == 'tool_result'
        ]
        if not tool_results:
            return {
                'review_notes': 'No tool outputs to review.',
                'graph_events': [
                    {'node': 'reviewer', 'status': 'done', 'summary': 'Skipped (no tools).'}
                ],
            }

        prompt = (
            'Review the following tool outputs for clarity and obvious issues. '
            'Return 2-4 short bullet points with caution notes if needed.\n\n'
            f"Tool outputs:\n{tool_results}"
        )
        review_messages = [
            {
                'role': 'system',
                'content': graph_reviewer_prompt(),
            },
            {'role': 'user', 'content': prompt},
        ]
        review = self.llm.complete_chat(
            messages=review_messages,
            model=state['model'],
            temperature=0.1,
            tools=None,
            tool_choice=None,
        )

        notes = (review.content or '').strip() or 'Reviewer found no issues.'
        return {
            'review_notes': notes,
            'graph_events': [
                {'node': 'reviewer', 'status': 'done', 'summary': 'Reviewed tool outputs.'}
            ],
        }


class AnswerNode:
    def __init__(self, llm: Any) -> None:
        self.llm = llm

    def __call__(self, state: GraphState) -> GraphState:
        tool_results = [
            evt
            for evt in (state.get('tool_events') or [])
            if evt.get('type') == 'tool_result'
        ]

        context_lines = []
        if tool_results:
            context_lines.append('Tool results:')
            for tr in tool_results:
                context_lines.append(
                    f"- {tr.get('tool_name')}: {tr.get('result')}"
                )
        if state.get('review_notes'):
            context_lines.append('Reviewer notes:')
            context_lines.append(str(state['review_notes']))

        no_hits = self._all_search_results_empty(tool_results)

        if context_lines:
            answer_messages = list(state['llm_messages']) + [
                {
                    'role': 'user',
                    'content': (
                        'Using the tool outputs below, produce the final user-facing answer.\n'
                        'If search results are empty or weak, still answer from general engineering knowledge '
                        'instead of refusing.\n\n'
                        + '\n'.join(context_lines)
                    ),
                }
            ]
            result = self.llm.complete_chat(
                messages=answer_messages,
                model=state['model'],
                temperature=state['temperature'],
                tools=None,
                tool_choice=None,
            )
            final = (result.content or '').strip()
        else:
            # Fallback for direct-answer path
            result = self.llm.complete_chat(
                messages=state['llm_messages'],
                model=state['model'],
                temperature=state['temperature'],
                tools=None,
                tool_choice=None,
            )
            final = (result.content or '').strip()

        # Safety fallback for empty-search refusal style responses.
        if no_hits and self._looks_like_refusal(final):
            direct_result = self.llm.complete_chat(
                messages=list(state['llm_messages']),
                model=state['model'],
                temperature=state['temperature'],
                tools=None,
                tool_choice=None,
            )
            final = (direct_result.content or '').strip() or final

        if not final:
            final = '(No content returned by the model.)'

        return {
            'final_answer': final,
            'graph_events': [
                {'node': 'answer', 'status': 'done', 'summary': 'Generated final answer.'}
            ],
        }

    def _all_search_results_empty(self, tool_results: list[dict[str, Any]]) -> bool:
        search_results = [
            str(evt.get('result') or '')
            for evt in tool_results
            if evt.get('tool_name') == 'search'
        ]
        if not search_results:
            return False
        return all('No knowledge hits' in text for text in search_results)

    def _looks_like_refusal(self, text: str) -> bool:
        lowered = (text or '').lower()
        triggers = [
            'did not provide any relevant information',
            'if you could provide more context',
            'did not provide any relevant',
            'try searching for related terms',
        ]
        return any(t in lowered for t in triggers)
