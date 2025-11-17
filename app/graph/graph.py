"""LangGraph workflow definition - RAG v2 Pipeline."""

from langgraph.graph import StateGraph, END

from app.graph.state import MenuGraphState
from app.graph.nodes_refactored import (
    parseIntent,
    queryAndGenerate,
    fetchPricing,
    validateBudget,
    adjustMenu,
    buildResponse,
)


def should_adjust_menu(state: MenuGraphState) -> str:
    """Decide whether to adjust menu or build response."""
    needs_adjustment = state.get("needs_adjustment", False)
    needs_enhancement = state.get("needs_enhancement", False)
    iteration_count = state.get("iteration_count", 0)
    max_iterations = 2

    if (needs_adjustment or needs_enhancement) and iteration_count < max_iterations:
        action = "enhancing" if needs_enhancement else "reducing"
        print(
            f"[GRAPH] Routing to adjust_menu ({action}, iteration {iteration_count + 1}/{max_iterations})"
        )
        return "adjust_menu"

    if (needs_adjustment or needs_enhancement) and iteration_count >= max_iterations:
        menu = state.get("generated_menu", {})
        total_price = menu.get("total_price", 0)
        intent = state.get("intent", {})
        budget = intent.get("budget", 0)

        if total_price > budget:
            print(
                f"[GRAPH] Max iterations reached ({max_iterations}), menu still exceeds budget, routing to build_response with error"
            )
            state[
                "error"
            ] = f"Failed to adjust menu after {max_iterations} attempts: Menu exceeds budget"
        else:
            print(
                f"[GRAPH] Max iterations reached ({max_iterations}), accepting result < budget ({total_price:,.0f}/{budget:,.0f} VND)"
            )
            state["budget_error"] = None
        return "build_response"

    print("[GRAPH] Budget OK, routing to build_response")
    return "build_response"


def create_menu_graph() -> StateGraph:
    """Create RAG v2 pipeline graph."""
    workflow = StateGraph(MenuGraphState)

    # Nodes
    workflow.add_node("parseIntent", parseIntent)
    workflow.add_node("queryAndGenerate", queryAndGenerate)
    workflow.add_node("fetchPricing", fetchPricing)
    workflow.add_node("validateBudget", validateBudget)
    workflow.add_node("adjustMenu", adjustMenu)
    workflow.add_node("buildResponse", buildResponse)

    # Entry
    workflow.set_entry_point("parseIntent")

    # Linear flow
    workflow.add_edge("parseIntent", "queryAndGenerate")
    workflow.add_edge("queryAndGenerate", "fetchPricing")
    workflow.add_edge("fetchPricing", "validateBudget")

    # Adjustment loop
    workflow.add_conditional_edges(
        "validateBudget",
        should_adjust_menu,
        {"adjust_menu": "adjustMenu", "build_response": "buildResponse"},
    )
    workflow.add_edge("adjustMenu", "fetchPricing")

    # End
    workflow.add_edge("buildResponse", END)

    return workflow.compile()


menu_graph = create_menu_graph()
