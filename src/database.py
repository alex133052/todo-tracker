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
            # Создаём таблицу пользователей
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
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='is_verified'
            """)
            if not cur.fetchone():
                cur.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE")
            
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='verification_token'
            """)
            if not cur.fetchone():
                cur.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
            
            # Создаём таблицу задач
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
            
            # Добавляем user_id, если нет
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='todos' AND column_name='user_id'
            """)
            if not cur.fetchone():
                cur.execute("ALTER TABLE todos ADD COLUMN user_id INT")
            
            conn.commit()

    def create_user(self, email: str, password: str) -> dict:
        conn = self._get_connection()
        hashed_pw = pwd_context.hash(password)
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
            cur.execute(
                "UPDATE users SET is_verified = TRUE, verification_token = NULL WHERE verification_token = %s",
                (token,)
            )
            conn.commit()
            return cur.rowcount > 0

    def get_user_by_email(self, email: str):
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, hashed_password, is_verified FROM users WHERE email = %s",
                (email,)
            )
            user = cur.fetchone()
            return dict(user) if user else None

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

    def update_todo(self, todo_id: int, user_id: int, **kwargs) -> dict:
        conn = self._get_connection()
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['title', 'description', 'category', 'due_date', 'completed']:
                updates.append(f"{key} = %s")
                values.append(value)
        
        if not updates:
            return None
        
        values.append(todo_id)
        values.append(user_id)
        
        with conn.cursor() as cur:
            cur.execute(
                f"""UPDATE todos SET {', '.join(updates)} 
                    WHERE id = %s AND user_id = %s 
                    RETURNING id, title, description, category, due_date, completed, created_at""",
                values
            )
            conn.commit()
            result = cur.fetchone()
            return dict(result) if result else None

    def delete_todo(self, todo_id: int, user_id: int) -> bool:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM todos WHERE id = %s AND user_id = %s",
                (todo_id, user_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def get_statistics(self, user_id: int) -> dict:
        """Получить статистику задач пользователя"""
        conn = self._get_connection()
        with conn.cursor() as cur:
            # Всего задач
            cur.execute("SELECT COUNT(*) FROM todos WHERE user_id = %s", (user_id,))
            total = cur.fetchone()['count']
            
            # Выполнено
            cur.execute("SELECT COUNT(*) FROM todos WHERE user_id = %s AND completed = TRUE", (user_id,))
            completed = cur.fetchone()['count']
            
            # В процессе (не выполнено)
            pending = total - completed
            
            # Просрочено
            cur.execute("""
                SELECT COUNT(*) FROM todos 
                WHERE user_id = %s AND completed = FALSE AND due_date < CURRENT_DATE
            """, (user_id,))
            overdue = cur.fetchone()['count']
            
            # Процент выполнения
            completion_rate = round((completed / total * 100) if total > 0 else 0)
            
            return {
                "total": total,
                "completed": completed,
                "pending": pending,
                "overdue": overdue,
                "completion_rate": completion_rate
            }

    def get_overdue_report(self):
        """
        Возвращает словарь: { 'email_пользователя': [список просроченных задач] }
        """
        conn = self._get_connection()
        report = {}
        
        with conn.cursor() as cur:
            # 1. Берем все просроченные НЕ выполненные задачи
            cur.execute("""
                SELECT u.email, t.title, t.due_date 
                FROM todos t
                JOIN users u ON t.user_id = u.id
                WHERE t.completed = FALSE 
                AND t.due_date < CURRENT_DATE
            """)
            rows = cur.fetchall()
            
            # 2. Группируем их по email
            for row in rows:
                email = row['email']
                if email not in report:
                    report[email] = []
                report[email].append({
                    'title': row['title'],
                    'due_date': str(row['due_date'])
                })
                
        return report