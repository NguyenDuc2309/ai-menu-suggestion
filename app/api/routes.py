"""API routes."""
import time
import traceback
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException
from slowapi.util import get_remote_address
from app.models.request import MenuRequest
from app.models.response import MenuResponse, MenuData, MenuDish, IngredientItem
from app.graph.graph import menu_graph
from app.graph.state import MenuGraphState

router = APIRouter(prefix="/api/v1", tags=["menu"])

# Simple rate limiting storage: {ip: (count, reset_time)}
_rate_limit_storage = defaultdict(lambda: (0, time.time() + 60))


def check_rate_limit(request: Request, limit: int = 10, window: int = 60):
    """Check rate limit for request."""
    ip = get_remote_address(request)
    current_time = time.time()
    
    count, reset_time = _rate_limit_storage[ip]
    
    # Reset if window expired
    if current_time > reset_time:
        _rate_limit_storage[ip] = (1, current_time + window)
        return
    
    # Check limit
    if count >= limit:
        raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {limit} requests per {window} seconds")
    
    # Increment count
    _rate_limit_storage[ip] = (count + 1, reset_time)


@router.post("/menu/suggest", response_model=MenuResponse)
async def suggest_menu(request: Request, menu_request: MenuRequest) -> MenuResponse:
    # Validate input
    if not menu_request.query or not menu_request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required and cannot be empty")
    
    # Rate limiting: 10 requests per minute per IP
    check_rate_limit(request, limit=10, window=60)
    
    print(f"\n[REQUEST] Starting menu suggestion for query: '{menu_request.query}'")
    request_start_time = time.time()
    try:
        initial_state: MenuGraphState = {
            "user_input": menu_request.query,
            "intent": {},
            "available_ingredients": [],
            "combination_rules": [],
            "generated_menu": {},
            "final_response": None,
            "error": None,
            "iteration_count": 0,
            "needs_adjustment": None,
            "budget_error": None,
            "llm_usage": []
        }
        
        print("[REQUEST] Invoking menu graph workflow...")
        try:
            final_state = menu_graph.invoke(initial_state)
            print(f"[REQUEST] Graph workflow completed in {time.time() - request_start_time:.3f}s")
        except ValueError as e:
            # Critical errors (quota, API key) are raised as ValueError
            error_msg = str(e)
            print(f"[REQUEST] Critical error during workflow execution: {error_msg}")
            if "quota" in error_msg.lower() or "429" in error_msg.lower():
                raise HTTPException(status_code=503, detail="API quota exceeded. Please try again later.")
            elif "api key" in error_msg.lower():
                raise HTTPException(status_code=503, detail="Invalid API key configuration")
            else:
                raise HTTPException(status_code=500, detail="Workflow execution failed")
        except Exception as e:
            # Any other exception during workflow execution
            error_msg = str(e)
            print(f"[REQUEST] Unexpected error during workflow execution: {error_msg}")
            print(f"[REQUEST] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Internal server error during workflow execution")
        
        total_time = time.time() - request_start_time
        
        # Check for errors in state
        if final_state.get("error"):
            error_msg = final_state["error"]
            print(f"[REQUEST] ERROR detected in final state: {error_msg}")
            print(f"[REQUEST] Final state keys: {list(final_state.keys())}")
            print(f"[REQUEST] Iteration count: {final_state.get('iteration_count', 0)}")
            
            # Extract clean error message
            clean_error = error_msg
            if "Error generating menu:" in error_msg:
                clean_error = error_msg.split("Error generating menu:")[-1].strip()
            if "Error querying Pinecone:" in clean_error:
                clean_error = clean_error.split("Error querying Pinecone:")[-1].strip()
            if "Error embedding content:" in clean_error:
                clean_error = clean_error.split("Error embedding content:")[-1].strip()
            
            # Determine status code based on error type
            if "quota" in error_msg.lower() or "429" in error_msg.lower() or "resourceexhausted" in error_msg.lower():
                print("[REQUEST] Error type: API quota exceeded")
                raise HTTPException(status_code=503, detail="API quota exceeded. Please try again later.")
            elif "API key" in error_msg.lower() or "API_KEY_INVALID" in error_msg or "not valid" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
                print("[REQUEST] Error type: API key configuration")
                raise HTTPException(status_code=503, detail="Invalid API key configuration")
            elif "Missing" in error_msg or "configuration" in error_msg.lower():
                print("[REQUEST] Error type: Service configuration")
                raise HTTPException(status_code=503, detail="Service configuration error")
            else:
                print("[REQUEST] Error type: General failure")
                raise HTTPException(status_code=500, detail="Failed to generate menu")
        
        final_response = final_state.get("final_response")
        if not final_response:
            raise HTTPException(status_code=500, detail="No response generated")
        
        # Check if menu is empty (indicates error)
        menu_items_list = final_response.get("menu_items", [])
        if not menu_items_list:
            raise HTTPException(status_code=500, detail="Failed to generate menu items")
        
        # Calculate total tokens from llm_usage
        llm_usage = final_state.get("llm_usage", [])
        total_tokens = 0
        for usage in llm_usage:
            tokens = usage.get("tokens", {})
            total_tokens += tokens.get("total_tokens", 0)
        
        metadata = {
            "process_time": round(total_time, 3),
            "token_usage": total_tokens
        }
        
        # Format menu dishes and recalculate prices from available ingredients
        available_ingredients = final_state.get("available_ingredients", [])
        available_map = {
            ing["name"].lower(): ing for ing in available_ingredients
        }
        
        menu_dishes = []
        for item in menu_items_list:
            ingredients = []
            dish_total_price = 0
            
            for ing in item.get("ingredients", []):
                ing_name = ing["name"]
                ing_name_lower = ing_name.lower()
                ing_quantity = ing.get("quantity", 0)
                ing_unit = ing.get("unit", "g")
                
                # Recalculate price from available ingredients
                # base_price in mock_ingredients.json is price per unit
                if ing_name_lower in available_map:
                    available_ing = available_map[ing_name_lower]
                    base_price = available_ing["base_price"]  # price per unit
                    calculated_price = base_price * ing_quantity
                else:
                    calculated_price = ing.get("price", 0)
                
                ingredients.append(
                    IngredientItem(
                        name=ing_name,
                        quantity=ing_quantity,
                        unit=ing_unit,
                        price=round(calculated_price)
                    )
                )
                dish_total_price += calculated_price
            
            menu_dishes.append(
                MenuDish(
                    name=item["name"],
                    total_price=round(dish_total_price),
                    ingredients=ingredients
                )
            )
        
        # Get intent info
        intent = final_state.get("intent", {})
        cuisine = final_response.get("cuisine_type", intent.get("cuisine", "Việt"))
        total_budget = intent.get("budget", 200000)
        # Recalculate total price from recalculated dish prices
        total_estimated_price = sum(dish.total_price for dish in menu_dishes)
        
        # Budget validation is now handled in the graph, but double-check here
        # Allow 5% tolerance for rounding
        if total_estimated_price > total_budget * 1.05:
            error_msg = f"Generated menu exceeds budget: {total_estimated_price:,.0f} VND > {total_budget:,.0f} VND"
            print(f"[REQUEST] Budget validation failed: {error_msg}")
            print(f"[REQUEST] This should have been caught by validate_budget_node!")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate menu within budget. Menu cost: {total_estimated_price:,.0f} VND, Budget: {total_budget:,.0f} VND"
            )
        
        # Generate message
        num_dishes = len(menu_dishes)
        cuisine_name = cuisine
        budget_formatted = f"{total_budget:,.0f}".replace(",", ".")
        message = f"Hôm nay tôi gợi ý cho bạn {num_dishes} món {cuisine_name} hấp dẫn, ngon miệng và phù hợp với ngân sách {budget_formatted} VND. Mỗi món đều liệt kê nguyên liệu và giá, giúp bạn dễ dàng chuẩn bị."
        
        menu_data = MenuData(
            cuisine=cuisine,
            total_budget=total_budget,
            total_estimated_price=total_estimated_price,
            menu=menu_dishes
        )
        
        return MenuResponse(
            statusCode=200,
            message=message,
            data=menu_data,
            metadata=metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        error_msg = str(e)
        print(f"[REQUEST] ValueError caught: {error_msg}")
        print(f"[REQUEST] Traceback: {traceback.format_exc()}")
        if "Missing" in error_msg or "API key" in error_msg.lower():
            raise HTTPException(status_code=503, detail="Service configuration error")
        raise HTTPException(status_code=400, detail="Invalid request")
    except Exception as e:
        error_msg = str(e)
        print(f"[REQUEST] Unexpected exception caught: {error_msg}")
        print(f"[REQUEST] Traceback: {traceback.format_exc()}")
        # Check if it's an API key error
        if "API key" in error_msg.lower() or "API_KEY_INVALID" in error_msg:
            raise HTTPException(status_code=503, detail="Invalid API key configuration")
        raise HTTPException(status_code=500, detail="Internal server error")

