import psycopg2
import os
from psycopg2.extras import RealDictCursor
from datetime import datetime
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
            # 1. Обновляем таблицу пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_verified BOOLEAN DEFAULT FALSE,
                    verification_token TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Добавляем колонки, если их нет
            cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='is_verified'""")
            if not cur.fetchone():
                cur.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE")
            cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='verification_token'""")
            if not cur.fetchone():
                cur.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
            
            # 2. Таблица задач
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
             # Добавляем колонку user_id в todos, если нет
            cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='todos' AND column_name='user_id'""")
            if not cur.fetchone():
                cur.execute("ALTER TABLE todos ADD COLUMN user_id INT")

            conn.commit()

    def create_user(self, email: str, password: str) -> dict:
        conn = self._get_connection()
        hashed_pw = pwd_context.hash(password)
        # Генерируем токен для верификации
        import secrets
        token = secrets.token_urlsafe(32)
        
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO users (email, hashed_password, verification_token) VALUES (%s, %s, %s) RETURNING id, email",
                    (email, hashed_pw, token)
                )
                conn.commit()
                return dict(cur.fetchone())
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                raise ValueError("Этот email уже зарегистрирован")

    def verify_user(self, token: str) -> bool:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET is_verified = TRUE, verification_token = NULL WHERE verification_token = %s", (token,))
            conn.commit()
            return cur.rowcount > 0

    def get_user_by_email(self, email: str):
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, hashed_password, is_verified FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            return dict(user) if user else None

    # ... остальные методы (create_todo, get_all_todos и т.д.) оставляем без изменений ...
    # (они уже есть в твоем файле)
    
    def get_overdue_tasks_for_user(self, user_id: int, user_email: str):
        """Получить просроченные задачи для email-рассылки"""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT title, due_date FROM todos
                WHERE user_id = %s AND completed = FALSE AND due_date < CURRENT_DATE
            """, (user_id,))
            return cur.fetchall()
            
    # (Не забудь добавить остальные методы из предыдущего шага, если они удалились!)
    def create_todo(self, title: str, description: str, category: str, due_date, user_id: int) -> dict:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO todos (title, description, category, due_date, user_id) 
                   VALUES (%s, %s, %s, %s, %s) 
                   RETURNING id, title, description, category, due_date, completed, created_at""",
                (title, description, category, due_date if due_date else None, user_id)
            )
            conn.commit()
            return dict(cur.fetchone())

    def get_all_todos(self, user_id: int) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, description, category, due_date, completed, created_at 
                FROM todos 
                WHERE user_id = %s
                ORDER BY 
                    CASE WHEN completed THEN 1 ELSE 0 END,
                    due_date ASC NULLS LAST,
                    created_at DESC
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]

    # ... и так далее для update_todo, delete_todo, get_statistics ...