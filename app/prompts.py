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
1. FIRST: Calculate the cost of each available ingredient per unit from the list
2. SECOND: Use combination rules to identify possible dishes
3. THIRD: For each possible dish, calculate total cost BEFORE adding it to menu
4. FOURTH: Only select dishes whose total cost keeps you UNDER the budget limit
5. FIFTH: Verify total_price <= {budget} VND before returning

PRICE CALCULATION RULES (MANDATORY):
- Each ingredient has a "price" field which is the price PER UNIT (per gram/ml/etc)
- To calculate ingredient cost: ingredient_cost = price_per_unit × quantity_used
- Example: If "cá basa" has price: 100000 VND per gram, and you use 200g, then cost = 100000 × 200 = 20,000,000 VND
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
- If "cá basa" costs 100,000 VND per gram, using 200g = 100,000 × 200 = 20,000,000 VND (TOO EXPENSIVE - REJECT)
- If "cá basa" costs 100,000 VND per gram, using 0.5g = 100,000 × 0.5 = 50,000 VND (OK if other dishes fit remaining 50,000)
- If "hành lá" costs 15,000 VND per gram, using 5g = 15,000 × 5 = 75,000 VND (TOO EXPENSIVE for small budget)
- If "hành lá" costs 15,000 VND per gram, using 1g = 15,000 × 1 = 15,000 VND (OK)
- Strategy: For small budgets, use TINY quantities of expensive ingredients or choose cheaper alternatives

Cuisine type: {cuisine}
Budget: {budget} VND (MAXIMUM - DO NOT EXCEED - THIS IS A HARD LIMIT)

Available ingredients:
{ingredients_text}

Ingredient combination rules:
{context_text}

Generate a menu by applying these rules. REMEMBER: total_price MUST be <= {budget} VND."""

ADJUST_MENU_PROMPT = """You are a menu adjustment expert. Adjust the menu to fix validation errors.
You can:
- Reduce quantities of ingredients
- Replace ingredients with available alternatives
- Remove dishes if necessary
- Ensure total price <= budget

Return ONLY a valid JSON object with the same structure as the input menu:
{{
    "items": [
        {{
            "name": "Dish name",
            "ingredients": [
                {{"name": "ingredient name", "quantity": number, "unit": "g|kg|ml|etc", "price": price_in_vnd}}
            ],
            "price": estimated_price_in_vnd
        }}
    ],
    "total_price": total_price_in_vnd
}}

IMPORTANT:
- Calculate price for each ingredient: price = (price_per_unit from available list) * quantity_used
- Example: If hành lá costs 75 VND per gram (15000 VND per gram in stock), then 20g costs 75 * 20 = 1500 VND
- Each dish's price should be the sum of all ingredient prices used in that dish

Current menu:
{menu}

Validation errors:
{errors_text}

Available ingredients:
{ingredients_text}

Budget: {budget} VND

Adjust the menu:"""

