from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.database import TodoDatabase
from src.models import TodoCreate, TodoUpdate, TodoResponse, StatisticsResponse
from typing import Optional

app = FastAPI(title="Todo Tracker API")

# Добавляем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = TodoDatabase()

@app.on_event("startup")
def startup():
    db.init_db()

@app.get("/")
def root():
    return FileResponse("src/index.html")

@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate):
    return db.create_todo(todo.title, todo.description, todo.category, todo.due_date)

@app.get("/todos", response_model=list[TodoResponse])
def get_todos(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    if search:
        return db.search_todos(search)
    elif category:
        return db.get_todos_by_category(category)
    else:
        return db.get_all_todos()

@app.get("/categories", response_model=list[str])
def get_categories():
    return db.get_categories()

@app.put("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: int, todo: TodoUpdate):
    result = db.update_todo(todo_id, **todo.dict(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    success = db.delete_todo(todo_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}

@app.get("/statistics", response_model=StatisticsResponse)
def get_statistics():
    return db.get_statistics()