from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import os
from src.database import TodoDatabase
from src.email_service import send_verification_email, send_overdue_reminder
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(title="Todo Tracker Pro")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Database
db = TodoDatabase()

# Password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Scheduler
scheduler = BackgroundScheduler()

def send_daily_reminders_job():
    """Эта функция запускается автоматически по расписанию"""
    print("⏰ Запуск проверки просроченных задач...")
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
    
    # Запускаем планировщик (каждый час)
    scheduler.add_job(send_daily_reminders_job, 'cron', hour='*') 
    scheduler.start()
    print("📅 Scheduler started: Checking overdue tasks every hour")

@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()

# Models
class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    email: str
    is_verified: bool = False

class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = "Общее"
    due_date: Optional[str] = None

class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[str] = None
    completed: Optional[bool] = None

class TodoResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: str
    due_date: Optional[str]
    completed: bool
    created_at: datetime

class Token(BaseModel):
    access_token: str
    token_type: str

# Helpers
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def authenticate_user(email: str, password: str):
    user = db.get_user_by_email(email)
    if not user:
        return False
    # Обрезаем пароль до 72 символов (ограничение bcrypt)
    if len(password) > 72:
        password = password[:72]
    if not verify_password(password, user['hashed_password']):
        return False
    return user

def create_access_token( dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.exceptions.InvalidTokenError:
        raise credentials_exception
    user = db.get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user

# === АДМИН ПАНЕЛЬ ===
ADMIN_EMAIL = "alex1330@gmail.com"  # ← Твоя почта администратора

def get_current_admin(token: str = Depends(oauth2_scheme)):
    """Проверяет, что текущий пользователь - Админ"""
    credentials_exception = HTTPException(status_code=401, detail="Не удалось проверить credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.exceptions.InvalidTokenError:
        raise credentials_exception
        
    if email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Доступ запрещен. Только для администратора.")
    return email

@app.get("/admin/pending-users")
def get_pending_users(admin_email: str = Depends(get_current_admin)):
    """Получить список неподтвержденных пользователей (только для админа)"""
    return db.get_pending_users()

@app.post("/admin/verify/{user_id}")
def verify_user(user_id: int, admin_email: str = Depends(get_current_admin)):
    """Подтвердить пользователя (только для админа)"""
    if db.verify_user_by_id(user_id):
        return {"message": "Пользователь подтвержден"}
    raise HTTPException(status_code=404, detail="Пользователь не найден")

# === AUTH ENDPOINTS ===
@app.post("/auth/register", response_model=UserResponse)
def register(user: UserCreate):
    # Обрезаем пароль при регистрации
    if len(user.password) > 72:
        user.password = user.password[:72]
    
    new_user = db.create_user(user.email, user.password)
    
    # Отправляем email с подтверждением
    try:
        send_verification_email(new_user['email'], new_user.get('verification_token', 'test_token'))
        print(f"📧 Verification email sent to {new_user['email']}")
    except Exception as e:
        print(f"⚠️ Email sending failed: {e}")
    
    return {"email": new_user['email'], "is_verified": False}

@app.post("/token", response_model=Token)
def login(user: UserCreate):
    db_user = authenticate_user(user.email, user.password)
    if not db_user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    
    # Проверка: подтвержден ли email
    if not db_user.get('is_verified'):
        raise HTTPException(status_code=403, detail="Аккаунт не подтвержден администратором.")
    
    access_token = create_access_token(
        data={"sub": db_user['email']},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/verify")
def verify_email(token: str):
    if db.verify_user(token):
        return {"message": "Email подтвержден! Теперь вы можете войти."}
    raise HTTPException(status_code=400, detail="Неверный или истекший токен")

# === TODO ENDPOINTS ===
@app.get("/todos", response_model=List[TodoResponse])
def get_todos(current_user: dict = Depends(get_current_user)):
    return db.get_all_todos(current_user['id'])

@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate, current_user: dict = Depends(get_current_user)):
    return db.create_todo(
        title=todo.title,
        description=todo.description,
        category=todo.category,
        due_date=todo.due_date,
        user_id=current_user['id']
    )

@app.put("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(todo_id: int, todo: TodoUpdate, current_user: dict = Depends(get_current_user)):
    updated = db.update_todo(todo_id, current_user['id'], **todo.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return updated

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, current_user: dict = Depends(get_current_user)):
    if not db.delete_todo(todo_id, current_user['id']):
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return {"message": "Задача удалена"}

@app.get("/statistics")
def get_statistics(current_user: dict = Depends(get_current_user)):
    return db.get_statistics(current_user['id'])

# === ROOT PAGE (FRONTEND) ===
@app.get("/")
async def root_page():
    """Отдаёт index.html"""
    return FileResponse("src/index.html")

# Root API check
@app.get("/api")
def root():
    return {"message": "Todo Tracker Pro API", "status": "running"}