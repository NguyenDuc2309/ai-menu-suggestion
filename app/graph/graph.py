"""LangGraph workflow definition."""
from langgraph.graph import StateGraph, END
from app.graph.state import MenuGraphState
from app.graph.nodes import (
    parse_intent_node,
    query_ingredients_node,
    retrieve_rules_and_generate_menu_node,
    build_response_node
)


def create_menu_graph() -> StateGraph:
    """Create and compile the menu suggestion workflow graph."""
    
    # Create graph
    workflow = StateGraph(MenuGraphState)
    
    # Add nodes
    workflow.add_node("parse_intent", parse_intent_node)
    workflow.add_node("query_ingredients", query_ingredients_node)
    workflow.add_node("retrieve_rules_and_generate_menu", retrieve_rules_and_generate_menu_node)
    workflow.add_node("build_response", build_response_node)
    
    # Define edges - simplified flow without validation loop
    workflow.set_entry_point("parse_intent")
    workflow.add_edge("parse_intent", "query_ingredients")
    workflow.add_edge("query_ingredients", "retrieve_rules_and_generate_menu")
    workflow.add_edge("retrieve_rules_and_generate_menu", "build_response")
    
    # After build_response, end
    workflow.add_edge("build_response", END)
    
    # Compile graph
    app = workflow.compile()
    
    return app


# Create compiled graph instance
menu_graph = create_menu_graph()

