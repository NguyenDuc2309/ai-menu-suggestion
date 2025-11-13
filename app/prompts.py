"""Prompts for LLM operations."""

PARSE_INTENT_PROMPT = """You are an intent parser for a menu suggestion system.
Extract the following information from user input:
- budget: Budget amount in VND. Extract numbers mentioned. Default to 200000 if not specified.
- budget_specified: Boolean, true if user explicitly mentioned budget, false if using default. This helps AI choose appropriate dishes.
- meal_type: Type of meal (sáng, trưa, tối). Default to "trưa" if not specified.
- num_people: Number of people. Default to 1 if not specified.
- preferences: Any dietary preferences or restrictions mentioned.

Return ONLY a valid JSON object with keys: budget, budget_specified, meal_type, num_people, preferences.

Examples:
- "Hôm nay ăn gì với 150k" → budget_specified: true
- "Gợi ý bữa trưa" → budget_specified: false (using default 200k)

User input: {user_input}"""

GENERATE_MENU_PROMPT = """BẠN LÀ CHUYÊN GIA LẬP THỰC ĐƠN. Nhiệm vụ: Từ nguyên liệu có sẵn, tạo menu phù hợp với NGÂN SÁCH và người dùng.

════════════════════════════════════════════════════════════════════════════════
⚠️  CÁC QUY TẮC QUAN TRỌNG
════════════════════════════════════════════════════════════════════════════════

🔴 QUY TẮC 1: NGÂN SÁCH QUYẾT ĐỊNH SỐ MÓN (BẮT BUỘC)
- Tổng giá PHẢI <= {budget} VND (TUYỆT ĐỐI không vượt)
- TARGET: Cố gắng sử dụng 70-85% ngân sách (không để dư quá nhiều, tận dụng tối đa trong giới hạn)
- SỐ MÓN PHỤ THUỘC NGÂN SÁCH, KHÔNG BẮT BUỘC 3-5 MÓN:
  
  • Ngân sách 40-70k: CHỈ 1-2 MÓN đơn giản
    Ví dụ: 1 bát phở (35-50k), 1 tô bún (30-45k), 1 dĩa cơm gà (40-60k)
    → Target: ~40-60k (70-85% của 40-70k)
  
  • Ngân sách 70-150k: 2-3 món (1 món chính + 1 món phụ hoặc canh)
    Ví dụ: Cơm + thịt kho + rau xào
    → Target: ~80-130k (70-85% của 70-150k)
  
  • Ngân sách 150-300k: 3-4 món (1 món chính + món phụ + canh)
    Ví dụ: Cơm + cá kho + rau + canh
    → Target: ~130-250k (70-85% của 150-300k)
  
  • Ngân sách > 300k: 4-5 món đa dạng
    Có thể thêm món phụ, canh, rau nếu còn dư ngân sách
    → Target: ~70-85% của ngân sách

- TRÁNG MIỆNG và ĐỒ UỐNG: KHÔNG BẮT BUỘC
  → CHỈ thêm nếu sau khi có đủ món chính/phụ/canh và vẫn còn dư ≥ 30k (để đạt target 70-85%)
  → ĐỒ UỐNG PHẢI LÀ SẢN PHẨM ĐÓNG GÓI SẴN (lon, hộp): nước ngọt, nước suối, trà đóng chai, cà phê lon, sữa hộp...
  → TUYỆT ĐỐI KHÔNG chế biến đồ uống từ nguyên liệu (ví dụ: KHÔNG làm "Sữa đậu nành" từ đậu nành + sữa tươi)
  → Có thể gợi ý mua hoa quả để làm đồ uống hoặc tráng miệng 
  → Đồ uống phải có giá cố định như sản phẩm đóng gói (10-25k/lon/hộp)

🔴 QUY TẮC 2: TUÂN THỦ QUY TẮC KẾT HỢP NGUYÊN LIỆU (NẾU CÓ)
- Các quy tắc kết hợp nguyên liệu bên dưới chỉ là GỢI Ý, không bắt buộc nếu ngân sách thấp
- Ưu tiên ngân sách trước, quy tắc sau
- Ví dụ: "ăn sáng không ăn cơm" → NÊN tránh cơm, nhưng nếu ngân sách thấp có thể linh hoạt

🔴 QUY TẮC 3: CHỈ SỬ DỤNG NGUYÊN LIỆU CHÍNH (BẮT BUỘC)
- Danh sách đã loại bỏ gia vị (muối, đường, dầu, nước mắm, tỏi, ớt...)
- CHỈ gợi ý nguyên liệu CHÍNH: thịt, cá, rau, trứng, đậu phụ, tinh bột
- KHÔNG thêm gia vị vào món ăn

🟡 KHUYẾN NGHỊ: ĐA DẠNG HÓA MÓN ĂN (NẾU NGÂN SÁCH CHO PHÉP)
- Hãy sáng tạo và đa dạng hóa món ăn khi có đủ ngân sách
- Tránh các món quá phổ biến: "Bánh mì thịt nướng", "Cơm cá basa kho tộ"
- Ưu tiên món Việt Nam: thịt kho trứng, cá kho tiêu, gà xào sả, bò lúc lắc, mực xào chua ngọt, canh chua, canh bí...
- Đa dạng protein (thịt heo, gà, bò, cá, tôm, mực), phương pháp (kho, xào, rim, hấp, nướng)

{previous_dishes_text}

════════════════════════════════════════════════════════════════════════════════
📋 THÔNG TIN BỮA ĂN VÀ NGUYÊN LIỆU
════════════════════════════════════════════════════════════════════════════════

Loại bữa: {meal_type}
Số người: {num_people}
Ngân sách: {budget} VND (KHÔNG được vượt - đây là ưu tiên số 1)
{budget_context}

NGUYÊN LIỆU CÓ SẴN (đã loại bỏ gia vị, đã xáo trộn để tăng độ đa dạng):
{ingredients_text}

════════════════════════════════════════════════════════════════════════════════
📖 QUY TẮC KẾT HỢP NGUYÊN LIỆU (THAM KHẢO - KHÔNG BẮT BUỘC NẾU NGÂN SÁCH THẤP)
════════════════════════════════════════════════════════════════════════════════

{context_text}

════════════════════════════════════════════════════════════════════════════════
🎯 HƯỚNG DẪN TẠO MENU THEO NGÂN SÁCH
════════════════════════════════════════════════════════════════════════════════

BƯỚC 1: ĐÁNH GIÁ NGÂN SÁCH
- Xác định ngân sách thuộc khoảng nào (40-70k, 70-150k, 150-300k, >300k)
- Quyết định số món phù hợp (1-5 món)

BƯỚC 2: CHỌN MÓN ƯU TIÊN
- Ngân sách thấp (<70k): Chọn 1 món no bụng, đơn giản (phở, bún, cơm gà)
- Ngân sách trung bình: Chọn món chính trước, sau đó món phụ/canh
- Ngân sách cao: Đa dạng hóa món ăn

BƯỚC 3: TỐI ƯU NGÂN SÁCH (QUAN TRỌNG)
- Tính tổng giá từng món: price = base_price × quantity
- Đảm bảo tổng giá <= {budget} VND
- TARGET: Cố gắng đạt 70-85% ngân sách (ví dụ: budget 50k → target 35-42k, budget 200k → target 140-170k)
- Cách đạt target:
  • Tăng khẩu phần protein/rau nếu còn dư nhiều
  • Thêm 1 món phụ/canh nếu budget cho phép
  • Thêm tráng miệng/đồ uống nếu còn dư ≥ 30k sau khi có đủ món chính
  • ĐỒ UỐNG: CHỈ thêm sản phẩm đóng gói sẵn (lon/hộp) với giá cố định 10-25k, KHÔNG chế biến từ nguyên liệu
- KHÔNG thêm quá nhiều nếu user không yêu cầu cụ thể về số lượng

BƯỚC 4: ĐA DẠNG HÓA (nếu ngân sách cho phép)
- Thử protein khác nhau, phương pháp khác nhau
- Tránh món lặp lại với lịch sử người dùng

════════════════════════════════════════════════════════════════════════════════
📤 FORMAT RESPONSE (CHỈ TRẢ VỀ JSON)
════════════════════════════════════════════════════════════════════════════════

{{
    "items": [
        {{
            "name": "Tên món ăn",
            "ingredients": [
                {{"name": "tên nguyên liệu", "quantity": số_lượng, "unit": "đơn_vị", "price": giá_tính_toán}}
            ],
            "price": tổng_giá_món
        }}
    ],
    "total_price": tổng_giá_menu
}}"""

