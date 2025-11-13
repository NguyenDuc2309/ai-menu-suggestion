# Pinecone Usage trong Hệ thống

## Tổng quan

Pinecone được sử dụng như **vector database** để lưu trữ và retrieve tri thức về món ăn, công thức nấu ăn. Đây là một phần quan trọng của RAG (Retrieval Augmented Generation) pipeline.

## Vị trí sử dụng trong code

### 1. Service Layer: `app/services/vector_store.py`

```python
class VectorStoreService:
    """Service để query Pinecone vector store."""

    def query_knowledge(
        self,
        cuisine_type: str,
        ingredients: List[str],
        top_k: int = 5
    ) -> List[str]:
        """
        Query Pinecone để lấy knowledge về món ăn.

        - Embedding query text thành vector
        - Tìm top_k documents tương tự nhất
        - Trả về text content của các documents
        """
```

**Mục đích:**

- Encapsulate logic kết nối với Pinecone
- Xử lý embedding và similarity search
- Trả về knowledge documents dưới dạng text

### 2. Graph Node: `app/graph/nodes.py` - `retrieve_and_generate_menu_node`

```python
def retrieve_and_generate_menu_node(state: MenuGraphState) -> MenuGraphState:
    """Retrieve knowledge from Pinecone and generate menu."""
    # 1. Lấy cuisine type và ingredients từ state
    # 2. Query Pinecone để lấy knowledge
    vector_store = get_vector_store_service()
    context = vector_store.query_knowledge(
        cuisine_type=cuisine,
        ingredients=ingredient_names,
        top_k=5
    )
    state["pinecone_context"] = context

    # 3. Generate menu với LLM, sử dụng context từ Pinecone
    menu = llm_service.generate_menu(
        ingredients=ingredients,
        context=context,  # <-- Knowledge từ Pinecone
        cuisine=cuisine,
        budget=budget
    )
```

**Mục đích:**

- Retrieve knowledge về món ăn theo cuisine type
- Cung cấp context cho LLM khi generate menu
- Đảm bảo menu được tạo dựa trên tri thức có sẵn

## Flow sử dụng Pinecone

```
User Input: "Hôm nay ăn gì với 200k, đồ Hàn"
    ↓
[Parse Intent] → cuisine="Hàn", budget=200000
    ↓
[Query Ingredients] → available_ingredients = [...]
    ↓
[Retrieve Knowledge] → Query Pinecone
    ├─ Build query: "Hàn cuisine recipes with ingredients: kimchi, thịt heo, ..."
    ├─ Embed query thành vector
    ├─ Similarity search trong Pinecone index
    └─ Return top 5 documents về món Hàn Quốc
    ↓
[Generate Menu] → LLM sử dụng Pinecone context
    ├─ Input: ingredients + Pinecone knowledge
    └─ Output: Menu với các món phù hợp
    ↓
[Validate & Adjust] → ...
```

## Cấu hình Pinecone

### Environment Variables (`.env`)

```env
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENVIRONMENT=your_environment  # e.g., "us-east1-gcp"
PINECONE_INDEX_NAME=your_index_name    # e.g., "menu-knowledge"
```

### Khởi tạo trong `VectorStoreService`

```python
# Sử dụng OpenAI embeddings để convert text → vector
self.embeddings = OpenAIEmbeddings(openai_api_key=config.OPENAI_API_KEY)

# Kết nối với Pinecone index
self.vector_store = PineconeVectorStore(
    index_name=config.PINECONE_INDEX_NAME,
    embedding=self.embeddings,
    pinecone_api_key=config.PINECONE_API_KEY
)
```

## Cấu trúc dữ liệu trong Pinecone

### Documents nên chứa:

1. **Công thức món ăn**

   - Tên món
   - Nguyên liệu cần thiết
   - Cách nấu
   - Giá trị dinh dưỡng

2. **Kiến thức về cuisine**

   - Đặc điểm của từng loại món ăn (Hàn, Việt, Nhật, etc.)
   - Cách kết hợp nguyên liệu
   - Món ăn phổ biến

3. **Metadata** (nếu có)
   - cuisine_type: "Hàn", "Việt", etc.
   - dish_type: "main", "side", "soup"
   - difficulty: "easy", "medium", "hard"

### Example Document:

```
Title: Kimchi Jjigae (Canh Kimchi)
Cuisine: Hàn Quốc
Type: Main dish

Ingredients:
- Kimchi: 200g
- Thịt heo: 150g
- Tỏi: 2 tép
- Hành tây: 50g
- Gochujang: 1 thìa

Instructions:
1. Xào thịt heo với kimchi
2. Thêm nước và đun sôi
3. Nêm gia vị với gochujang
...

Nutritional Info:
- Calories: ~250 per serving
- Protein: 15g
```

## API nào sử dụng Pinecone?

**Không có API endpoint riêng cho Pinecone.** Pinecone được sử dụng **internally** trong workflow:

- **API Endpoint**: `POST /api/v1/menu/suggest`
- **Internal Usage**: Trong node `retrieve_and_generate_menu_node` của LangGraph workflow
- **Không expose trực tiếp**: User không gọi Pinecone API trực tiếp, mà thông qua menu suggestion API

## Lợi ích của việc sử dụng Pinecone

1. **RAG (Retrieval Augmented Generation)**:

   - LLM có context cụ thể về món ăn thay vì chỉ dựa vào training data
   - Menu được generate chính xác hơn, phù hợp với cuisine type

2. **Scalability**:

   - Có thể thêm hàng nghìn documents về món ăn
   - Pinecone tự động index và search nhanh

3. **Accuracy**:
   - Similarity search đảm bảo lấy được knowledge liên quan nhất
   - Giảm hallucination của LLM

## Setup Pinecone Index

Để sử dụng hệ thống, cần:

1. **Tạo Pinecone account** tại https://www.pinecone.io/
2. **Tạo index** với:
   - Dimension: 1536 (cho OpenAI embeddings) hoặc 768 (cho text-embedding-3-small)
   - Metric: cosine
   - Name: `menu-knowledge` (hoặc tên khác, update trong `.env`)
3. **Upload documents** về món ăn vào index
4. **Cấu hình** `.env` với API key và index name

## Troubleshooting

### Lỗi thường gặp:

1. **"Pinecone configuration is missing"**

   - Kiểm tra `.env` có đủ `PINECONE_API_KEY` và `PINECONE_INDEX_NAME`

2. **"Error querying Pinecone"**

   - Kiểm tra API key có đúng không
   - Kiểm tra index name có tồn tại không
   - Kiểm tra index có documents không

3. **Empty results**
   - Index chưa có documents
   - Query không match với documents trong index
   - Thử query với keywords khác
