"""Request models for API endpoints."""
from typing import Optional
from pydantic import BaseModel, Field


class MenuRequest(BaseModel):
    query: str = Field(
        ...,
        description="Câu hỏi hoặc yêu cầu của người dùng về menu (ví dụ: 'Hôm nay ăn gì với 200k')",
        example="Gợi ý bữa trưa 200k cho 2 người"
    )
    user_id: Optional[str] = Field(
        None,
        description="ID người dùng (tùy chọn) để theo dõi lịch sử và tránh món lặp lại. Có thể nhập bất kỳ chuỗi gì (ví dụ: 'user123', 'alice', email, UUID...)",
        example="user123"
    )
    
    class Config:
        schema_extra = {
            "examples": [
                {
                    "query": "Gợi ý bữa trưa 200k cho 2 người",
                    "user_id": "user123"
                },
            ]
        }

