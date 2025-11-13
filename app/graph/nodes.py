"""LangGraph nodes implementation."""
import json
import os
import random
from typing import Dict, Any
from app.graph.state import MenuGraphState
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store_service


def parse_intent_node(state: MenuGraphState) -> MenuGraphState:
    """Parse user input to extract intent."""
    print("[STEP] parse_intent: Starting...")
    try:
        llm_service = get_llm_service()
        intent = llm_service.parse_intent(state["user_input"])
        state["intent"] = intent
        state["iteration_count"] = 0
        print(f"[STEP] parse_intent: Success - meal_type={intent.get('meal_type')}, budget={intent.get('budget')}")
    except Exception as e:
        error_msg = f"Error parsing intent: {str(e)}"
        print(f"[STEP] parse_intent: FAILED - {error_msg}")
        # Check if it's a critical error (quota, API key, JSON parsing, etc.) - raise to stop workflow
        error_str = str(e).lower()
        if "quota" in error_str or "429" in error_str or "resourceexhausted" in error_str:
            print("[STEP] parse_intent: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API quota exceeded: {str(e)}")
        if "api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or "401" in error_str:
            print("[STEP] parse_intent: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API key error: {str(e)}")
        if "failed to parse intent" in error_str or "invalid json" in error_str or "jsondecodeerror" in error_str:
            print("[STEP] parse_intent: Critical error detected (JSON parsing failed), raising exception to stop workflow")
            raise ValueError(f"Failed to parse intent: LLM returned invalid response. {str(e)}")
        # For non-critical errors, set error in state
        state["error"] = error_msg
        state["intent"] = {
            "budget": 200000,
            "meal_type": "trưa",
            "num_people": 1,
            "preferences": []
        }
        state["iteration_count"] = 0
    return state


def query_ingredients_node(state: MenuGraphState) -> MenuGraphState:
    """Query database (mock) to get available ingredients from JSON file."""
    print("[STEP] query_ingredients: Starting...")
    # Check for errors from previous steps
    if state.get("error"):
        print("[STEP] query_ingredients: Error detected in state, skipping")
        return state
    
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(
            current_dir, 
            "..", 
            "data", 
            "mock_ingredients.json"
        )
        
        with open(json_path, "r", encoding="utf-8") as f:
            mock_ingredients = json.load(f)
        
        state["available_ingredients"] = mock_ingredients
        print(f"[STEP] query_ingredients: Success - loaded {len(mock_ingredients)} ingredients")
    except FileNotFoundError as e:
        error_msg = "Mock ingredients file not found"
        print(f"[STEP] query_ingredients: FAILED - {error_msg}")
        state["error"] = error_msg
        state["available_ingredients"] = []
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing JSON: {str(e)}"
        print(f"[STEP] query_ingredients: FAILED - {error_msg}")
        state["error"] = error_msg
        state["available_ingredients"] = []
    except Exception as e:
        error_msg = f"Error querying ingredients: {str(e)}"
        print(f"[STEP] query_ingredients: FAILED - {error_msg}")
        state["error"] = error_msg
        state["available_ingredients"] = []
    return state


