"""Prompts for LLM operations."""

PARSE_INTENT_PROMPT = """You are an intent parser. Extract ONLY what the user explicitly mentions:

- budget: Budget amount in VND (ONLY if user mentions specific number like "150k", "200000"). Return null if not mentioned.
- num_people: Number of people (ONLY if user mentions like "cho 2 người", "3 người"). Return 1 if not mentioned.
- preferences: Dietary preferences or restrictions (ONLY if user mentions like "ăn chay", "không ăn thịt bò"). Return empty array [] if not mentioned.

IMPORTANT:
- DO NOT infer meal_type (sáng/trưa/tối) - it will be auto-detected from current time
- DO NOT infer budget if user doesn't mention it - it will be auto-calculated
- ONLY extract what user explicitly says

Return ONLY valid JSON:
{{
    "budget": number_or_null,
    "num_people": number,
    "preferences": ["preference1", "preference2"]
}}

Examples:
- "Ăn gì với 150k" → {{"budget": 150000, "num_people": 1, "preferences": []}}
- "Gợi ý món cho 3 người" → {{"budget": null, "num_people": 3, "preferences": []}}
- "Ăn chay" → {{"budget": null, "num_people": 1, "preferences": ["ăn chay"]}}
- "Hôm nay ăn gì" → {{"budget": null, "num_people": 1, "preferences": []}}

User input: {user_input}"""

GENERATE_MENU_PROMPT = """BẠN LÀ CHUYÊN GIA LẬP THỰC ĐƠN. Nhiệm vụ: Từ nguyên liệu có sẵn, tạo menu phù hợp với NGÂN SÁCH và người dùng.

════════════════════════════════════════════════════════════════════════════════
⚠️  CÁC QUY TẮC QUAN TRỌNG
════════════════════════════════════════════════════════════════════════════════

🔴 QUY TẮC 1: NGÂN SÁCH QUYẾT ĐỊNH SỐ MÓN (BẮT BUỘC)
- Tổng giá PHẢI <= {budget} VND (TUYỆT ĐỐI không vượt)
- TARGET: Sử dụng 80-95% ngân sách (tối thiểu 80%, không để dư quá nhiều)
- SỐ MÓN PHỤ THUỘC NGÂN SÁCH:
  
  • Ngân sách 40-70k: 1-2 món đơn giản (phở, bún, cơm gà)
  • Ngân sách 70-150k: 2-3 món (món chính + phụ/canh)
  • Ngân sách 150-300k: 3-4 món (món chính + phụ + canh)
  • Ngân sách > 300k: 4-5 món đa dạng

- TRÁNG MIỆNG và ĐỒ UỐNG: CHỈ thêm nếu còn dư ngân sách
  → ĐỒ UỐNG PHẢI LÀ SẢN PHẨM ĐÓNG GÓI SẴN (lon, hộp): nước ngọt, nước suối, trà đóng chai, cà phê lon, sữa hộp...
  → TUYỆT ĐỐI KHÔNG chế biến đồ uống từ nguyên liệu
  → Giá cố định: 10-25k/lon/hộp

🔴 QUY TẮC 2: TUÂN THỦ QUY TẮC KẾT HỢP NGUYÊN LIỆU (NẾU CÓ)
- Các quy tắc kết hợp nguyên liệu bên dưới chỉ là GỢI Ý, không bắt buộc nếu ngân sách thấp
- Ưu tiên ngân sách trước, quy tắc sau
- Ví dụ: "ăn sáng không ăn cơm" → NÊN tránh cơm, nhưng nếu ngân sách thấp có thể linh hoạt

🔴 QUY TẮC 3: CHỈ SỬ DỤNG NGUYÊN LIỆU CHÍNH (BẮT BUỘC)
- Danh sách đã loại bỏ gia vị (muối, đường, dầu, nước mắm, tỏi, ớt...)
- CHỈ gợi ý nguyên liệu CHÍNH: thịt, cá, rau, trứng, đậu phụ, tinh bột
- KHÔNG thêm gia vị vào món ăn

🔴 QUY TẮC 4: ƯU TIÊN RAU CỦ TƯƠI SỐNG (BẮT BUỘC)
- RAU CỦ và HOA QUẢ: LUÔN ưu tiên đồ TƯƠI SỐNG trước
- CHỈ sử dụng "rau củ đông lạnh", "rau củ đóng hộp" khi:
  • KHÔNG còn rau củ tươi sống phù hợp trong danh sách
  • Ngân sách quá thấp và chỉ có đông lạnh/đóng hộp rẻ hơn
- Ví dụ:
  ✓ Ưu tiên: "rau muống", "rau cải", "cà chua", "cà rốt", "hành tây" (tươi)
  ✗ Tránh: "rau củ đông lạnh", "rau củ đóng hộp" (chỉ dùng khi không còn lựa chọn)

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

BƯỚC 3: TỐI ƯU NGÂN SÁCH
- Tính tổng giá: price = base_price × quantity cho từng nguyên liệu
- Đảm bảo tổng giá <= {budget} VND và >= 80% budget
- Nếu còn dư ngân sách: tăng khẩu phần, thêm món phụ/canh, hoặc tráng miệng/đồ uống (sản phẩm đóng gói 10-25k)

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

{enhancement_note}

⚠️  QUY TẮC BẮT BUỘC:
- CHỈ sử dụng nguyên liệu CHÍNH từ danh sách (thịt, cá, rau, tinh bột)
- KHÔNG thêm gia vị (muối, đường, dầu, nước mắm, xì dầu, tỏi, ớt...)
- RAU CỦ: Ưu tiên đồ TƯƠI SỐNG, chỉ dùng đông lạnh/đóng hộp khi không còn lựa chọn
- Tổng giá PHẢI <= {budget} VND và >= 80% budget
- Ưu tiên món ăn gia đình Việt Nam truyền thống

CHIẾN LƯỢC ĐIỀU CHỈNH (theo thứ tự ưu tiên):
1. VƯỢT BUDGET: Bỏ tráng miệng/đồ uống → Giảm số món → Thay món đắt bằng rẻ hơn → Giảm khẩu phần
2. DƯỚI 80% BUDGET: Tăng khẩu phần → Thêm món phụ/canh → Thêm tráng miệng/đồ uống (10-25k) → Nâng cấp nguyên liệu → Thêm món mới

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

