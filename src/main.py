from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from src.database import TodoDatabase
from src.models import UserCreate, Token
from src.auth import create_access_token, get_current_user
from datetime import timedelta
from src.auth import ACCESS_TOKEN_EXPIRE_MINUTES, authenticate_user

app = FastAPI(title="Todo Tracker Pro")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

db = TodoDatabase()

@app.on_event("startup")
def startup():
    db.init_db()

@app.get("/")
def root():
    return FileResponse("src/index.html")

# --- AUTH ---
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

# --- TODOS (теперь с авторизацией) ---
@app.post("/todos")
def create_todo(todo: dict, current_user: dict = Depends(get_current_user)):
    # TODO: добавить user_id в вызов db.create_todo
    return db.create_todo(todo['title'], todo.get('description', ''), todo.get('category', 'Общее'), todo.get('due_date'))

@app.get("/todos")
def get_todos(current_user: dict = Depends(get_current_user)):
    # TODO: добавить фильтрацию по current_user['email'] или user_id
    return db.get_all_todos()

# ... остальные эндпоинты ...