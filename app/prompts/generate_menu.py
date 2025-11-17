"""Prompt for generating menu from products and combination rules."""

GENERATE_MENU_PROMPT = """Tạo menu Việt Nam từ danh sách sản phẩm và quy tắc kết hợp.

**THÔNG TIN ĐẦU VÀO:**
- Loại bữa: {meal_type}
- Số người: {num_people}
- Ngân sách: {budget} VND
- Sở thích: {preferences_text}
- Lịch sử món: {previous_dishes_text}

{budget_context}

**🚨 DANH SÁCH SẢN PHẨM BẮT BUỘC (BẮT BUỘC PHẢI DÙNG):**
{products_text}

⚠️ **QUY TẮC TUYỆT ĐỐI - KHÔNG ĐƯỢC VI PHẠM:**
- CHỈ ĐƯỢC DÙNG các sản phẩm trong danh sách trên
- TUYỆT ĐỐI PHẢI DÙNG product_id CHÍNH XÁC từ danh sách (ví dụ: prod_001, prod_010)
- KHÔNG được tự tạo product_id, KHÔNG được dùng tên sản phẩm thay cho product_id
- Nếu không có sản phẩm phù hợp trong danh sách → KHÔNG tạo món đó, chọn món khác

**QUY TẮC KẾT HỢP:**
{combination_rules}

**NHIỆM VỤ:**
Dựa vào danh sách sản phẩm BẮT BUỘC và quy tắc kết hợp, tạo menu phù hợp với:
1. Budget constraints
2. Meal type structure
3. Ingredient pairing logic
4. User preferences

**YÊU CẦU OUTPUT:**
Trả về JSON với format:
{{
    "items": [
        {{
            "name": "Tên món ăn",
            "ingredients": [
                {{"product_id": "prod_XXX", "name": "Tên sản phẩm CHÍNH XÁC từ danh sách", "quantity": số_lượng, "unit": "đơn_vị", "price": giá}}
            ],
            "price": tổng_giá_món
        }}
    ],
    "total_price": tổng_giá_menu
}}

**LƯU Ý QUAN TRỌNG:**
- product_id trong ingredients PHẢI CHÍNH XÁC từ danh sách trên (ví dụ: prod_001, prod_010)
- name trong ingredients PHẢI CHÍNH XÁC với tên sản phẩm tương ứng trong danh sách (không được tự chế / viết tắt)
- KHÔNG được dùng name thay cho product_id, cả 2 field đều BẮT BUỘC PHẢI ĐÚNG
- Tên món ăn có thể tự do nhưng ingredient phải dùng product_id + name chuẩn
- Price sẽ được cập nhật sau, có thể để 0
"""

