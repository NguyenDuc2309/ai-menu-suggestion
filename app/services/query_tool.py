"""Query tool for database operations.
Generates SQL from intent and applies to data."""
import json
import os
import re
from typing import List, Dict, Any


def apply_sql_filter(where_clause: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply SQL WHERE clause logic to mockup data using pure Python."""
    if not where_clause:
        return data
    
    print(f"[FILTER] Applying WHERE: {where_clause[:150]}...")
    
    conditions = re.split(r'\s+AND\s+', where_clause, flags=re.IGNORECASE)
    filtered = []
    
    for item in data:
        name_lower = item.get("name", "").lower()
        base_price = item.get("base_price", 0)
        category = item.get("category", "").lower()
        
        match = True
        
        for cond in conditions:
            cond = cond.strip().strip('()')
            
            # base_price conditions
            if 'base_price' in cond.lower():
                if '<=' in cond:
                    m = re.search(r'base_price\s*<=\s*(\d+)', cond, re.IGNORECASE)
                    if m and base_price > float(m.group(1)):
                        match = False
                        break
                elif '>=' in cond:
                    m = re.search(r'base_price\s*>=\s*(\d+)', cond, re.IGNORECASE)
                    if m and base_price < float(m.group(1)):
                        match = False
                        break
            
            # category conditions
            elif 'category' in cond.lower():
                if 'NOT IN' in cond.upper():
                    m = re.search(r"category\s+NOT\s+IN\s*\(([^)]+)\)", cond, re.IGNORECASE)
                    if m:
                        excluded = [c.strip().strip("'\"").lower() for c in m.group(1).split(',')]
                        if category in excluded:
                            match = False
                            break
                elif '!=' in cond or '<>' in cond:
                    m = re.search(r"category\s*(?:!=|<>)\s*['\"]?([^'\"]+)['\"]?", cond, re.IGNORECASE)
                    if m and category == m.group(1).strip().lower():
                        match = False
                        break
                elif 'IN' in cond.upper():
                    m = re.search(r"category\s+IN\s*\(([^)]+)\)", cond, re.IGNORECASE)
                    if m:
                        allowed = [c.strip().strip("'\"").lower() for c in m.group(1).split(',')]
                        if category not in allowed:
                            match = False
                            break
                elif '=' in cond:
                    m = re.search(r"category\s*=\s*['\"]?([^'\"]+)['\"]?", cond, re.IGNORECASE)
                    if m and category != m.group(1).strip().lower():
                        match = False
                        break
            
            # name conditions
            elif 'name' in cond.lower():
                if 'NOT LIKE' in cond.upper():
                    m = re.search(r"name\s+NOT\s+LIKE\s+['\"]([^'\"]+)['\"]", cond, re.IGNORECASE)
                    if m:
                        sql_pattern = m.group(1)
                        # Convert SQL LIKE pattern to regex
                        # %text% → contains, text% → starts with, %text → ends with, text → exact
                        regex_pattern = sql_pattern
                        if not regex_pattern.startswith('%'):
                            regex_pattern = '^' + regex_pattern  # Must start from beginning
                        if not regex_pattern.endswith('%'):
                            regex_pattern = regex_pattern + '$'  # Must end at end
                        regex_pattern = regex_pattern.replace('%', '.*')  # % → any chars
                        
                        if re.search(regex_pattern, name_lower, re.IGNORECASE):
                            match = False
                            break
                elif 'LIKE' in cond.upper():
                    m = re.search(r"name\s+LIKE\s+['\"]([^'\"]+)['\"]", cond, re.IGNORECASE)
                    if m:
                        sql_pattern = m.group(1)
                        regex_pattern = sql_pattern
                        if not regex_pattern.startswith('%'):
                            regex_pattern = '^' + regex_pattern
                        if not regex_pattern.endswith('%'):
                            regex_pattern = regex_pattern + '$'
                        regex_pattern = regex_pattern.replace('%', '.*')
                        
                        # MUST match to keep this item
                        if not re.search(regex_pattern, name_lower, re.IGNORECASE):
                            match = False
                            break
                elif 'NOT IN' in cond.upper():
                    m = re.search(r"name\s+NOT\s+IN\s*\(([^)]+)\)", cond, re.IGNORECASE)
                    if m:
                        excluded = [n.strip().strip("'\"").lower() for n in m.group(1).split(',')]
                        if name_lower in excluded:
                            match = False
                            break
        
        if match:
            filtered.append(item)
    
    print(f"[FILTER] Filtered from {len(data)} to {len(filtered)} ingredients")
    return filtered


class QueryTool:
    """Tool for querying ingredients with SQL generation.
    
    Flow:
    1. Receive intent (budget, meal_type, num_people, preferences)
    2. Generate SQL query using LLM from intent
    3. Log SQL for future DB integration
    4. Apply SQL filter to mockup data (current) / Execute on real DB (future)
    5. Return filtered ingredients
    
    This maximizes filtering to reduce data sent to LLM.
    """
    
    def __init__(self):
        """Initialize query tool."""
        self._mockup_data_path = None
        self._cached_mockup_data = None
    
    def _load_mockup_data(self) -> List[Dict[str, Any]]:
        """Load mockup ingredient data from JSON file."""
        if self._cached_mockup_data is not None:
            return self._cached_mockup_data
        
        if self._mockup_data_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            self._mockup_data_path = os.path.join(
                current_dir, "..", "data", "mock_ingredients.json"
            )
        
        try:
            with open(self._mockup_data_path, "r", encoding="utf-8") as f:
                mockup_data = json.load(f)
            self._cached_mockup_data = mockup_data
            print(f"[TOOL] Loaded {len(mockup_data)} ingredients")
            return mockup_data
        except FileNotFoundError:
            raise ValueError(f"Mock ingredients file not found: {self._mockup_data_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing mockup JSON file: {str(e)}")
    
    def _generate_sql_from_intent(self, intent: Dict[str, Any]) -> str:
        """Generate SQL WHERE clause from intent using LLM."""
        from app.services.llm_service import get_llm_service
        
        budget = intent.get("budget", 0)
        meal_type = intent.get("meal_type", "")
        num_people = intent.get("num_people", 1)
        preferences = intent.get("preferences", [])
        
        try:
            llm_service = get_llm_service()
            sql = llm_service.generate_sql_where_clause(
                budget=budget,
                meal_type=meal_type,
                num_people=num_people,
                preferences=preferences
            )
            print(f"[SQL] Generated: {sql[:200]}")
            return sql
        except Exception as e:
            print(f"[SQL] Generation failed: {e}, using fallback")
            return self._fallback_sql(budget, num_people, preferences)
    
    def _fallback_sql(self, budget: int, num_people: int, preferences: List[str]) -> str:
        """Fallback SQL generation - only basic filters when LLM fails.
        
        LLM is responsible for handling preferences flexibly.
        Fallback only provides: budget + category + exclude condiments.
        """
        conditions = []
        
        # Budget filter - chỉ loại trừ nguyên liệu đắt hơn budget tổng
        if budget > 0:
            conditions.append(f"base_price < {budget}")
        
        # Category filter (prefer fresh, exclude condiments)
        conditions.append("category IN ('tươi', 'chay', 'đông lạnh')")
        conditions.append("category != 'gia vị'")
        
        where_clause = " AND ".join(conditions)
        print(f"[SQL] Fallback (basic filters only, preferences skipped): {where_clause}")
        return where_clause
    
    def query_ingredients(self, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query ingredients based on intent.
        
        1. Load mockup data
        2. Generate SQL from intent via LLM
        3. Apply SQL filter to mockup data
        4. Return filtered ingredients
        
        Args:
            intent: Dict with budget, meal_type, num_people, preferences
            
        Returns:
            Filtered list of ingredients
        """
        # Load data
        all_data = self._load_mockup_data()
        
        if not intent:
            print("[TOOL] No intent, returning all data")
            return all_data
        
        preferences = intent.get("preferences", []) or []
        
        # Generate SQL WHERE clause from intent
        where_clause = self._generate_sql_from_intent(intent)
        
        # Apply filter
        filtered_data = apply_sql_filter(where_clause, all_data)
        
        print(f"[TOOL] Query complete: {len(filtered_data)} ingredients returned")
        return filtered_data


_query_tool = None


def get_query_tool() -> QueryTool:
    """Get or create query tool instance."""
    global _query_tool
    if _query_tool is None:
        _query_tool = QueryTool()
    return _query_tool

