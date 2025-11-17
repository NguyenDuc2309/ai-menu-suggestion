"""LangGraph State definition - RAG v2 Pipeline."""
from typing import TypedDict, List, Dict, Any, Optional


class MenuGraphState(TypedDict):
    """State for the RAG v2 menu suggestion workflow."""
    
    # User input
    user_input: str
    
    # User ID for tracking history (optional)
    user_id: Optional[str]
    
    # Previous dishes suggested to this user
    previous_dishes: List[str]
    
    # Parsed intent
    intent: Dict[str, Any]  # {budget, meal_type, num_people, preferences}
    
    # RAG v2: Recipes retrieved from Vector DB (món ăn + nguyên liệu)
    rag_recipes: List[str]  # Recipe documents from Pinecone
    
    # RAG v2: Parsed products với ID làm định danh (no duplicates, no gia vị/gạo/mì)
    available_products: Dict[str, Dict[str, Any]]  # {prod_id: {"id": "...", "name": "...", "price": ...}}
    
    # DEPRECATED: Available ingredients (kept for backward compatibility)
    available_ingredients: List[Dict[str, Any]]
    
    # DEPRECATED: Combination rules (kept for backward compatibility)
    combination_rules: List[str]
    
    # Generated menu
    generated_menu: Dict[str, Any]  # {items: [...], total_price: float}
    
    # Out of stock ingredients (from Step D: fetch_realtime_pricing)
    out_of_stock_ingredients: List[str]
    
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

