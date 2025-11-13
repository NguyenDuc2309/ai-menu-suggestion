"""LangGraph conditional edges and routing logic."""
from app.graph.state import MenuGraphState


def route_after_validate(state: MenuGraphState) -> str:
    """
    Route after validation node.
    
    Returns:
        "adjust_menu" if validation failed
        "build_response" if validation passed
    """
    # Check for errors first - if error exists, stop workflow
    if state.get("error"):
        print("[ROUTE] Error detected in state, routing to build_response to end workflow")
        return "build_response"
    
    validation_result = state.get("validation_result", {})
    quantity_valid = validation_result.get("quantity_valid", False)
    price_valid = validation_result.get("price_valid", False)
    
    # If both validations pass, proceed to build response
    if quantity_valid and price_valid:
        return "build_response"
    
    # Otherwise, adjust menu
    return "adjust_menu"

