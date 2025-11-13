"""Request models for API endpoints."""
from pydantic import BaseModel


class MenuRequest(BaseModel):
    query: str