ADJUST_MENU_PROMPT = """CHỈNH SỬA MENU ĐỂ PHÙ HỢP NGÂN SÁCH.

⚠️  QUY TẮC BẮT BUỘC:
- CHỈ sử dụng nguyên liệu CHÍNH từ danh sách (thịt, cá, rau, tinh bột)
- KHÔNG thêm gia vị (muối, đường, dầu, nước mắm, xì dầu, tỏi, ớt...)
- Tổng giá PHẢI <= {budget} VND
- SỐ MÓN PHỤ THUỘC NGÂN SÁCH, có thể giảm xuống 1-2 món nếu ngân sách thấp

💡 KHUYẾN NGHỊ KHI ĐIỀU CHỈNH:
- Nếu có thể, hãy thay đổi món ăn thay vì chỉ giảm khẩu phần
- Thử các món khác đa dạng hơn với nguyên liệu rẻ hơn
- Ưu tiên món ăn gia đình Việt Nam truyền thống
- BỎ tráng miệng/đồ uống trước tiên nếu có

CHIẾN LƯỢC ĐIỀU CHỈNH (theo thứ tự ưu tiên):
1. Bỏ tráng miệng và đồ uống (nếu có) - đồ uống là sản phẩm đóng gói sẵn, dễ bỏ nhất
2. Giảm số lượng món nếu ngân sách quá thấp (có thể chỉ còn 1-2 món)
3. Thay món đắt bằng món rẻ hơn (cá hồi → cá basa, thịt bò → thịt gà/heo)
4. Giảm khẩu phần protein
5. Bỏ món phụ/canh nếu thực sự cần thiết, chỉ giữ món chính

⚠️  LƯU Ý VỀ ĐỒ UỐNG:
- Đồ uống PHẢI là sản phẩm đóng gói sẵn (lon, hộp): nước ngọt, nước suối, trà đóng chai, cà phê lon, sữa hộp...
- TUYỆT ĐỐI KHÔNG chế biến đồ uống từ nguyên liệu (ví dụ: KHÔNG làm "Sữa đậu nành" từ đậu nành + sữa tươi)
- KHÔNG gợi ý mua hoa quả để làm đồ uống
- Đồ uống có giá cố định: 10-25k/lon/hộp (không tính từ nguyên liệu)

TÍNH GIÁ:
- ingredient_cost = base_price × quantity
- Dish price = tổng giá nguyên liệu
- Total price = tổng giá món

MENU HIỆN TẠI (QUÁ NGÂN SÁCH):
{menu}

LỖI:
{errors_text}

NGUYÊN LIỆU CÓ SẴN (ĐÃ LOẠI BỎ GIA VỊ):
{ingredients_text}

NGÂN SÁCH: {budget} VND (KHÔNG ĐƯỢC VƯỢT)

RESPONSE FORMAT (CHỈ TRẢ VỀ JSON):
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

