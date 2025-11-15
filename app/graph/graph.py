"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from app.graph.state import MenuGraphState
from app.graph.nodes import (
    parse_intent_node,
    query_ingredients_node,
    prefilter_ingredients_by_budget_node,
    retrieve_rules_and_generate_menu_node,
    validate_budget_node,
    adjust_menu_node,
    build_response_node
)


def should_adjust_menu(state: MenuGraphState) -> str:
    """Conditional edge: decide whether to adjust menu or build response."""
    needs_adjustment = state.get("needs_adjustment", False)
    needs_enhancement = state.get("needs_enhancement", False)
    iteration_count = state.get("iteration_count", 0)
    max_iterations = 2
    
    if (needs_adjustment or needs_enhancement) and iteration_count < max_iterations:
        action = "enhancing" if needs_enhancement else "reducing"
        print(f"[GRAPH] Routing to adjust_menu ({action}, iteration {iteration_count + 1}/{max_iterations})")
        return "adjust_menu"
    elif (needs_adjustment or needs_enhancement) and iteration_count >= max_iterations:
        # Kiểm tra xem menu có vượt budget không
        menu = state.get("generated_menu", {})
        total_price = menu.get("total_price", 0)
        intent = state.get("intent", {})
        budget = intent.get("budget", 0)
        
        if total_price > budget:
            # Nếu vượt budget, đánh dấu lỗi
            print(f"[GRAPH] Max iterations reached ({max_iterations}), menu still exceeds budget, routing to build_response with error")
            state["error"] = f"Failed to adjust menu after {max_iterations} attempts: Menu exceeds budget"
        else:
            # Nếu < budget, chấp nhận kết quả (không set error)
            print(f"[GRAPH] Max iterations reached ({max_iterations}), accepting result < budget ({total_price:,.0f}/{budget:,.0f} VND)")
            state["budget_error"] = None  # Clear error nếu có
        return "build_response"
    else:
        print("[GRAPH] Budget OK, routing to build_response")
        return "build_response"


def create_menu_graph() -> StateGraph:
    """Create and compile the menu suggestion workflow graph with budget validation loop."""
    workflow = StateGraph(MenuGraphState)
    
    workflow.add_node("parse_intent", parse_intent_node)
    workflow.add_node("query_ingredients", query_ingredients_node)
    workflow.add_node("prefilter_ingredients", prefilter_ingredients_by_budget_node)
    workflow.add_node("retrieve_rules_and_generate_menu", retrieve_rules_and_generate_menu_node)
    workflow.add_node("validate_budget", validate_budget_node)
    workflow.add_node("adjust_menu", adjust_menu_node)
    workflow.add_node("build_response", build_response_node)
    
    workflow.set_entry_point("parse_intent")
    workflow.add_edge("parse_intent", "query_ingredients")
    workflow.add_edge("query_ingredients", "prefilter_ingredients")
    workflow.add_edge("prefilter_ingredients", "retrieve_rules_and_generate_menu")
    workflow.add_edge("retrieve_rules_and_generate_menu", "validate_budget")
    
    workflow.add_conditional_edges(
        "validate_budget",
        should_adjust_menu,
        {
            "adjust_menu": "adjust_menu",
            "build_response": "build_response"
        }
    )
    
    workflow.add_edge("adjust_menu", "validate_budget")
    workflow.add_edge("build_response", END)
    
    app = workflow.compile()
    return app


menu_graph = create_menu_graph()

