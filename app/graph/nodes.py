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

# Step 1: Parse intent
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


# Step 2: Retrieve recipes from RAG (RAG v2 Pipeline)
def retrieve_recipes_from_rag_node(state: MenuGraphState) -> MenuGraphState:
    """Query RAG to retrieve recipes with ingredients (RAG v2).
    
    RAG returns:
    - Món ăn hoàn chỉnh với nguyên liệu
    - Combination rules
    - Domain knowledge
    """
    print("[STEP] retrieve_recipes_from_rag: Starting...")
    if state.get("error"):
        print("[STEP] retrieve_recipes_from_rag: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        meal_type = intent.get("meal_type")
        num_people = intent.get("num_people", 1)
        preferences = intent.get("preferences", [])
        
        if not budget or not meal_type:
            raise ValueError("Missing budget or meal_type in intent")
        
        print(f"[STEP] retrieve_recipes_from_rag: Querying RAG for recipes (meal_type: {meal_type}, preferences: {preferences})...")
        vector_store = get_vector_store_service()
        recipes = vector_store.query_recipes(
            meal_type=meal_type,
            preferences=preferences,
            budget=budget,
            num_people=num_people,
            top_k=10
        )
        
        if not recipes:
            error_msg = "Không tìm thấy món ăn phù hợp trong RAG"
            print(f"[STEP] retrieve_recipes_from_rag: FAILED - {error_msg}")
            state["error"] = error_msg
            state["rag_recipes"] = []
            return state
        
        state["rag_recipes"] = recipes
        print(f"[STEP] retrieve_recipes_from_rag: Success - retrieved {len(recipes)} results from RAG")
        
        # LOG CHI TIẾT RAG RECIPES
        print("\n" + "="*100)
        print("🔥 RAG RESULTS DETAILS:")
        print("="*100)
        for idx, recipe in enumerate(recipes, 1):
            print(f"\n--- RESULT {idx} ---")
            print(recipe)
            print("-" * 80)
        print("="*100 + "\n")
        
    except Exception as e:
        error_msg = str(e)
        error_str = error_msg.lower()
        print(f"[STEP] retrieve_recipes_from_rag: FAILED - Exception type: {type(e).__name__}, Message: {error_msg}")
        import traceback
        print(f"[STEP] retrieve_recipes_from_rag: Traceback: {traceback.format_exc()}")
        
        if "quota" in error_str or "429" in error_str or "resourceexhausted" in error_str:
            raise ValueError(f"API quota exceeded: {error_msg}")
        if "api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or "401" in error_str:
            raise ValueError(f"API key error: {error_msg}")
        
        state["error"] = f"Error querying RAG: {error_msg}"
        state["rag_recipes"] = []
    
    return state


# Step 3: Generate menu from RAG recipes (RAG v2 Pipeline)
def generate_menu_from_rag_recipes_node(state: MenuGraphState) -> MenuGraphState:
    """Generate menu by selecting and formatting recipes from RAG.
    
    LLM task: Select best recipes from RAG, format to JSON.
    RAG already has: món ăn + nguyên liệu + combination rules.
    """
    print("[STEP] generate_menu_from_rag: Starting...")
    if state.get("error"):
        print("[STEP] generate_menu_from_rag: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        meal_type = intent.get("meal_type")
        num_people = intent.get("num_people", 1)
        preferences = intent.get("preferences", [])
        
        if not budget or not meal_type:
            raise ValueError("Missing budget or meal_type in intent")
        
        rag_recipes = state.get("rag_recipes", [])
        if not rag_recipes:
            raise ValueError("No RAG recipes available")
        
        print(f"[STEP] generate_menu_from_rag: Generating menu from {len(rag_recipes)} RAG recipes...")
        llm_service = get_llm_service()
        
        previous_dishes = state.get("previous_dishes", [])
        if previous_dishes:
            print(f"[STEP] generate_menu_from_rag: User has {len(previous_dishes)} previous dishes, will avoid repeating them")
        
        budget_specified = intent.get("budget_specified", True)
        print(f"[STEP] generate_menu_from_rag: Budget specified by user: {budget_specified}")
        
        # Generate menu from RAG recipes
        menu = llm_service.generate_menu_from_rag(
            rag_recipes=rag_recipes,
            meal_type=meal_type,
            num_people=num_people,
            budget=budget,
            previous_dishes=previous_dishes,
            budget_specified=budget_specified,
            preferences=preferences,
        )
        state["generated_menu"] = menu
        
        menu_items_count = len(menu.get("items", []))
        print(f"[STEP] generate_menu_from_rag: Success - generated {menu_items_count} menu items")
        
    except Exception as e:
        error_msg = str(e)
        error_str = error_msg.lower()
        print(f"[STEP] generate_menu_from_rag: FAILED - Exception type: {type(e).__name__}, Message: {error_msg}")
        import traceback
        print(f"[STEP] generate_menu_from_rag: Traceback: {traceback.format_exc()}")
        
        if "quota" in error_str or "429" in error_str or "resourceexhausted" in error_str:
            print("[STEP] generate_menu_from_rag: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API quota exceeded: {error_msg}")
        if "api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or "401" in error_str:
            print("[STEP] generate_menu_from_rag: Critical error detected, raising exception to stop workflow")
            raise ValueError(f"API key error: {error_msg}")
        if "Failed to generate" in error_str or "invalid json" in error_str or "jsondecodeerror" in error_str or "missing required key" in error_str or "keyerror" in error_str:
            print("[STEP] generate_menu_from_rag: Critical error detected (JSON parsing/structure failed), raising exception to stop workflow")
            raise ValueError(f"Failed to generate: LLM returned invalid response. {error_msg}")
        state["error"] = f"Error generating menu: {error_msg}"
        state["generated_menu"] = {"items": [], "total_price": 0}
    return state

# Step 4: Fetch realtime ingredient pricing (Step C in RAG v2)
def fetch_realtime_pricing_node(state: MenuGraphState) -> MenuGraphState:
    """Fetch realtime pricing from mockupData.json and update menu prices.
    
    Step C: Lấy giá thực tế từ DB/API và cập nhật menu.
    """
    print("[STEP] fetch_realtime_pricing: Starting...")
    if state.get("error"):
        print("[STEP] fetch_realtime_pricing: Error detected in state, skipping")
        return state
    
    try:
        menu = state.get("generated_menu", {})
        if not menu or not menu.get("items"):
            print("[STEP] fetch_realtime_pricing: No menu items to price")
            return state
        
        # Load realtime prices from mockupData
        query_tool = get_query_tool()
        all_products = query_tool._load_mockup_data()
        
        # Create price map
        price_map = {}
        for product in all_products:
            name_lower = product.get("name", "").lower()
            price_map[name_lower] = {
                "base_price": product.get("base_price", 0),
                "quantity": product.get("quantity", 0),
                "unit": product.get("unit", "g")
            }
        
        print(f"[STEP] fetch_realtime_pricing: Loaded {len(price_map)} products for pricing")
        
        # Update menu with realtime prices
        updated_items = []
        total_price = 0
        out_of_stock = []
        
        for item in menu.get("items", []):
            dish_price = 0
            updated_ingredients = []
            
            for ing in item.get("ingredients", []):
                ing_name = ing.get("name", "")
                ing_name_lower = ing_name.lower()
                ing_quantity = ing.get("quantity", 0)
                ing_unit = ing.get("unit", "g")
                
                if ing_name_lower in price_map:
                    product_info = price_map[ing_name_lower]
                    base_price = product_info["base_price"]
                    stock_quantity = product_info["quantity"]
                    
                    # Check stock
                    if stock_quantity < ing_quantity:
                        out_of_stock.append(ing_name)
                        print(f"[STEP] fetch_realtime_pricing: {ing_name} out of stock (need {ing_quantity}, have {stock_quantity})")
                    
                    # Calculate realtime price
                    realtime_price = base_price * ing_quantity
                    dish_price += realtime_price
                    
                    updated_ingredients.append({
                        "name": ing_name,
                        "quantity": ing_quantity,
                        "unit": ing_unit,
                        "price": realtime_price
                    })
                else:
                    # Ingredient not found in mockupData
                    out_of_stock.append(ing_name)
                    print(f"[STEP] fetch_realtime_pricing: {ing_name} not found in mockupData")
                    # Keep original price as fallback
                    updated_ingredients.append(ing)
                    dish_price += ing.get("price", 0)
            
            updated_items.append({
                "name": item.get("name", ""),
                "ingredients": updated_ingredients,
                "price": dish_price
            })
            total_price += dish_price
        
        updated_menu = {
            "items": updated_items,
            "total_price": total_price
        }
        
        state["generated_menu"] = updated_menu
        state["out_of_stock_ingredients"] = out_of_stock
        
        if out_of_stock:
            print(f"[STEP] fetch_realtime_pricing: Warning - {len(out_of_stock)} ingredients out of stock or not found")
        
        print(f"[STEP] fetch_realtime_pricing: Success - updated menu with realtime prices, total: {total_price:,.0f} VND")
        
    except Exception as e:
        error_msg = f"Error fetching realtime pricing: {str(e)}"
        print(f"[STEP] fetch_realtime_pricing: FAILED - {error_msg}")
        import traceback
        print(f"[STEP] fetch_realtime_pricing: Traceback: {traceback.format_exc()}")
        # Don't set error, use fallback prices
        print("[STEP] fetch_realtime_pricing: Using fallback prices from RAG")
    
    return state


# Step 5: Validate budget
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


# Step 6: Adjust menu (Step D in RAG v2)
def adjust_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Adjust menu to fit within budget (Step D).
    
    Uses RAG recipes to replace or adjust dishes.
    """
    print("[STEP] adjust_menu: Starting...")
    if state.get("error"):
        print("[STEP] adjust_menu: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        menu = state.get("generated_menu", {})
        rag_recipes = state.get("rag_recipes", [])
        budget_error = state.get("budget_error", "Menu needs adjustment")
        needs_enhancement = state.get("needs_enhancement", False)
        out_of_stock = state.get("out_of_stock_ingredients", [])
        
        if not budget:
            raise ValueError("Missing budget in intent")
        
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        iteration = state["iteration_count"]
        
        if needs_enhancement:
            min_target = budget * 0.75
            print(f"[STEP] adjust_menu: Iteration {iteration}, enhancing menu to reach minimum {min_target:,.0f} VND (75% of {budget:,.0f} VND)")
        else:
            print(f"[STEP] adjust_menu: Iteration {iteration}, reducing menu to fit within budget {budget:,.0f} VND")
        
        llm_service = get_llm_service()
        adjusted_menu = llm_service.adjust_menu_from_rag(
            menu=menu,
            rag_recipes=rag_recipes,
            validation_errors=[budget_error],
            out_of_stock=out_of_stock,
            budget=budget,
            needs_enhancement=needs_enhancement
        )
        
        state["generated_menu"] = adjusted_menu
        
        # Re-fetch realtime pricing after adjustment
        query_tool = get_query_tool()
        all_products = query_tool._load_mockup_data()
        price_map = {p.get("name", "").lower(): p for p in all_products}
        
        total_price = 0
        for item in adjusted_menu.get("items", []):
            dish_price = 0
            for ing in item.get("ingredients", []):
                ing_name_lower = ing.get("name", "").lower()
                if ing_name_lower in price_map:
                    base_price = price_map[ing_name_lower].get("base_price", 0)
                    quantity = ing.get("quantity", 0)
                    dish_price += base_price * quantity
                else:
                    dish_price += ing.get("price", 0)
            total_price += dish_price
        
        adjusted_menu["total_price"] = total_price
        state["generated_menu"] = adjusted_menu
        
        menu_items_count = len(adjusted_menu.get("items", []))
        print(f"[STEP] adjust_menu: Success - adjusted menu has {menu_items_count} items, new total: {total_price:,.0f} VND")
        
    except Exception as e:
        error_msg = f"Error adjusting menu: {str(e)}"
        print(f"[STEP] adjust_menu: FAILED - {error_msg}")
        state["error"] = error_msg
    return state


# Step 7: Build response (Step E in RAG v2)
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

