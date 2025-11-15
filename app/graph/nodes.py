"""LangGraph nodes implementation."""
import json
import os
import random
from datetime import datetime
from typing import Dict, Any
from app.graph.state import MenuGraphState
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store_service
from app.services.query_tool import get_query_tool


def get_meal_type(hour: int) -> str:
    """Detect meal type based on hour."""
    if 0 <= hour < 4:
        return "tối"
    elif 4 <= hour < 10:
        return "sáng"
    elif 10 <= hour < 14:
        return "trưa"
    elif 14 <= hour < 17:
        return "trưa"
    elif 17 <= hour < 24:
        return "tối"
    else:
        return "trưa"


def get_budget(meal_type: str, num_people: int) -> int:
    """Get default budget for meal type and number of people."""
    if meal_type == "sáng":
        return 40000 * num_people
    elif meal_type == "trưa":
        return 65000 * num_people
    elif meal_type == "tối":
        return 80000 * num_people
    else:
        return 65000 * num_people


def detect_meal_type_from_input(user_input: str) -> tuple[str, bool]:
    """Detect meal_type from user input. Returns (meal_type, specified)."""
    user_input_lower = user_input.lower()
    
    if any(keyword in user_input_lower for keyword in ["ăn sáng", "bữa sáng", "sáng nay", "buổi sáng"]):
        return ("sáng", True)
    elif any(keyword in user_input_lower for keyword in ["ăn trưa", "bữa trưa", "trưa nay", "buổi trưa"]):
        return ("trưa", True)
    elif any(keyword in user_input_lower for keyword in ["ăn tối", "bữa tối", "tối nay", "buổi tối"]):
        return ("tối", True)
    
    return (None, False)


def parse_intent_node(state: MenuGraphState) -> MenuGraphState:
    """Parse user input to extract intent. Always sets complete intent with fallback logic."""
    print("[STEP] parse_intent: Starting...")
    
    user_input = state["user_input"]
    detected_meal_type, meal_type_specified = detect_meal_type_from_input(user_input)
    
    current_hour = datetime.now().hour
    if meal_type_specified:
        meal_type = detected_meal_type
        print(f"[STEP] parse_intent: User specified meal_type={meal_type}")
    else:
        meal_type = get_meal_type(current_hour)
        print(f"[STEP] parse_intent: Auto-detected meal_type={meal_type} from hour={current_hour}")
    
    num_people = 1
    user_budget = None
    preferences = []
    
    try:
        llm_service = get_llm_service()
        parsed = llm_service.parse_intent(user_input)
        
        if isinstance(parsed, dict):
            user_budget = parsed.get("budget")
            num_people = parsed.get("num_people", 1)
            preferences = parsed.get("preferences", [])
            
            if not isinstance(num_people, int) or num_people < 1:
                num_people = 1
            if not isinstance(preferences, list):
                preferences = []
    except Exception as e:
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
        print(f"[STEP] parse_intent: LLM parse failed, using fallback defaults")
    
    if user_budget is not None and isinstance(user_budget, (int, float)) and user_budget > 0:
        budget = int(user_budget)
        budget_specified = True
        print(f"[STEP] parse_intent: User specified budget={budget:,} VND")
    else:
        budget = get_budget(meal_type, num_people)
        budget_specified = False
        print(f"[STEP] parse_intent: Auto-applied budget={budget:,} VND for {meal_type} ({num_people} người)")
    
    intent = {
        "budget": budget,
        "budget_specified": budget_specified,
        "meal_type": meal_type,
        "meal_type_specified": meal_type_specified,
        "num_people": num_people,
        "preferences": preferences
    }
    
    state["intent"] = intent
    state["iteration_count"] = 0
    print(f"[STEP] parse_intent: Success - meal_type={meal_type}, meal_type_specified={meal_type_specified}, budget={budget}, budget_specified={budget_specified}, num_people={num_people}")
    return state


