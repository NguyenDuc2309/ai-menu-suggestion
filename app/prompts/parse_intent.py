"""Prompt cho việc trích xuất ý định người dùng."""

PARSE_INTENT_PROMPT = """Trích xuất ý định người dùng **chỉ dựa trên thông tin rõ ràng**:

**CÁC TRƯỜNG CẦN TRÍCH XUẤT:**
- budget: Ngân sách (VND). Ví dụ: "150k" → 150000, "200 nghìn" → 200000. Nếu không nhắc → null
- num_people: Số người ăn. Ví dụ: "cho 2 người" → 2, "3 người ăn" → 3. Mặc định: 1
- preferences: Sở thích/yêu cầu về món ăn, ghi nguyên văn. Ví dụ: ["gà", "trứng", "ăn chay"]. Nếu không nhắc → []

**YÊU CẦU OUTPUT:**
Trả về JSON chính xác theo format:
{{
    "budget": number_or_null,
    "num_people": number,
    "preferences": ["preference1", "preference2"]
}}

**INPUT:** {user_input}"""

