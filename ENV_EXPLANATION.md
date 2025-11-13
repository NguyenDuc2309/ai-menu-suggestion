# Giải thích Environment Variables

## Dòng 13-14 trong .env

```env
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=your_pinecone_index_name
```

### PINECONE_ENVIRONMENT

**Mục đích:** Chỉ định environment/region của Pinecone index

**Giá trị có thể:**

- `us-east1-gcp` - Google Cloud Platform, US East
- `us-west1-gcp` - Google Cloud Platform, US West
- `eu-west1-gcp` - Google Cloud Platform, EU West
- `asia-southeast1-gcp` - Google Cloud Platform, Asia Southeast
- Hoặc các environment khác tùy theo Pinecone account của bạn

**Ví dụ:**

```env
PINECONE_ENVIRONMENT=us-east1-gcp
```

**Lưu ý:**

- Với Pinecone v3 (pinecone-client >= 3), có thể không cần environment nữa vì Pinecone tự động detect
- Nhưng vẫn nên giữ để đảm bảo compatibility

### PINECONE_INDEX_NAME

**Mục đích:** Tên của Pinecone index chứa knowledge về món ăn

**Giá trị:** Tên index bạn đã tạo trong Pinecone console

**Ví dụ:**

```env
PINECONE_INDEX_NAME=menu-knowledge
```

**Cách tạo index:**

1. Đăng nhập Pinecone Console: https://app.pinecone.io/
2. Tạo index mới với:
   - Name: `menu-knowledge` (hoặc tên khác)
   - Dimension: `1536` (cho OpenAI text-embedding-ada-002) hoặc `768` (cho text-embedding-3-small)
   - Metric: `cosine`
   - Environment: Chọn environment phù hợp

**Lưu ý:**

- Index name phải match chính xác với tên trong Pinecone console
- Index phải được tạo trước khi sử dụng
- Index cần có documents được upload vào để query được

## Các biến môi trường khác

### LLM Provider

```env
LLM_PROVIDER=openai  # hoặc "gemini"
OPENAI_API_KEY=your_openai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### Pinecone

```env
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_ENVIRONMENT=your_pinecone_environment
PINECONE_INDEX_NAME=your_pinecone_index_name
```

### API Config

```env
API_TITLE=AI Menu Suggestion API
API_VERSION=1.0.0
API_DESCRIPTION=AI-powered menu suggestion system using LangGraph and Pinecone
```
