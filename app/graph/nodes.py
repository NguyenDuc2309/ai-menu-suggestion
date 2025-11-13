"""LangGraph nodes implementation."""
import json
import os
from typing import Dict, Any
from app.graph.state import MenuGraphState
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store_service


def parse_intent_node(state: MenuGraphState) -> MenuGraphState:
    """Parse user input to extract intent."""
    print("[STEP] parse_intent: Starting...")
    try:
        llm_service = get_llm_service()
        intent, usage_info = llm_service.parse_intent(state["user_input"])
        state["intent"] = intent
        state["iteration_count"] = 0
        if "llm_usage" not in state:
            state["llm_usage"] = []
        state["llm_usage"].append({"operation": "parse_intent", **usage_info})
        print(f"[STEP] parse_intent: Success - cuisine={intent.get('cuisine')}, budget={intent.get('budget')}")
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
            "cuisine": "Việt",
            "budget": 200000,
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


def retrieve_rules_and_generate_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Retrieve ingredient combination rules from Pinecone and generate menu."""
    print("[STEP] retrieve_rules_and_generate_menu: Starting...")
    # Check for errors from previous steps
    if state.get("error"):
        print("[STEP] retrieve_rules_and_generate_menu: Error detected in state, skipping")
        return state
    
    try:
        intent = state.get("intent", {})
        cuisine = intent.get("cuisine", "Việt")
        budget = intent.get("budget", 200000)
        
        ingredients = state.get("available_ingredients", [])
        ingredient_names = [ing["name"] for ing in ingredients]
        
        print(f"[STEP] retrieve_rules_and_generate_menu: Querying Pinecone for {cuisine} cuisine combination rules...")
        vector_store = get_vector_store_service()
        combination_rules = vector_store.query_combination_rules(
            cuisine_type=cuisine,
            ingredients=ingredient_names,
            top_k=5
        )
        state["combination_rules"] = combination_rules
        print(f"[STEP] retrieve_rules_and_generate_menu: Pinecone returned {len(combination_rules)} combination rules")
        
        print(f"[STEP] retrieve_rules_and_generate_menu: Generating menu with LLM using combination rules...")
        llm_service = get_llm_service()
        menu, usage_info = llm_service.generate_menu(
            ingredients=ingredients,
            context=combination_rules,
            cuisine=cuisine,
            budget=budget
        )
        state["generated_menu"] = menu
        if "llm_usage" not in state:
            state["llm_usage"] = []
        state["llm_usage"].append({"operation": "generate_menu", **usage_info})
        
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


# Removed validate_node and adjust_menu_node - no longer needed with combination rules approach


def build_response_node(state: MenuGraphState) -> MenuGraphState:
    """Build final response."""
    print("[STEP] build_response: Starting...")
    try:
        menu = state.get("generated_menu", {})
        intent = state.get("intent", {})
        cuisine = intent.get("cuisine", "Việt")
        
        response = {
            "menu_items": menu.get("items", []),
            "total_price": menu.get("total_price", 0),
            "cuisine_type": cuisine
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
            "cuisine_type": ""
        }
    return state

