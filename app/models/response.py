"""Response models for API endpoints."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class IngredientItem(BaseModel):
    name: str
    quantity: float
    unit: str
    price: float


class MenuDish(BaseModel):
    name: str
    total_price: float
    ingredients: List[IngredientItem]


class MenuData(BaseModel):
    meal_type: str
    total_budget: float
    total_estimated_price: float
    menu: List[MenuDish]


class MenuResponse(BaseModel):
    statusCode: int
    message: str
    data: MenuData
    metadata: Dict[str, Any]

