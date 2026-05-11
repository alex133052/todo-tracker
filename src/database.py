import psycopg2
import os
from psycopg2.extras import RealDictCursor
from datetime import datetime
from src.auth import get_password_hash

class TodoDatabase:
    def __init__(self):
        host = os.getenv("DATABASE_HOST", "localhost")
        password = os.getenv("DATABASE_PASSWORD", "secret")
        db_name = os.getenv("DATABASE_NAME", "postgres")
        user = os.getenv("DATABASE_USER", "postgres")
        
        self.dsn = f"dbname={db_name} user={user} password={password} host={host} port=5432"
        self._conn = None

    def _get_connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
            self._conn.cursor_factory = RealDictCursor
        return self._conn

    def init_db(self):
        conn = self._get_connection()
        with conn.cursor() as cur:
            # 1. Таблица пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. Таблица задач (добавляем user_id если нет)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'Общее',
                    due_date DATE,
                    completed BOOLEAN DEFAULT FALSE,
                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def create_user(self, email: str, password: str) -> dict:
        conn = self._get_connection()
        hashed_pw = get_password_hash(password)
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO users (email, hashed_password) VALUES (%s, %s) RETURNING id, email",
                    (email, hashed_pw)
                )
                conn.commit()
                return dict(cur.fetchone())
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                raise ValueError("Пользователь с таким email уже существует")

    def authenticate_user(self, email: str, password: str):
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, hashed_password FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user or not pwd_context.verify(password, user['hashed_password']):
                return None
            return dict(user)

    # ... остальные методы get_all_todos, create_todo и т.д. остаются без изменений ...
    # (просто добавь user_id во все запросы INSERT/SELECT)