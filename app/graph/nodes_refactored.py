"""LangGraph nodes - Refactored with JS-style naming."""
import json
import re
from datetime import datetime
from typing import Dict, Any, List
from app.graph.state import MenuGraphState
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store_service
from app.services.query_tool import get_query_tool
from app.prompts import COMBINATION_RULES_PROMPT


def getMealType(hour: int) -> str:
    """Detect meal type based on hour."""
    if 0 <= hour < 4:
        return "tối"
    elif 4 <= hour < 10:
        return "sáng"
    elif 10 <= hour < 14:
        return "trưa"
    elif 14 <= hour < 17:
        return "trưa"
    else:
        return "tối"


def getDefaultBudget(meal_type: str, num_people: int) -> int:
    """Get default budget for meal type and number of people."""
    budgets = {"sáng": 40000, "trưa": 65000, "tối": 80000}
    return budgets.get(meal_type, 65000) * num_people


def detectMealType(user_input: str) -> tuple[str, bool]:
    """Detect meal_type from user input."""
    keywords = {
        "sáng": ["ăn sáng", "bữa sáng", "sáng nay", "buổi sáng"],
        "trưa": ["ăn trưa", "bữa trưa", "trưa nay", "buổi trưa"],
        "tối": ["ăn tối", "bữa tối", "tối nay", "buổi tối"]
    }
    
    user_lower = user_input.lower()
    for meal_type, kw_list in keywords.items():
        if any(kw in user_lower for kw in kw_list):
            return (meal_type, True)
    
    return (None, False)


# Step 1: Parse Intent
def parseIntent(state: MenuGraphState) -> MenuGraphState:
    """Parse user input to extract intent."""
    print("[STEP] parseIntent: Starting...")
    
    user_input = state["user_input"]
    detected_meal, meal_specified = detectMealType(user_input)
    
    current_hour = datetime.now().hour
    meal_type = detected_meal if meal_specified else getMealType(current_hour)
    
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
        if any(x in error_str for x in ["quota", "429", "api key", "401"]):
            raise ValueError(f"API error: {str(e)}")
        print(f"[STEP] parseIntent: LLM failed, using defaults")
    
    if user_budget and isinstance(user_budget, (int, float)) and user_budget > 0:
        budget = int(user_budget)
        budget_specified = True
    else:
        budget = getDefaultBudget(meal_type, num_people)
        budget_specified = False
    
    state["intent"] = {
        "budget": budget,
        "budget_specified": budget_specified,
        "meal_type": meal_type,
        "meal_type_specified": meal_specified,
        "num_people": num_people,
        "preferences": preferences
    }
    state["iteration_count"] = 0
    
    print(f"[STEP] parseIntent: Success - {meal_type}, budget={budget:,}, people={num_people}")
    return state


