"""Prompt cho việc điều chỉnh menu từ RAG (RAG v2)."""

ADJUST_MENU_FROM_RAG_PROMPT = """Điều chỉnh menu bằng cách thay thế/thêm bớt món từ RAG recipes.

**QUY TẮC:**
- Budget: {budget} VND
- Target: 75% <= Total <= {budget} VND
- Max retries: 3

**CHIẾN LƯỢC:**

*Nếu vượt budget:*
- Bỏ món đắt nhất
- Thay bằng món rẻ hơn từ RAG recipes
- Giảm khẩu phần

*Nếu dưới 75% budget:*
- Thêm món từ RAG recipes  
- Tăng khẩu phần món hiện có

*Nếu hết stock:*
- Thay bằng món tương đương từ RAG recipes
- Nguyên liệu hết stock: {out_of_stock}

**MENU HIỆN TẠI:**
{menu}

**LỖI CẦN SỬA:**
{errors_text}

**RAG RECIPES KHẢ DỤNG:**
{rag_recipes_text}

**OUTPUT JSON:**
{{
    "items": [
        {{
            "name": "Tên món",
            "ingredients": [
                {{"name": "nguyên liệu", "quantity": số, "unit": "đơn_vị", "price": 0}}
            ],
            "price": 0
        }}
    ],
    "total_price": 0
}}

**LƯU Ý:** Price = 0 là OK, sẽ được tính lại sau.
"""

