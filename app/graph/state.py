"""LangGraph State definition."""
from typing import TypedDict, List, Dict, Any, Optional


class MenuGraphState(TypedDict):
    """State for the menu suggestion workflow."""
    
    # User input
    user_input: str
    
    # User ID for tracking history (optional)
    user_id: Optional[str]
    
    # Previous dishes suggested to this user
    previous_dishes: List[str]
    
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
    
    # Iteration counter for adjustment loop
    iteration_count: int
    
    # Budget validation
    needs_adjustment: Optional[bool]
    needs_enhancement: Optional[bool]
    budget_error: Optional[str]

