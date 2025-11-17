"""Combination rules for Vietnamese menu planning."""

COMBINATION_RULES_PROMPT = """HỆ THỐNG QUY TẮC KẾT HỢP NGUYÊN LIỆU VÀ XÂY DỰNG THỰC ĐƠN VIỆT NAM

**1. NGUYÊN TẮC CỐT LÕI**

[FILTER: NO_SPICE] - Không liệt kê gia vị cơ bản (mắm, muối, tiêu, đường, hành, tỏi) như món ăn

[FILTER: FRESH_FIRST] - Ưu tiên rau củ quả tươi theo mùa

[FILTER: NO_BEVERAGE_MEAL] - Đồ uống không phải món chính (trừ bữa sáng)

[FILTER: BUDGET_IS_KING] - Ngân sách quyết định cấu trúc món ăn

**2. LOGIC PHỐI HỢP THEO THUỘC TÍNH MÓN**

Property 1: [CHIÊN/RÁN/NƯỚNG] → Cần [GIẢI NGẤY]
- Kết hợp: Nộm, Dưa góp, Kim chi, Canh chua
- Tránh: Canh béo, Món xào dầu mỡ

Property 2: [KHO/RIM] → Cần [TRUNG HÒA VỊ]
- Kết hợp: Rau củ luộc, Cơm trắng
- Tránh: Món đậm vị khác

Property 3: [HẢI SẢN] → Cần [CÂN BẰNG VỊ TANH]
- Kết hợp: Rau sống (thì là, tía tô), Dưa chua
- Gia vị: Gừng, Sả, Riềng

Property 4: [CANH BÉO/HẦM] → Tránh trùng lặp chất béo
- Kết hợp: Món khô thanh (Cá chiên, Trứng chiên)

Property 5: [TRỨNG] (Bữa sáng) → Cần tinh bột
- Kết hợp: Bánh mì, Xôi
- Tránh: Đạm động vật khác

**3. CẤU TRÚC BỮA ĂN THEO NGÂN SÁCH**

3.1. Bữa SÁNG - 1 món (One-dish meal)
- Phở, Bún, Miến, Cháo, Xôi, Bánh mì

3.2. TRƯA/TỐI + Budget TIẾT KIỆM
- Cấu trúc A: Cơm rang, Mì xào, Bún trộn (all-in-one)
- Cấu trúc B: 1 Món mặn + Cơm trắng
- Loại bỏ: Tráng miệng, Canh (trừ canh là món chính)

3.3. TRƯA/TỐI + Budget VỪA PHẢI
- Cấu trúc: 1 Mặn + 1 Rau/Phụ + 1 Canh
- Áp dụng logic phối hợp (Mục 2)

3.4. TRƯA/TỐI + Budget CAO CẤP
- Cấu trúc: 1-2 Mặn + 1-2 Rau/Phụ + 1 Canh + 1 Tráng miệng
- Áp dụng logic phối hợp (Mục 2)

**4. XỬ LÝ THAY THẾ NGUYÊN LIỆU**

IF thiếu nguyên liệu:
- Thịt Bò ↔ Thịt Heo nạc (Đạm đỏ)
- Cải ngọt ↔ Cải thìa, Rau muống (Rau lá xanh)

IF dị ứng/không thích:
- Loại bỏ hoàn toàn nguyên liệu đó

**5. FORMAT OUTPUT**

Template 1 (Sáng/Tiết kiệm):
Món chính: [Tên món]

Template 2 (Vừa phải):
Món chính: [Tên món]
Món rau: [Tên món]
Canh: [Tên món]

Template 3 (Cao cấp):
Món chính 1: [Tên món]
Món chính 2: [Tên món]
Món rau/xào: [Tên món]
Canh: [Tên món]
Tráng miệng: [Tên món]
"""