def prefilter_ingredients_by_budget_node(state: MenuGraphState) -> MenuGraphState:
    """Filter ingredients: Remove condiments and filter based on budget."""
    print("[STEP] prefilter_ingredients: Starting...")
    # Check for errors from previous steps
    if state.get("error"):
        print("[STEP] prefilter_ingredients: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget", 200000)
        all_ingredients = state.get("available_ingredients", [])
        
        # CRITICAL: Remove condiments/spices (people already have them at home)
        EXCLUDED_CONDIMENTS = {
            "muối", "đường", "dầu ăn", "xì dầu", "nước mắm", "tỏi", "ớt", 
            "hạt nêm", "bột ngọt", "tiêu", "mắm tôm", "giấm", "mật ong",
            "tương ớt", "tương đen", "dầu hào", "nước tương", "mè", "vừng",
            "bột canh", "hành tím", "gừng", "sả", "lá chanh", "rau mùi tàu",
            "hành lá", "ngò", "rau mùi", "ngò gai"  # herbs people usually have
        }
        
        # Filter out condiments first
        non_condiment_ingredients = [
            ing for ing in all_ingredients 
            if ing["name"].lower() not in EXCLUDED_CONDIMENTS
        ]
        
        print(f"[STEP] prefilter_ingredients: Removed condiments - from {len(all_ingredients)} to {len(non_condiment_ingredients)} ingredients")
        
        # Sort by base_price (cheapest first)
        sorted_ingredients = sorted(non_condiment_ingredients, key=lambda x: x.get("base_price", 0))
        
        # Budget-based filtering strategy
        if budget < 150000:
            # Very tight budget: only cheap ingredients
            max_base_price = 200  # Max 200 VND per unit
            print(f"[STEP] prefilter_ingredients: Tight budget ({budget} VND), filtering for base_price <= {max_base_price}")
        elif budget < 500000:
            # Medium budget: cheap to medium ingredients
            max_base_price = 500
            print(f"[STEP] prefilter_ingredients: Medium budget ({budget} VND), filtering for base_price <= {max_base_price}")
        else:
            # Large budget: all ingredients
            max_base_price = float('inf')
            print(f"[STEP] prefilter_ingredients: Large budget ({budget} VND), using all ingredients")
        
        # Filter by budget
        filtered = []
        
        # Prioritize main ingredients (proteins, vegetables, starches)
        # But exclude "gia vị" category since we already filtered condiments
        for ing in sorted_ingredients:
            if ing.get("base_price", 0) <= max_base_price:
                filtered.append(ing)
        
        # Limit to top 50 ingredients to reduce context size
        filtered = filtered[:50]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_filtered = []
        for ing in filtered:
            if ing["name"] not in seen:
                seen.add(ing["name"])
                unique_filtered.append(ing)
        
        # CRITICAL: Shuffle ingredients to prevent LLM token bias
        # This ensures different dishes are suggested each time
        random.shuffle(unique_filtered)
        
        state["available_ingredients"] = unique_filtered
        print(f"[STEP] prefilter_ingredients: Success - final list has {len(unique_filtered)} main ingredients (condiments excluded, shuffled for diversity)")
        
    except Exception as e:
        error_msg = f"Error prefiltering ingredients: {str(e)}"
        print(f"[STEP] prefilter_ingredients: FAILED - {error_msg}")
        state["error"] = error_msg
    return state


