# AI Menu Suggestion System

Hệ thống AI gợi ý menu thông minh sử dụng LangGraph để xây dựng workflow đa bước với validation và tự động điều chỉnh.

## Tổng quan

Hệ thống phân tích query tự nhiên của người dùng, filter nguyên liệu thông minh, và tạo menu phù hợp với ngân sách và sở thích.

**Kiến trúc**: LangGraph + LLM (OpenAI/Gemini) + Pinecone (Vector DB) + Query Tool

**Tính năng**:

- Intent parsing từ query tự nhiên
- SQL generation để filter ingredients tối ưu
- Auto budget detection và meal type detection
- Iterative menu adjustment để đảm bảo trong budget (80-100%)
- Knowledge retrieval từ Pinecone

## Pipeline Workflow

```
parse_intent → query_ingredients → prefilter_ingredients →
retrieve_rules_and_generate_menu → validate_budget →
[adjust_menu → validate_budget] (loop) → build_response
```

**Flow chính**:

1. **Parse Intent**: Extract budget, num_people, preferences, meal_type
2. **Query Ingredients**: LLM sinh SQL → Filter ingredients từ DB/mockup
3. **Prefilter**: Prioritize fresh, limit 50 ingredients
4. **Generate Menu**: Query Pinecone → LLM generate menu
5. **Validate Budget**: Check trong budget và >= 80% budget
6. **Adjust Menu**: Loop điều chỉnh nếu cần (max 2 iterations)
7. **Build Response**: Format response

## Cấu trúc dự án

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Configuration
├── graph/               # LangGraph workflow
│   ├── state.py
│   ├── nodes.py
│   └── graph.py
├── services/            # Core services
│   ├── llm_service.py
│   ├── vector_store.py
│   ├── query_tool.py
│   └── user_history.py
├── prompts.py           # LLM prompts
└── data/
    └── mock_ingredients.json
```

## Cài đặt

```bash
# Setup
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Config
cp .env.example .env
# Edit .env với API keys
```

**Environment Variables**:

```env
LLM_PROVIDER=openai  # hoặc "gemini"
OPENAI_API_KEY=...
GEMINI_API_KEY=...
PINECONE_API_KEY=...
PINECONE_ENVIRONMENT=...
PINECONE_INDEX_NAME=...
```

## Chạy

```bash
python -m app.main
# hoặc
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API Docs: `http://localhost:8000/docs`

## Core Components

- **QueryTool**: LLM sinh SQL từ intent → Filter ingredients tối ưu
- **LLMService**: Abstraction cho OpenAI/Gemini (parse intent, generate SQL, generate menu, adjust menu)
- **Budget Validation**: Check over budget hoặc under 80% → trigger adjustment loop
