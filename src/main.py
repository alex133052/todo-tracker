import csv
import io
from fastapi.responses import StreamingResponse
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import os
from src.database import TodoDatabase
from src.email_service import send_verification_email, send_overdue_reminder
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="Todo Tracker Pro")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

db = TodoDatabase()
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
scheduler = BackgroundScheduler()

def send_daily_reminders_job():
    print(" Запуск проверки просроченных задач...")
    try:
        report = db.get_overdue_report()
        for email, tasks in report.items():
            print(f"📧 Отправка напоминания для {email} ({len(tasks)} задач)")
            send_overdue_reminder(email, tasks)
    except Exception as e:
        print(f"❌ Ошибка в планировщике: {e}")

@app.on_event("startup")
def startup():
    db.init_db()
    print("✅ Server started successfully")
    scheduler.add_job(send_daily_reminders_job, 'cron', hour='*') 
    scheduler.start()
    print("📅 Scheduler started")

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()

class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    email: str
    is_verified: bool = False

# ✅ ОБНОВЛЕННАЯ МОДЕЛЬ ЗАДАЧИ (добавили priority и tags)
class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = "Общее"
    priority: Optional[str] = "medium" # high, medium, low
    tags: Optional[str] = ""           # comma separated
    due_date: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[str] = None
    due_date: Optional[str] = None
    completed: Optional[bool] = None

from datetime import datetime, date  # ✅ Добавь date в импорт

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: str
    priority: str
    tags: str
    due_date: Optional[date]  # ✅ Теперь принимает date объект
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password) > 100: plain_password = plain_password[:100]
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(email: str, password: str):
    user = db.get_user_by_email(email)
    if not user: return False
    if len(password) > 100: password = password[:100]
    if not verify_password(password, user['hashed_password']): return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta: expire = datetime.utcnow() + expires_delta
    else: expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise credentials_exception
    except jwt.exceptions.InvalidTokenError:
        raise credentials_exception
    user = db.get_user_by_email(email)
    if user is None: raise credentials_exception
    return user

ADMIN_EMAIL = "alex1330@gmail.com"

def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
    except: raise HTTPException(status_code=401, detail="Не удалось проверить credentials")
    if email != ADMIN_EMAIL: raise HTTPException(status_code=403, detail="Доступ запрещен. Только для администратора.")
    return email

@app.get("/admin/pending-users")
def get_pending_users(admin_email: str = Depends(get_current_admin)):
    return db.get_pending_users()

@app.post("/admin/verify/{user_id}")
def verify_user(user_id: int, admin_email: str = Depends(get_current_admin)):
    if db.verify_user_by_id(user_id): return {"message": "Пользователь подтвержден"}
    raise HTTPException(status_code=404, detail="Пользователь не найден")

@app.post("/auth/register", response_model=UserResponse)
def register(user: UserCreate):
    password = user.password[:100] if len(user.password) > 100 else user.password
    new_user = db.create_user(user.email, password)
    try:
        send_verification_email(new_user['email'], new_user.get('verification_token', 'test_token'))
        print(f"📧 Verification email sent to {new_user['email']}")
    except Exception as e:
        print(f"⚠️ Email sending failed: {e}")
    return {"email": new_user['email'], "is_verified": False}

@app.post("/token", response_model=Token)
def login(user: UserCreate):
    db_user = authenticate_user(user.email, user.password)
    if not db_user: raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not db_user.get('is_verified'): raise HTTPException(status_code=403, detail="Аккаунт не подтвержден администратором.")
    access_token = create_access_token(data={"sub": db_user['email']}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/verify")
def verify_email(token: str):
    if db.verify_user(token): return {"message": "Email подтвержден!"}
    raise HTTPException(status_code=400, detail="Неверный или истекший токен")

@app.get("/todos", response_model=List[TodoResponse])
def get_todos(current_user: dict = Depends(get_current_user)):
    return db.get_all_todos(current_user['id'])

# ✅ ОБНОВЛЕННЫЙ СОЗДАНИЕ ЗАДАЧИ
@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate, current_user: dict = Depends(get_current_user)):
    return db.create_todo(
        title=todo.title,
        description=todo.description,
        category=todo.category,
        priority=todo.priority,
        tags=todo.tags,
        due_date=todo.due_date,
        user_id=current_user['id']
    )

@app.put("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: int, todo: TodoUpdate, current_user: dict = Depends(get_current_user)):
    updated = db.update_todo(todo_id, current_user['id'], **todo.dict(exclude_unset=True))
    if not updated: raise HTTPException(status_code=404, detail="Задача не найдена")
    return updated

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, current_user: dict = Depends(get_current_user)):
    if not db.delete_todo(todo_id, current_user['id']): raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"message": "Задача удалена"}

@app.get("/statistics")
def get_statistics(current_user: dict = Depends(get_current_user)):
    return db.get_statistics(current_user['id'])

@app.get("/todos/export/csv")
def export_todos_csv(current_user: dict = Depends(get_current_user)):
    todos = db.get_all_todos(current_user['id'])
    
    output = io.StringIO()
    # ✅ Добавляем UTF-8 BOM для корректного отображения кириллицы
    output.write('\ufeff')  # Это BOM (Byte Order Mark)
    
    writer = csv.writer(output, delimiter=';')
    
    writer.writerow(["ID", "Задача", "Описание", "Категория", "Приоритет", "Теги", "Срок", "Статус"])
    
    for todo in todos:
        status = "Выполнено" if todo['completed'] else "В процессе"
        writer.writerow([
            todo['id'],
            todo['title'],
            todo['description'] or "",
            todo['category'],
            todo['priority'],
            todo['tags'] or "",
            todo['due_date'],
            status
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",  # ✅ Указываем кодировку
        headers={"Content-Disposition": "attachment; filename=todos.csv"}
    )
    # Получаем задачи
    todos = db.get_all_todos(current_user['id'])
    
    # Создаем CSV файл в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';') # Используем ; для Excel
    
    # Заголовки
    writer.writerow(["ID", "Задача", "Описание", "Категория", "Приоритет", "Теги", "Срок", "Статус"])
    
    # Данные
    for todo in todos:
        status = "Выполнено" if todo['completed'] else "В процессе"
        writer.writerow([
            todo['id'],
            todo['title'],
            todo['description'] or "",
            todo['category'],
            todo['priority'],
            todo['tags'] or "",
            todo['due_date'],
            status
        ])
    
    # Отдаем файл
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=todos.csv"}
    )


@app.get("/")
async def root_page():
    return FileResponse("src/index.html")

@app.get("/api")
def root():
    return {"message": "Todo Tracker Pro API", "status": "running"}