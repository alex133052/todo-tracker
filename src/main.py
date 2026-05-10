from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from src.database import TodoDatabase
from src.models import TodoCreate, TodoResponse

app = FastAPI(title="Todo Tracker API")
db = TodoDatabase()

@app.on_event("startup")
def startup():
    db.init_db()

@app.get("/")
def root():
    return FileResponse("src/index.html")

@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate):
    return db.create_todo(todo.title, todo.description)

@app.get("/todos", response_model=list[TodoResponse])
def get_todos():
    return db.get_all_todos()

@app.put("/todos/{todo_id}")
def toggle_todo(todo_id: int):
    success = db.update_todo(todo_id, True) # Упрощенно: всегда помечаем как выполненное
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task completed"}

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    success = db.delete_todo(todo_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}