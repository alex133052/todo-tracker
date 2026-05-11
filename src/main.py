from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.database import TodoDatabase
from src.models import UserCreate, Token
from src.auth import create_access_token, get_current_user, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta
from typing import Optional

app = FastAPI(title="Todo Tracker Pro")

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

# ================= AUTH =================

@app.post("/auth/register", response_model=dict)
def register(user: UserCreate):
    try:
        new_user = db.create_user(user.email, user.password)
        return {"message": "Пользователь создан", "user_id": new_user['id']}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/token", response_model=Token)
def login(user: UserCreate):
    db_user = authenticate_user(user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    access_token = create_access_token(
        data={"sub": db_user['email']},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# ================= TODOS =================

@app.post("/todos")
def create_todo(todo: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    return db.create_todo(
        todo['title'], 
        todo.get('description', ''), 
        todo.get('category', 'Общее'), 
        todo.get('due_date'), 
        user_id
    )

@app.get("/todos")
def get_todos(
    current_user: dict = Depends(get_current_user),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    user_id = current_user['id']
    
    if search:
        return db.search_todos(search, user_id)
    elif category:
        return db.get_todos_by_category(category, user_id)
    else:
        return db.get_all_todos(user_id)

@app.get("/categories")
def get_categories(current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    return db.get_categories(user_id)

@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, todo: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    result = db.update_todo(todo_id, user_id, **todo)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    success = db.delete_todo(todo_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted"}

@app.get("/statistics")
def get_statistics(current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    return db.get_statistics(user_id)