def query_ingredients_node(state: MenuGraphState) -> MenuGraphState:
    """Query ingredients using SQL generated from intent.
    
    Query tool will:
    - Generate SQL from intent using LLM
    - Filter mockup data (or execute on real DB later)
    - Return filtered ingredients
    """
    print("[STEP] query_ingredients: Starting...")
    if state.get("error"):
        print("[STEP] query_ingredients: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        preferences = intent.get("preferences", []) or []
        query_tool = get_query_tool()
        ingredients = query_tool.query_ingredients(intent)
        
        if not ingredients:
            # CRITICAL: Không có nguyên liệu → DỪNG pipeline
            if preferences:
                pref_text = ", ".join(preferences)
                error_msg = f"Không có nguyên liệu phù hợp với yêu cầu: {pref_text}"
            else:
                error_msg = "Không có nguyên liệu phù hợp với điều kiện lọc"
            print(f"[STEP] query_ingredients: FAILED - {error_msg}")
            state["error"] = error_msg
            state["available_ingredients"] = []
            return state
        
        state["available_ingredients"] = ingredients
        print(f"[STEP] query_ingredients: Success - retrieved {len(ingredients)} filtered ingredients")
        
    except Exception as e:
        error_msg = f"Error querying ingredients: {str(e)}"
        print(f"[STEP] query_ingredients: FAILED - {error_msg}")
        state["error"] = error_msg
        state["available_ingredients"] = []
    
    return state


def prefilter_ingredients_by_budget_node(state: MenuGraphState) -> MenuGraphState:
    """Post-process filtered ingredients: prioritize fresh, limit count, shuffle."""
    print("[STEP] prefilter_ingredients: Starting...")
    if state.get("error"):
        print("[STEP] prefilter_ingredients: Error detected in state, skipping")
        return state
    
    try:
        all_ingredients = state.get("available_ingredients", [])
        
        # Separate fresh vs other
        fresh_ingredients = []
        other_ingredients = []
        
        for ing in all_ingredients:
            category = ing.get("category", "").lower()
            if category == "tươi" or category == "chay":
                fresh_ingredients.append(ing)
            else:
                other_ingredients.append(ing)
        
        # Sort by price
        fresh_ingredients.sort(key=lambda x: x.get("base_price", 0))
        other_ingredients.sort(key=lambda x: x.get("base_price", 0))
        
        # Prioritize fresh (40 fresh + 10 other max)
        filtered = fresh_ingredients[:40] + other_ingredients[:10]
        
        # Remove duplicates
        seen = set()
        unique_filtered = []
        for ing in filtered:
            if ing["name"] not in seen:
                seen.add(ing["name"])
                unique_filtered.append(ing)
        
        # Shuffle for diversity
        random.shuffle(unique_filtered)
        
        state["available_ingredients"] = unique_filtered
        print(f"[STEP] prefilter_ingredients: Success - {len(unique_filtered)} ingredients ({len([i for i in unique_filtered if i.get('category','').lower() in ['tươi','chay']])} fresh)")
        
    except Exception as e:
        error_msg = f"Error prefiltering ingredients: {str(e)}"
        print(f"[STEP] prefilter_ingredients: FAILED - {error_msg}")
        state["error"] = error_msg
    return state


def retrieve_rules_and_generate_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Retrieve ingredient combination rules from Pinecone and generate menu."""
    print("[STEP] retrieve_rules_and_generate_menu: Starting...")
    if state.get("error"):
        print("[STEP] retrieve_rules_and_generate_menu: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        meal_type = intent.get("meal_type")
        num_people = intent.get("num_people", 1)
        preferences = intent.get("preferences", [])
        
        if not budget or not meal_type:
            raise ValueError("Missing budget or meal_type in intent")
        
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
        
        previous_dishes = state.get("previous_dishes", [])
        if previous_dishes:
            print(f"[STEP] retrieve_rules_and_generate_menu: User has {len(previous_dishes)} previous dishes, will avoid repeating them")
        
        budget_specified = intent.get("budget_specified", True)
        print(f"[STEP] retrieve_rules_and_generate_menu: Budget specified by user: {budget_specified}")
        
        menu = llm_service.generate_menu(
            ingredients=ingredients,
            context=combination_rules,
            meal_type=meal_type,
            num_people=num_people,
            budget=budget,
            previous_dishes=previous_dishes,
            budget_specified=budget_specified,
            preferences=preferences,
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
        
        if "quota" in error_str or "429" in error_str or "resourceexhausted" in error_str:
            print("[STEP] retrieve_rules_and_generate_menu: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API quota exceeded: {error_msg}")
        if "api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or "401" in error_str:
            print("[STEP] retrieve_rules_and_generate_menu: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API key error: {error_msg}")
        if "Failed to generate" in error_str or "invalid json" in error_str or "jsondecodeerror" in error_str or "missing required key" in error_str or "keyerror" in error_str:
            print("[STEP] retrieve_rules_and_generate_menu: Critical error detected (JSON parsing/structure failed), raising exception to stop workflow")
            raise ValueError(f"Failed to generate: LLM returned invalid response. {error_msg}")
        state["error"] = f"Error generating menu: {error_msg}"
        state["combination_rules"] = []
        state["generated_menu"] = {"items": [], "total_price": 0}
    return state


def validate_budget_node(state: MenuGraphState) -> MenuGraphState:
    """Validate that generated menu is within budget."""
    print("[STEP] validate_budget: Starting...")
    if state.get("error"):
        print("[STEP] validate_budget: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        menu = state.get("generated_menu", {})
        available_ingredients = state.get("available_ingredients", [])
        
        if not budget:
            raise ValueError("Missing budget in intent")
        
        ingredient_map = {ing["name"].lower(): ing for ing in available_ingredients}
        
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
                    dish_price += ing.get("price", 0)
            total_price += dish_price
        
        budget_tolerance = budget * 1.05
        min_budget_usage = budget * 0.75
        iteration_count = state.get("iteration_count", 0)
        max_iterations = 2
        
        # Nếu đã qua 2 lần adjust, chỉ check < budget, bỏ qua yêu cầu 75%
        if iteration_count >= max_iterations:
            if total_price <= budget:
                state["needs_adjustment"] = False
                state["needs_enhancement"] = False
                state["budget_error"] = None
                usage_percent = (total_price / budget) * 100
                print(f"[STEP] validate_budget: PASS (max iterations reached) - total {total_price:,.0f} VND ({usage_percent:.1f}% budget) < budget")
            else:
                state["needs_adjustment"] = True
                state["needs_enhancement"] = False
                state["budget_error"] = f"Menu total ({total_price:,.0f} VND) exceeds budget ({budget:,.0f} VND)"
                print(f"[STEP] validate_budget: FAILED (max iterations) - {state['budget_error']}")
        # Nếu chưa đến max iterations, áp dụng quy tắc 75%
        elif total_price > budget_tolerance:
            state["needs_adjustment"] = True
            state["needs_enhancement"] = False
            state["budget_error"] = f"Menu total ({total_price:,.0f} VND) exceeds budget ({budget:,.0f} VND) by {total_price - budget:,.0f} VND"
            print(f"[STEP] validate_budget: FAILED - {state['budget_error']}")
        elif total_price < min_budget_usage:
            state["needs_adjustment"] = False
            state["needs_enhancement"] = True
            usage_percent = (total_price / budget) * 100
            state["budget_error"] = f"Menu total ({total_price:,.0f} VND) chỉ dùng {usage_percent:.1f}% budget ({budget:,.0f} VND). Cần tăng lên tối thiểu {min_budget_usage:,.0f} VND (75% budget)"
            print(f"[STEP] validate_budget: NEEDS ENHANCEMENT - {state['budget_error']}")
        else:
            state["needs_adjustment"] = False
            state["needs_enhancement"] = False
            state["budget_error"] = None
            usage_percent = (total_price / budget) * 100
            print(f"[STEP] validate_budget: Success - total {total_price:,.0f} VND ({usage_percent:.1f}% budget) trong khoảng hợp lý")
        
        menu["total_price"] = total_price
        state["generated_menu"] = menu
        
    except Exception as e:
        error_msg = f"Error validating budget: {str(e)}"
        print(f"[STEP] validate_budget: FAILED - {error_msg}")
        state["error"] = error_msg
    return state


def adjust_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Adjust menu to fit within budget or enhance to meet minimum usage using LLM."""
    print("[STEP] adjust_menu: Starting...")
    if state.get("error"):
        print("[STEP] adjust_menu: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        menu = state.get("generated_menu", {})
        available_ingredients = state.get("available_ingredients", [])
        budget_error = state.get("budget_error", "Menu needs adjustment")
        needs_enhancement = state.get("needs_enhancement", False)
        
        if not budget:
            raise ValueError("Missing budget in intent")
        
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        iteration = state["iteration_count"]
        
        if needs_enhancement:
            min_target = budget * 0.80
            print(f"[STEP] adjust_menu: Iteration {iteration}, enhancing menu to reach minimum {min_target:,.0f} VND (75% of {budget:,.0f} VND)")
        else:
            print(f"[STEP] adjust_menu: Iteration {iteration}, reducing menu to fit within budget {budget:,.0f} VND")
        
        llm_service = get_llm_service()
        adjusted_menu = llm_service.adjust_menu(
            menu=menu,
            validation_errors=[budget_error],
            available_ingredients=available_ingredients,
            budget=budget,
            needs_enhancement=needs_enhancement
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
        budget = intent.get("budget")
        meal_type = intent.get("meal_type")
        
        if not budget or not meal_type:
            raise ValueError("Missing budget or meal_type in intent")
        
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