def retrieve_rules_and_generate_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Retrieve ingredient combination rules from Pinecone and generate menu."""
    print("[STEP] retrieve_rules_and_generate_menu: Starting...")
    # Check for errors from previous steps
    if state.get("error"):
        print("[STEP] retrieve_rules_and_generate_menu: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget", 200000)
        meal_type = intent.get("meal_type", "trưa")
        num_people = intent.get("num_people", 1)
        
        ingredients = state.get("available_ingredients", [])
        ingredient_names = [ing["name"] for ing in ingredients]
        
        print(f"[STEP] retrieve_rules_and_generate_menu: Querying Pinecone for combination rules (meal_type: {meal_type})...")
        vector_store = get_vector_store_service()
        combination_rules = vector_store.query_combination_rules(
            meal_type=meal_type,
            ingredients=ingredient_names,
            top_k=5
        )
        state["combination_rules"] = combination_rules
        print(f"[STEP] retrieve_rules_and_generate_menu: Pinecone returned {len(combination_rules)} combination rules")
        
        print(f"[STEP] retrieve_rules_and_generate_menu: Generating menu with LLM using combination rules...")
        llm_service = get_llm_service()
        
        # Get previous dishes for diversity
        previous_dishes = state.get("previous_dishes", [])
        if previous_dishes:
            print(f"[STEP] retrieve_rules_and_generate_menu: User has {len(previous_dishes)} previous dishes, will avoid repeating them")
        
        # Check if budget was specified by user
        budget_specified = intent.get("budget_specified", True)
        print(f"[STEP] retrieve_rules_and_generate_menu: Budget specified by user: {budget_specified}")
        
        menu = llm_service.generate_menu(
            ingredients=ingredients,
            context=combination_rules,
            meal_type=meal_type,
            num_people=num_people,
            budget=budget,
            previous_dishes=previous_dishes,
            budget_specified=budget_specified
        )
        state["generated_menu"] = menu
        
        menu_items_count = len(menu.get("items", []))
        print(f"[STEP] retrieve_rules_and_generate_menu: Success - generated {menu_items_count} menu items")
        
    except Exception as e:
        error_msg = str(e)
        error_str = error_msg.lower()
        print(f"[STEP] retrieve_rules_and_generate_menu: FAILED - Exception type: {type(e).__name__}, Message: {error_msg}")
        import traceback
        print(f"[STEP] retrieve_rules_and_generate_menu: Traceback: {traceback.format_exc()}")
        
        # Check if it's a critical error (quota, API key, JSON parsing, etc.) - raise to stop workflow
        if "quota" in error_str or "429" in error_str or "resourceexhausted" in error_str:
            print("[STEP] retrieve_rules_and_generate_menu: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API quota exceeded: {error_msg}")
        if "api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or "401" in error_str:
            print("[STEP] retrieve_rules_and_generate_menu: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API key error: {error_msg}")
        if "failed to generate menu" in error_str or "invalid json" in error_str or "jsondecodeerror" in error_str or "missing required key" in error_str or "keyerror" in error_str:
            print("[STEP] retrieve_rules_and_generate_menu: Critical error detected (JSON parsing/structure failed), raising exception to stop workflow")
            raise ValueError(f"Failed to generate menu: LLM returned invalid response. {error_msg}")
        # For non-critical errors, set error in state
        state["error"] = f"Error generating menu: {error_msg}"
        state["combination_rules"] = []
        state["generated_menu"] = {"items": [], "total_price": 0}
    return state


def validate_budget_node(state: MenuGraphState) -> MenuGraphState:
    """Validate that generated menu is within budget."""
    print("[STEP] validate_budget: Starting...")
    # Check for errors from previous steps
    if state.get("error"):
        print("[STEP] validate_budget: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget", 200000)
        menu = state.get("generated_menu", {})
        available_ingredients = state.get("available_ingredients", [])
        
        # Create ingredient map for price lookup
        ingredient_map = {ing["name"].lower(): ing for ing in available_ingredients}
        
        # Recalculate total price to verify
        total_price = 0
        for item in menu.get("items", []):
            dish_price = 0
            for ing in item.get("ingredients", []):
                ing_name_lower = ing["name"].lower()
                if ing_name_lower in ingredient_map:
                    base_price = ingredient_map[ing_name_lower]["base_price"]
                    ing_quantity = ing.get("quantity", 0)
                    ingredient_cost = base_price * ing_quantity
                    dish_price += ingredient_cost
                else:
                    # Use LLM provided price if ingredient not found
                    dish_price += ing.get("price", 0)
            total_price += dish_price
        
        # Allow 5% tolerance
        budget_tolerance = budget * 1.05
        
        if total_price > budget_tolerance:
            state["needs_adjustment"] = True
            state["budget_error"] = f"Menu total ({total_price:,.0f} VND) exceeds budget ({budget:,.0f} VND) by {total_price - budget:,.0f} VND"
            print(f"[STEP] validate_budget: FAILED - {state['budget_error']}")
        else:
            state["needs_adjustment"] = False
            state["budget_error"] = None
            print(f"[STEP] validate_budget: Success - total {total_price:,.0f} VND <= budget {budget:,.0f} VND")
        
        # Update menu with recalculated price
        menu["total_price"] = total_price
        state["generated_menu"] = menu
        
    except Exception as e:
        error_msg = f"Error validating budget: {str(e)}"
        print(f"[STEP] validate_budget: FAILED - {error_msg}")
        state["error"] = error_msg
    return state


def adjust_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Adjust menu to fit within budget using LLM."""
    print("[STEP] adjust_menu: Starting...")
    # Check for errors from previous steps
    if state.get("error"):
        print("[STEP] adjust_menu: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget", 200000)
        menu = state.get("generated_menu", {})
        available_ingredients = state.get("available_ingredients", [])
        budget_error = state.get("budget_error", "Menu exceeds budget")
        
        # Increment iteration counter
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        iteration = state["iteration_count"]
        
        print(f"[STEP] adjust_menu: Iteration {iteration}, attempting to adjust menu within budget {budget:,.0f} VND")
        
        # Call LLM to adjust menu
        llm_service = get_llm_service()
        adjusted_menu = llm_service.adjust_menu(
            menu=menu,
            validation_errors=[budget_error],
            available_ingredients=available_ingredients,
            budget=budget
        )
        
        state["generated_menu"] = adjusted_menu
        
        menu_items_count = len(adjusted_menu.get("items", []))
        print(f"[STEP] adjust_menu: Success - adjusted menu has {menu_items_count} items")
        
    except Exception as e:
        error_msg = f"Error adjusting menu: {str(e)}"
        print(f"[STEP] adjust_menu: FAILED - {error_msg}")
        state["error"] = error_msg
    return state


def build_response_node(state: MenuGraphState) -> MenuGraphState:
    """Build final response."""
    print("[STEP] build_response: Starting...")
    try:
        menu = state.get("generated_menu", {})
        intent = state.get("intent", {})
        budget = intent.get("budget", 200000)
        meal_type = intent.get("meal_type", "trưa")
        
        response = {
            "menu_items": menu.get("items", []),
            "total_price": menu.get("total_price", 0),
            "budget": budget,
            "meal_type": meal_type
        }
        
        state["final_response"] = response
        print(f"[STEP] build_response: Success - built response with {len(response['menu_items'])} items")
        
    except Exception as e:
        error_msg = f"Error building response: {str(e)}"
        print(f"[STEP] build_response: FAILED - {error_msg}")
        state["error"] = error_msg
        state["final_response"] = {
            "menu_items": [],
            "total_price": 0,
            "budget": 0,
            "meal_type": ""
        }
    return state

