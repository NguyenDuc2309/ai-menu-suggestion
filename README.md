# AI Menu Suggestion System

Hệ thống AI gợi ý menu sử dụng FastAPI + LangGraph + Pinecone. Hỗ trợ cả OpenAI (GPT-4) và Google Gemini.

## Tính năng

- **Multi-step workflow**: Sử dụng LangGraph để xây dựng workflow có điều kiện
- **Knowledge retrieval**: Tích hợp Pinecone để lấy tri thức về món ăn và công thức
- **Multi-provider LLM**: Hỗ trợ cả OpenAI và Google Gemini
- **Validation**: Tự động kiểm tra số lượng nguyên liệu và giá cả
- **Auto-adjustment**: Tự động điều chỉnh menu nếu không đáp ứng yêu cầu

## Cấu trúc dự án

```
menu-search/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── config.py               # Configuration management
│   ├── models/                 # Pydantic models
│   ├── graph/                  # LangGraph workflow
│   ├── services/               # Services (LLM, Vector Store)
│   └── api/                    # API routes
├── .env                        # Environment variables (not in git)
├── .env.example               # Example environment file
└── requirements.txt           # Python dependencies
```

## Cài đặt

### 1. Clone repository

```bash
git clone <repository-url>
cd menu-search
```

### 2. Tạo virtual environment

**Yêu cầu:** Python 3.11 hoặc cao hơn (khuyến nghị Python 3.11+)

```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### 4. Cấu hình environment variables

Copy `.env.example` thành `.env` và điền các giá trị:

```bash
cp .env.example .env
```

Chỉnh sửa `.env`:

```env
# LLM Provider: "openai" hoặc "gemini"
LLM_PROVIDER=openai

# OpenAI API Key (nếu dùng OpenAI)
OPENAI_API_KEY=your_openai_api_key_here

# Google Gemini API Key (nếu dùng Gemini)
GEMINI_API_KEY=your_gemini_api_key_here

# Pinecone Configuration
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=your_pinecone_index_name

# API Configuration (optional)
API_TITLE=AI Menu Suggestion API
API_VERSION=1.0.0
```

## Chạy ứng dụng

```bash
python -m app.main
```

Hoặc sử dụng uvicorn trực tiếp:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ứng dụng sẽ chạy tại: `http://localhost:8000`

## API Documentation

Sau khi chạy ứng dụng, truy cập Swagger UI tại:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### POST `/api/v1/menu/suggest`

Gợi ý menu dựa trên query của user.

**Request Body:**
```json
{
  "query": "Hôm nay ăn gì với 200k, đồ Hàn"
}
```

**Response:**
```json
{
  "menu_items": [
    {
      "name": "Kimchi Jjigae",
      "type": "main",
      "ingredients": [
        {
          "name": "kimchi",
          "quantity": 200,
          "unit": "g"
        },
        {
          "name": "thịt heo",
          "quantity": 150,
          "unit": "g"
        }
      ],
      "price": 50000
    }
  ],
  "total_price": 150000,
  "cuisine_type": "Hàn",
  "reasoning": "Menu được tạo dựa trên nguyên liệu có sẵn và ngân sách 200000 VND",
  "status": "success"
}
```

### GET `/health`

Health check endpoint.

## Workflow

1. **Parse Intent**: Phân tích user input để extract cuisine và budget
2. **Query Ingredients**: Lấy danh sách nguyên liệu có sẵn (mock data)
3. **Retrieve Knowledge & Generate Menu**: 
   - Query Pinecone để lấy tri thức về món ăn
   - LLM generate menu phù hợp với nguyên liệu có sẵn
4. **Validate**: Kiểm tra số lượng nguyên liệu và giá cả
5. **Adjust Menu**: Điều chỉnh menu nếu không pass validation (loop về validate)
6. **Build Response**: Format và trả về response cuối cùng

## Development

### Testing

```bash
# Test với curl
curl -X POST "http://localhost:8000/api/v1/menu/suggest" \
  -H "Content-Type: application/json" \
  -d '{"query": "Hôm nay ăn gì với 200k, đồ Hàn"}'
```

## Notes

- Hiện tại ingredients được mock trong code. Trong production, sẽ query từ database thực tế.
- Pinecone index cần được setup trước với các documents về món ăn và công thức.
- LLM provider có thể switch qua config `LLM_PROVIDER` trong `.env`.

