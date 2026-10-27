"""LangGraph multi-step agent with breakdown, research, and user approval."""

import os
import json
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from tools import search
from llm import get_llm

# ── State ──────────────────────────────────────────────────────────────────

class MultiStepState(TypedDict):
    query: str
    sub_questions: List[str]
    raw_search: str
    approved: bool
    final_answer: str


# ── LLM ────────────────────────────────────────────────────────────────────

def _llm():
    return get_llm(temperature=0.3)


# ── Nodes ──────────────────────────────────────────────────────────────────

def breakdown(state: MultiStepState) -> dict:
    """Break the query into 3-4 specific sub-questions."""
    prompt = (
        "You are a research planner. Break the following query into 3-4 specific "
        "sub-questions that need to be researched to answer it comprehensively.\n"
        "Return ONLY a JSON array of strings, no other text.\n\n"
        f"Query: {state['query']}"
    )
    resp = _llm().invoke(prompt)
    raw = resp.content.strip()
    # Extract JSON array from the response
    if "[" in raw:
        raw = raw[raw.index("["):raw.rindex("]")+1]
    try:
        questions = json.loads(raw)
    except Exception:
        # Fallback: split by newlines and number prefixes
        questions = [q.strip().lstrip("123456789. ") for q in raw.split("\n") if q.strip()]
    return {"sub_questions": questions[:4]}


def research(state: MultiStepState) -> dict:
    """Search for each sub-question and collect results."""
    chunks = []
    for q in state["sub_questions"]:
        try:
            raw = search.run(q)
            chunks.append(f"── {q} ──\n{raw[:600]}")
        except Exception:
            chunks.append(f"── {q} ──\n(no results)")
    return {"raw_search": "\n\n".join(chunks)}


def synthesize(state: MultiStepState) -> dict:
    """Compile research into a final answer."""
    prompt = (
        "You are a research synthesizer. Based on the following research, "
        "compile a comprehensive answer to the original query.\n"
        "Include specific findings and cite the source topics.\n\n"
        f"Original Query: {state['query']}\n\n"
        f"Research Findings:\n{state['raw_search']}"
    )
    resp = _llm().invoke(prompt)
    return {"final_answer": resp.content}


# ── Conditional edge ───────────────────────────────────────────────────────

def needs_approval(state: MultiStepState) -> str:
    """Route to synthesize if approved, otherwise stay."""
    return "synthesize" if state.get("approved") else "wait"


# ── Build graph ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(MultiStepState)

    graph.add_node("breakdown", breakdown)
    graph.add_node("research", research)
    graph.add_node("synthesize", synthesize)

    graph.set_entry_point("breakdown")
    graph.add_edge("breakdown", "research")
    graph.add_conditional_edges(
        "research",
        needs_approval,
        {"synthesize": "synthesize", "wait": END},
    )
    graph.add_edge("synthesize", END)

    return graph.compile()


# ── Stage runners (used by Flask) ──────────────────────────────────────────

def run_until_approval(query: str) -> MultiStepState:
    """Run breakdown + research, return state ready for user approval."""
    graph = build_graph()
    initial = MultiStepState(
        query=query,
        sub_questions=[],
        raw_search="",
        approved=False,
        final_answer="",
    )
    # Run only breakdown → research (stops at conditional edge)
    state = graph.invoke(initial, {"recursion_limit": 10})
    return state


def run_synthesis(state_data: dict) -> str:
    """Run the synthesize node with the given state and return final answer."""
    state_data["approved"] = True
    # Call synthesize directly
    result = synthesize(state_data)
    return result["final_answer"]
