from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from src.database import TodoDatabase
from src.models import UserCreate, Token
from src.auth import create_access_token, get_current_user, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES
from src.email_service import send_verification_email, send_overdue_reminder
from datetime import timedelta
from typing import Optional
from validate_email import validate_email
from apscheduler.schedulers.background import BackgroundScheduler
import os

app = FastAPI(title="Todo Tracker Pro")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

db = TodoDatabase()

# --- НАСТРОЙКА ПЛАНИРОВЩИКА ---
scheduler = BackgroundScheduler()

def check_overdue_tasks():
    print("🔄 Checking for overdue tasks...")
    # Здесь нужно пройтись по всем пользователям и проверить их задачи
    # Для простоты примера, это требует получения списка всех юзеров
    # В реальном проекте: db.get_all_users() -> loop -> check tasks -> send email
    pass

@app.on_event("startup")
def startup():
    db.init_db()
    # scheduler.start() # Раскомментируй, когда настроишь SMTP
    print("🚀 Server started")

# --- AUTH ---

@app.post("/auth/register", response_model=dict)
def register(user: UserCreate):
    # 1. Валидация формата и MX записей (серьезная проверка)
    is_valid = validate_email(user.email, check_mx=True, verify=True)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Некорректный email или домен не существует")

    # 2. Создание пользователя (статус pending)
    try:
        new_user = db.create_user(user.email, user.password)
        
        # 3. Отправка письма с токеном
        send_verification_email(new_user['email'], new_user.get('verification_token', 'test_token'))
        
        return {"message": "Пользователь создан. Проверьте почту для подтверждения."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/verify")
def verify_email(token: str):
    success = db.verify_user(token)
    if success:
        return HTMLResponse(content="<h1>✅ Email подтвержден! Теперь вы можете войти.</h1>")
    else:
        return HTMLResponse(content="<h1>❌ Неверная ссылка или срок истек.</h1>")

@app.post("/token", response_model=Token)
def login(user: UserCreate):
    db_user = authenticate_user(user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    if not db_user.get('is_verified'):
        raise HTTPException(status_code=403, detail="Аккаунт не подтвержден. Проверьте почту.")
    
    access_token = create_access_token(
        data={"sub": db_user['email']},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- TODOS ---
# (Роуты оставляем как были, они уже работают с user_id)
@app.post("/todos")
def create_todo(todo: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    return db.create_todo(todo['title'], todo.get('description', ''), todo.get('category', 'Общее'), todo.get('due_date'), user_id)

@app.get("/todos")
def get_todos(current_user: dict = Depends(get_current_user)):
    return db.get_all_todos(current_user['id'])

# ... остальные роуты ...