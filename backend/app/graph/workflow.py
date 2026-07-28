from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import AnswerNode, PlannerNode, ReviewerNode, ToolNode
from app.graph.state import GraphState


def build_agent_graph(*, llm, registry):
    graph = StateGraph(GraphState)

    graph.add_node('planner', PlannerNode(llm))
    graph.add_node('tool', ToolNode(registry))
    graph.add_node('reviewer', ReviewerNode(llm))
    graph.add_node('answer', AnswerNode(llm))

    graph.add_edge(START, 'planner')
    graph.add_edge('planner', 'tool')
    graph.add_edge('tool', 'reviewer')
    graph.add_edge('reviewer', 'answer')
    graph.add_edge('answer', END)

    return graph.compile()
