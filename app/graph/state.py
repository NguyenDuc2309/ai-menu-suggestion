"""LangGraph State definition."""
from typing import TypedDict, List, Dict, Any, Optional


class MenuGraphState(TypedDict):
    """State for the menu suggestion workflow."""
    
    # User input
    user_input: str
    
    # Parsed intent
    intent: Dict[str, Any]  # {cuisine, budget, preferences}
    
    # Available ingredients from database (mock)
    available_ingredients: List[Dict[str, Any]]  # [{name, quantity, price, unit}]
    
    # Ingredient combination rules retrieved from Pinecone
    combination_rules: List[str]
    
    # Generated menu
    generated_menu: Dict[str, Any]  # {items: [...], total_price: float}
    
    # Final response
    final_response: Optional[Dict[str, Any]]
    
    # Error handling
    error: Optional[str]
    
    # Iteration counter (kept for compatibility, not used in simplified flow)
    iteration_count: int
    
    # LLM usage tracking
    llm_usage: Optional[List[Dict[str, Any]]]

