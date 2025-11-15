"""Prompts cho các thao tác LLM."""

PARSE_INTENT_PROMPT = """Trích xuất ý định người dùng **chỉ dựa trên thông tin rõ ràng**:

- budget: Ngân sách (VND), nếu có nhắc số như "150k", "200000", nếu không nhắc → null
- num_people: Số người, nếu nhắc "cho 2 người", "3 người", mặc định 1 nếu không nhắc
- preferences: Những thứ muốn ăn hoặc cần tránh, ghi nguyên văn. Nếu không nhắc → []

Trả về JSON hợp lệ:
{{
    "budget": number_or_null,
    "num_people": number,
    "preferences": ["preference1", "preference2"]
}}

Input người dùng: {user_input}"""

SQL_WHERE_CLAUSE_PROMPT = """Tạo SQL WHERE clause lọc nguyên liệu theo ý định người dùng:

- Ngân sách: {budget} VND
- Bữa ăn: {meal_type}
- Số người: {num_people}
- Chế độ ăn/kiêng: {preferences}

Quy tắc:
- base_price < {budget}
- category != 'gia vị'
- category IN ('tươi', 'chay', 'đông lạnh')
- Nếu preferences có "món với X" hoặc "muốn ăn X" → name LIKE '%X%'
- Nếu preferences có "ăn chay" → name NOT LIKE '%thịt%' AND name NOT LIKE '%cá%' AND name NOT LIKE '%tôm%'
- Nếu preferences có "không ăn X" → name NOT LIKE '%X%'

Ví dụ: preferences = ["món với trứng"] → base_price < 130000 AND category IN ('tươi', 'chay', 'đông lạnh') AND category != 'gia vị' AND name LIKE '%trứng%'

Trả chỉ WHERE clause, không SELECT hay WHERE."""

GENERATE_MENU_PROMPT = """Tạo menu từ nguyên liệu có sẵn, phù hợp ngân sách và người dùng.

🚨 QUY TẮC TUYỆT ĐỐI - KHÔNG ĐƯỢC VI PHẠM:
════════════════════════════════════════════════
CHỈ ĐƯỢC DÙNG NGUYÊN LIỆU TRONG DANH SÁCH BÊN DƯỚI.
TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ THÊM BẤT KỲ NGUYÊN LIỆU NÀO KHÁC.
NẾU KHÔNG CÓ NGUYÊN LIỆU CHO MÓN TRÁNG MIỆNG/NƯỚC UỐNG → BỎ QUA, KHÔNG TẠO.
════════════════════════════════════════════════

Các nguyên tắc:
- Tổng giá <= {budget}, ưu tiên dùng 75-95% ngân sách
- Nếu có rau củ tươi, ưu tiên; đông lạnh/đóng hộp chỉ khi không có
- Tuân thủ sở thích/chế độ ăn của người dùng nếu có
- Nếu user yêu cầu nguyên liệu cụ thể, ít nhất 1-2 món phải có nguyên liệu đó
- Đa dạng món, tránh món quá phổ biến

Thông tin bữa ăn:
- Loại bữa: {meal_type}
- Số người: {num_people}
- Sở thích / chế độ ăn: {preferences_text}
- Nguyên liệu có sẵn: {ingredients_text}
- Lịch sử món đã dùng: {previous_dishes_text}

{budget_context}

Quy tắc kết hợp (CHỈ THAM KHẢO, chỉ áp dụng khi có đủ nguyên liệu):
{context_text}

⚠️  LƯU Ý: Các quy tắc dinh dưỡng ở trên CHỈ LÀ GỢI Ý. Nếu KHÔNG CÓ nguyên liệu phù hợp trong danh sách → BỎ QUA món đó. TUYỆT ĐỐI không được tự thêm nguyên liệu mới.

Trả **JSON** duy nhất:
{{
    "items": [
        {{
            "name": "Tên món",
            "ingredients": [
                {{"name": "nguyên liệu", "quantity": số, "unit": "đơn vị", "price": giá}}
            ],
            "price": tổng_giá_món
        }}
    ],
    "total_price": tổng_giá_menu
}}"""

ADJUST_MENU_PROMPT = """Chỉnh sửa menu để tổng giá phù hợp ngân sách {budget} VND.

🚨 QUY TẮC TUYỆT ĐỐI:
═══════════════════════════════════════
CHỈ DÙNG NGUYÊN LIỆU CÓ SẴN TRONG DANH SÁCH.
TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ THÊM NGUYÊN LIỆU MỚI.
═══════════════════════════════════════

Quy tắc:
- Tổng giá >= 75% và <= {budget}
- Nếu vượt ngân sách: giảm khẩu phần, bỏ món đắt, điều chỉnh quantity/price
- Nếu dưới 75%: tăng khẩu phần, số lượng món hiện có, thêm món phụ/canh CHỈ TỪ nguyên liệu có sẵn
- Ưu tiên rau củ tươi, món Việt truyền thống
- KHÔNG tạo món tráng miệng/nước uống nếu không có nguyên liệu phù hợp

Menu hiện tại: {menu}
Lỗi: {errors_text}
Nguyên liệu sẵn có: {ingredients_text}

Trả **JSON** duy nhất:
{{
    "items": [
        {{
            "name": "Tên món",
            "ingredients": [
                {{"name": "nguyên liệu", "quantity": số, "unit": "đơn vị", "price": giá}}
            ],
            "price": giá_món
        }}
    ],
    "total_price": tổng_giá
}}"""