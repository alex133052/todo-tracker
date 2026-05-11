from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from src.database import TodoDatabase
from src.models import UserCreate, Token
from src.auth import create_access_token, get_current_user, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES
from src.email_service import send_verification_email
from datetime import timedelta
from typing import Optional
from validate_email import validate_email
import os

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
    print("✅ Server started successfully")

@app.get("/")
def root():
    return FileResponse("src/index.html")

@app.post("/auth/register", response_model=dict)
def register(user: UserCreate):
    try:
        # Упрощённая проверка email (без verify=True, чтобы избежать таймаутов)
        is_valid = validate_email(user.email, check_mx=True)
        
        if not is_valid:
            # Для тестов можно раскомментировать pass вместо raise
            # pass
            raise HTTPException(status_code=400, detail="Некорректный email или домен")

        new_user = db.create_user(user.email, user.password)
        
        # Отправка письма с подтверждением
        try:
            send_verification_email(new_user['email'], new_user.get('verification_token', 'test_token'))
            print(f"📧 Verification email sent to {new_user['email']}")
        except Exception as e:
            print(f"⚠️ Email sending failed: {e}")
            
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

@app.post("/todos")
def create_todo(todo: dict, current_user: dict = Depends(get_current_user)):
    user_id = current_user['id']
    return db.create_todo(todo['title'], todo.get('description', ''), todo.get('category', 'Общее'), todo.get('due_date'), user_id)

@app.get("/todos")
def get_todos(current_user: dict = Depends(get_current_user)):
    return db.get_all_todos(current_user['id'])

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