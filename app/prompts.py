"""Prompts for LLM operations."""

PARSE_INTENT_PROMPT = """You are an intent parser for a menu suggestion system.
Extract the following information from user input:
- cuisine: Type of cuisine (e.g., "Hàn", "Việt", "Nhật", etc.). Default to "Việt" if not specified.
- budget: Budget amount in VND. Extract numbers mentioned. Default to 200000 if not specified.
- preferences: Any dietary preferences or restrictions mentioned.

Return ONLY a valid JSON object with keys: cuisine, budget, preferences.

User input: {user_input}"""

GENERATE_MENU_PROMPT = """You are a menu planning expert. Generate a complete menu by applying ingredient combination rules to available ingredients.

CRITICAL BUDGET CONSTRAINT: The TOTAL PRICE of ALL dishes MUST NOT exceed {budget} VND. This is ABSOLUTE and NON-NEGOTIABLE.

Your task (in this exact order):
1. FIRST: Read the base price (price per unit) of each available ingredient from the list
2. SECOND: Use combination rules to identify possible dishes
3. THIRD: For each possible dish, calculate total cost BEFORE adding it to menu
4. FOURTH: Only select dishes whose total cost keeps you UNDER the budget limit
5. FIFTH: Verify total_price <= {budget} VND before returning

PRICE CALCULATION RULES (MANDATORY):
- Each ingredient shows "Giá mỗi [unit]: X VND" which is the BASE PRICE per unit
- To calculate ingredient cost: ingredient_cost = base_price_per_unit × quantity_used
- Example: If "thịt heo" has "Giá mỗi g: 300 VND", using 200g costs = 300 × 200 = 60,000 VND
- Example: If "bánh mì" has "Giá mỗi ổ: 5000 VND", using 2 ổ costs = 5000 × 2 = 10,000 VND
- Each dish price = sum of all ingredient costs in that dish
- Total menu price = sum of all dish prices

BUDGET CHECK PROCESS:
1. Before selecting ANY ingredient, calculate: ingredient_cost = price × quantity
2. Before adding ANY dish, calculate: dish_total = sum of all ingredient costs
3. Before finalizing menu, calculate: menu_total = sum of all dish totals
4. If menu_total > {budget}, REMOVE dishes or REDUCE quantities until menu_total <= {budget}
5. If you cannot create any dish within budget, return empty menu with total_price = 0

The menu should include (only if within budget):
- Main dish (món chính) - REQUIRED if possible
- Side dish (món phụ) - OPTIONAL
- Soup (canh) - OPTIONAL

Return ONLY a valid JSON object with this structure:
{{
    "items": [
        {{
            "name": "Dish name",
            "ingredients": [
                {{"name": "ingredient name", "quantity": number, "unit": "g|kg|ml|etc", "price": calculated_price_in_vnd}}
            ],
            "price": sum_of_ingredient_prices_in_vnd
        }}
    ],
    "total_price": sum_of_all_dish_prices_in_vnd
}}

VERIFICATION CHECKLIST (MUST PASS ALL):
✓ Every ingredient price = (price_per_unit from list) × quantity_used
✓ Every dish price = sum of ingredient prices in that dish
✓ total_price = sum of all dish prices
✓ total_price <= {budget} VND
✓ All ingredients exist in available list
✓ All quantities <= available stock quantities

EXAMPLE CALCULATION (Budget: 100,000 VND):
- If "cá basa" costs 200 VND/g, using 200g = 200 × 200 = 40,000 VND (OK)
- If "thịt heo" costs 300 VND/g, using 150g = 300 × 150 = 45,000 VND (OK)
- If "rau muống" costs 30 VND/g, using 100g = 30 × 100 = 3,000 VND (OK)
- Total for 3 dishes = 40,000 + 45,000 + 3,000 = 88,000 VND (UNDER 100k budget - GOOD!)
- If "cá hồi" costs 1167 VND/g, using 200g = 1167 × 200 = 233,400 VND (TOO EXPENSIVE - REJECT)
- Strategy: For small budgets, choose cheaper ingredients (thịt gà, cá basa, rau) and use reasonable portions

Cuisine type: {cuisine}
Budget: {budget} VND (MAXIMUM - DO NOT EXCEED - THIS IS A HARD LIMIT)

Available ingredients:
{ingredients_text}

Ingredient combination rules:
{context_text}

Generate a menu by applying these rules. REMEMBER: total_price MUST be <= {budget} VND."""

ADJUST_MENU_PROMPT = """You are a menu adjustment expert. Adjust the menu to fit within budget constraints.

Your task:
1. Identify which dishes or ingredients are too expensive
2. Apply one or more strategies:
   - Reduce quantities of expensive ingredients (especially protein)
   - Replace expensive ingredients with cheaper alternatives (e.g., cá hồi → cá basa, thịt bò → thịt gà)
   - Remove optional dishes (side dishes, soup) and keep only main dish
   - Use smaller portions
3. Ensure total_price <= {budget} VND

PRICE CALCULATION (MANDATORY):
- Each ingredient has base_price per unit shown as "Giá mỗi [unit]: X VND"
- Calculate: ingredient_cost = base_price × quantity_used
- Example: "thịt heo" costs 300 VND/g, using 100g = 300 × 100 = 30,000 VND
- Dish price = sum of all ingredient costs
- Total price = sum of all dish prices

Return ONLY a valid JSON object with this structure:
{{
    "items": [
        {{
            "name": "Dish name",
            "ingredients": [
                {{"name": "ingredient name", "quantity": number, "unit": "g|kg|ml|etc", "price": calculated_price}}
            ],
            "price": dish_total_price
        }}
    ],
    "total_price": menu_total_price
}}

Current menu (OVER BUDGET):
{menu}

Budget error:
{errors_text}

Available ingredients:
{ingredients_text}

Budget limit: {budget} VND (MUST NOT EXCEED)

Adjust the menu:"""