# Step 2: Query Products + Combination Rules → Generate Menu
def queryAndGenerate(state: MenuGraphState) -> MenuGraphState:
    """Query products from vector store + get combination rules → Generate menu.
    
    Refactored logic:
    1. Query available products with price < budget from Vector Store
    2. Get combination rules
    3. LLM combines products + rules → output menu
    """
    print("[STEP] queryAndGenerate: Starting...")
    if state.get("error"):
        print("[STEP] queryAndGenerate: Error detected, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        meal_type = intent.get("meal_type")
        num_people = intent.get("num_people", 1)
        preferences = intent.get("preferences", [])
        
        if not budget or not meal_type:
            raise ValueError("Missing budget or meal_type")
        
        # Step 2.1: Query available products (price < budget) from Vector Store
        print(f"[STEP] queryAndGenerate: Querying products with price < {budget:,} VND...")
        vector_store = get_vector_store_service()
        
        query_text = f"Sản phẩm giá < {budget} VND cho bữa {meal_type}"
        if preferences:
            query_text += f", sở thích: {', '.join(preferences)}"
        
        print(f"[RAG] Query: {query_text}")
        products_docs = vector_store.vector_store.similarity_search(query_text, k=20)
        raw_products = [doc.page_content for doc in products_docs]
        
        if not raw_products:
            state["error"] = "Không tìm thấy sản phẩm phù hợp"
            return state
        
        print(f"[RAG] Retrieved {len(raw_products)} raw product documents")
        
        # LOG RAW PRODUCTS TRƯỚC KHI PARSE
        print("\n" + "="*100)
        print("🔥 RAW PRODUCTS (From Vector Store):")
        print("="*100)
        for idx, doc_content in enumerate(raw_products, 1):
            print(f"{idx}. {doc_content}")
        print("="*100 + "\n")
        
        # Step 2.2: Parse products theo ID - lưu nguyên bản data
        # Format từng dòng: prod_XXX: Tên sản phẩm - Giá
        products_dict = {}  # {prod_id: {"id": "prod_001", "name": "...", "price": 35000}}
        excluded_keywords = [
            "gia vị", "muối", "đường", "tiêu", "nước mắm", "nước tương", 
            "hạt nêm", "dầu ăn", "bơ thực vật",
            "gạo", "bún", "phở", "mì", "bánh mì",
            "sữa", "sữa chua"
        ]
        
        for doc_content in raw_products:
            # Parse format: prod_XXX: Tên sản phẩm - Giá
            # Lấy TẤT CẢ ID, name, price xuất hiện trong doc (không chỉ dòng đầu tiên)
            matches = re.findall(r'(prod_\d+):\s*(.+?)\s*-\s*(\d+)', doc_content)
            for prod_id, product_name, price_str in matches:
                product_name = product_name.strip()
                price = int(price_str)
                
                # Filter out gia vị, gạo, mì...
                if not any(keyword in product_name.lower() for keyword in excluded_keywords):
                    products_dict[prod_id] = {
                        "id": prod_id,
                        "name": product_name,
                        "price": price
                    }
        
        if not products_dict:
            state["error"] = "Không có sản phẩm hợp lệ sau khi lọc"
            return state
        
        print(f"[RAG] Parsed {len(products_dict)} unique products (after filtering)")
        
        # LOG CHI TIẾT PRODUCTS DICT
        print("\n" + "="*100)
        print("🔥 AVAILABLE PRODUCTS (Dict with ID):")
        print("="*100)
        for idx, (prod_id, prod_info) in enumerate(sorted(products_dict.items()), 1):
            print(f"{idx}. {prod_id}: {prod_info['name']} - {prod_info['price']:,} VND")
        print("="*100 + "\n")
        
        # Lưu vào state - dùng dict với ID làm key
        state["available_products"] = products_dict
        state["rag_recipes"] = raw_products
        
        # Step 2.3: Get combination rules
        combination_rules = COMBINATION_RULES_PROMPT
        print("[STEP] queryAndGenerate: Loaded combination rules")
        
        # Step 2.4: LLM generates menu from products + rules
        print("[STEP] queryAndGenerate: Generating menu with LLM...")
        llm_service = get_llm_service()
        
        previous_dishes = state.get("previous_dishes", [])
        budget_specified = intent.get("budget_specified", True)
        
        menu = llm_service.generate_menu_from_products(
            products_dict=products_dict,  # Pass dict với ID
            combination_rules=combination_rules,
            meal_type=meal_type,
            num_people=num_people,
            budget=budget,
            previous_dishes=previous_dishes,
            budget_specified=budget_specified,
            preferences=preferences,
        )
        
        # Step 2.5: STRICT VALIDATION - Reject nếu có ingredient không có trong danh sách
        print("[STEP] queryAndGenerate: STRICT validating ingredient IDs...")
        available_product_ids = set(products_dict.keys())
        invalid_ingredients = []
        
        for item in menu.get("items", []):
            for ing in item.get("ingredients", []):
                ing_id = ing.get("product_id", "").strip()
                
                # CHỈ CHẤP NHẬN product_id có trong products_dict
                if not ing_id or ing_id not in available_product_ids:
                    invalid_ingredients.append(ing_id or ing.get("name", "MISSING_ID"))
                    print(f"[VALIDATION] ❌ REJECTED: product_id '{ing_id}' không có trong danh sách")
        
        if invalid_ingredients:
            error_msg = f"LLM đã generate sản phẩm không có trong danh sách: {', '.join(set(invalid_ingredients))}\nDanh sách có sẵn: {', '.join(list(available_product_ids)[:10])}"
            print(f"[VALIDATION] ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        state["generated_menu"] = menu
        print(f"[STEP] queryAndGenerate: Success - generated {len(menu.get('items', []))} items")
        
    except Exception as e:
        error_msg = str(e)
        print(f"[STEP] queryAndGenerate: FAILED - {error_msg}")
        state["error"] = f"Error in queryAndGenerate: {error_msg}"
    
    return state


# Step 3: Fetch Realtime Pricing
def fetchPricing(state: MenuGraphState) -> MenuGraphState:
    """Fetch realtime pricing from mockupData."""
    print("[STEP] fetchPricing: Starting...")
    if state.get("error"):
        return state
    
    try:
        menu = state.get("generated_menu", {})
        if not menu or not menu.get("items"):
            return state
        
        query_tool = get_query_tool()
        all_products = query_tool._load_mockup_data()
        
        # Map theo ID: {prod_id: product_data}
        price_map_by_id = {p.get("id", ""): p for p in all_products}
        
        # Lấy available_products từ state để có thông tin đầy đủ
        available_products = state.get("available_products", {})
        
        updated_items = []
        total_price = 0
        out_of_stock = []
        
        for item in menu.get("items", []):
            dish_price = 0
            updated_ingredients = []
            
            for ing in item.get("ingredients", []):
                ing_product_id = ing.get("product_id", "")
                ing_quantity = ing.get("quantity", 0)
                ing_unit = ing.get("unit", "g")
                
                # Tìm product theo ID
                if ing_product_id in price_map_by_id:
                    product = price_map_by_id[ing_product_id]
                    base_price = product.get("base_price", product.get("salePrice", product.get("price", 0)))
                    stock = product.get("quantity", 0)
                    
                    if stock < ing_quantity:
                        out_of_stock.append(ing_product_id)
                    
                    price = base_price * ing_quantity
                    dish_price += price
                    
                    # Lấy name từ available_products hoặc product
                    product_name = available_products.get(ing_product_id, {}).get("name") or product.get("name", "")
                    
                    updated_ingredients.append({
                        "product_id": ing_product_id,
                        "name": product_name,
                        "quantity": ing_quantity,
                        "unit": ing_unit,
                        "price": price
                    })
                elif ing_product_id in available_products:
                    # Nếu có trong available_products nhưng không có trong mockupData
                    prod_info = available_products[ing_product_id]
                    price = prod_info.get("price", 0) * ing_quantity
                    dish_price += price
                    
                    updated_ingredients.append({
                        "product_id": ing_product_id,
                        "name": prod_info.get("name", ""),
                        "quantity": ing_quantity,
                        "unit": ing_unit,
                        "price": price
                    })
                else:
                    out_of_stock.append(ing_product_id)
                    updated_ingredients.append(ing)
                    dish_price += ing.get("price", 0)
            
            updated_items.append({
                "name": item.get("name", ""),
                "ingredients": updated_ingredients,
                "price": dish_price
            })
            total_price += dish_price
        
        state["generated_menu"] = {
            "items": updated_items,
            "total_price": total_price
        }
        state["out_of_stock_ingredients"] = out_of_stock
        
        print(f"[STEP] fetchPricing: Success - total: {total_price:,.0f} VND")
        
    except Exception as e:
        print(f"[STEP] fetchPricing: FAILED - {str(e)}")
    
    return state


# Step 4: Validate Budget
def validateBudget(state: MenuGraphState) -> MenuGraphState:
    """Validate menu budget."""
    print("[STEP] validateBudget: Starting...")
    if state.get("error"):
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget", 0)
        menu = state.get("generated_menu", {})
        total_price = menu.get("total_price", 0)
        
        iteration = state.get("iteration_count", 0)
        max_iterations = 2
        
        budget_tolerance = budget * 1.05
        min_usage = budget * 0.75
        
        if iteration >= max_iterations:
            if total_price <= budget:
                state["needs_adjustment"] = False
                state["needs_enhancement"] = False
                state["budget_error"] = None
            else:
                state["needs_adjustment"] = True
                state["budget_error"] = f"Exceeds budget: {total_price:,.0f} > {budget:,.0f}"
        elif total_price > budget_tolerance:
            state["needs_adjustment"] = True
            state["needs_enhancement"] = False
            state["budget_error"] = f"Exceeds budget by {total_price - budget:,.0f} VND"
        elif total_price < min_usage:
            state["needs_adjustment"] = False
            state["needs_enhancement"] = True
            state["budget_error"] = f"Under-utilized: {(total_price/budget)*100:.1f}%"
        else:
            state["needs_adjustment"] = False
            state["needs_enhancement"] = False
            state["budget_error"] = None
        
        print(f"[STEP] validateBudget: {total_price:,.0f}/{budget:,.0f} VND")
        
    except Exception as e:
        state["error"] = f"Validation error: {str(e)}"
    
    return state


# Step 5: Adjust Menu
def adjustMenu(state: MenuGraphState) -> MenuGraphState:
    """Adjust menu to fit budget."""
    print("[STEP] adjustMenu: Starting...")
    if state.get("error"):
        return state
    
    try:
        intent = state.get("intent", {})
        budget = intent.get("budget")
        menu = state.get("generated_menu", {})
        rag_recipes = state.get("rag_recipes", [])
        
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        
        llm_service = get_llm_service()
        adjusted = llm_service.adjust_menu_from_rag(
            menu=menu,
            rag_recipes=rag_recipes,
            validation_errors=[state.get("budget_error", "")],
            out_of_stock=state.get("out_of_stock_ingredients", []),
            budget=budget,
            needs_enhancement=state.get("needs_enhancement", False)
        )
        
        state["generated_menu"] = adjusted
        print(f"[STEP] adjustMenu: Adjusted")
        
    except Exception as e:
        state["error"] = f"Adjustment error: {str(e)}"
    
    return state


# Step 6: Build Response
def buildResponse(state: MenuGraphState) -> MenuGraphState:
    """Build final response."""
    print("[STEP] buildResponse: Starting...")
    try:
        menu = state.get("generated_menu", {})
        intent = state.get("intent", {})
        
        state["final_response"] = {
            "menu_items": menu.get("items", []),
            "total_price": menu.get("total_price", 0),
            "budget": intent.get("budget", 0),
            "meal_type": intent.get("meal_type", "")
        }
        
        print("[STEP] buildResponse: Success")
    except Exception as e:
        print(f"[STEP] buildResponse: FAILED - {str(e)}")
        state["final_response"] = {
            "menu_items": [],
            "total_price": 0,
            "budget": 0,
            "meal_type": ""
        }
    
    return state

