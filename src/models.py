from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime  # <-- Добавили datetime

class TodoCreate(BaseModel):
    title: str
    description: str = ""
    category: str = "Общее"
    due_date: Optional[date] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[date] = None
    completed: Optional[bool] = None

class TodoResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    due_date: Optional[date]
    completed: bool
    created_at: datetime  # <-- ИЗМЕНИЛИ str НА datetime

class StatisticsResponse(BaseModel):
    total: int
    completed: int
    pending: int
    overdue: int
    by_category: dict
    completion_rate: float