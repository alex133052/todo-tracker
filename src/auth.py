from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import psycopg2
import os

# Настройки JWT
SECRET_KEY = "your-super-secret-key-change-in-production"  # В продакшене вынести в .env!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db_connection():
    host = os.getenv("DATABASE_HOST", "localhost")
    password = os.getenv("DATABASE_PASSWORD", "secret")
    db_name = os.getenv("DATABASE_NAME", "postgres")
    user = os.getenv("DATABASE_USER", "postgres")
    dsn = f"dbname={db_name} user={user} password={password} host={host} port=5432"
    return psycopg2.connect(dsn)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate_user(email: str, password: str):
    """Проверяет email/пароль и возвращает пользователя или None"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, hashed_password FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                return None
            if not verify_password(password, user['hashed_password']):
                return None
            return {"id": user['id'], "email": user['email']}
    finally:
        conn.close()

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверные учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Проверяем, что пользователь существует
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user:
                raise credentials_exception
            return {"id": user['id'], "email": user['email']}
    finally:
        conn.close()