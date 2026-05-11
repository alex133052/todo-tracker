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
            # Таблица пользователей
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица задач с user_id
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
            
            # Добавляем колонки, если их нет (для обратной совместимости)
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='todos' AND column_name='user_id'
            """)
            if not cur.fetchone():
                cur.execute("ALTER TABLE todos ADD COLUMN user_id INT")
            
            conn.commit()

    def create_user(self, email: str, password: str) -> dict:
        conn = self._get_connection()
        hashed_pw = pwd_context.hash(password)
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

    def get_user_by_email(self, email: str):
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, hashed_password FROM users WHERE email = %s", (email,))
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

    def get_todos_by_category(self, category: str, user_id: int) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, description, category, due_date, completed, created_at 
                FROM todos 
                WHERE category = %s AND user_id = %s
                ORDER BY due_date ASC NULLS LAST
            """, (category, user_id))
            return [dict(row) for row in cur.fetchall()]

    def search_todos(self, query: str, user_id: int) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            search_term = f"%{query}%"
            cur.execute("""
                SELECT id, title, description, category, due_date, completed, created_at 
                FROM todos 
                WHERE (title ILIKE %s OR description ILIKE %s) AND user_id = %s
                ORDER BY created_at DESC
            """, (search_term, search_term, user_id))
            return [dict(row) for row in cur.fetchall()]

    def get_categories(self, user_id: int) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT category FROM todos 
                WHERE user_id = %s 
                ORDER BY category
            """, (user_id,))
            return [row['category'] for row in cur.fetchall()]

    def update_todo(self, todo_id: int, user_id: int, **kwargs) -> dict:
        conn = self._get_connection()
        updates = []
        values = []
        
        if 'completed' in kwargs:
            updates.append("completed = %s")
            values.append(kwargs['completed'])
        if 'title' in kwargs:
            updates.append("title = %s")
            values.append(kwargs['title'])
        if 'description' in kwargs:
            updates.append("description = %s")
            values.append(kwargs['description'])
        if 'category' in kwargs:
            updates.append("category = %s")
            values.append(kwargs['category'])
        if 'due_date' in kwargs:
            updates.append("due_date = %s")
            values.append(kwargs['due_date'])
        
        if not updates:
            return None
            
        values.append(todo_id)
        values.append(user_id)
        
        query = f"""
            UPDATE todos 
            SET {', '.join(updates)} 
            WHERE id = %s AND user_id = %s
            RETURNING id, title, description, category, due_date, completed, created_at
        """
        
        with conn.cursor() as cur:
            cur.execute(query, values)
            conn.commit()
            result = cur.fetchone()
            return dict(result) if result else None

    def delete_todo(self, todo_id: int, user_id: int) -> bool:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = %s AND user_id = %s", (todo_id, user_id))
            conn.commit()
            return cur.rowcount > 0

    def get_statistics(self, user_id: int) -> dict:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM todos WHERE user_id = %s", (user_id,))
            total = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) FROM todos WHERE completed = TRUE AND user_id = %s", (user_id,))
            completed = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) FROM todos WHERE completed = FALSE AND user_id = %s", (user_id,))
            pending = cur.fetchone()['count']
            
            cur.execute("""
                SELECT COUNT(*) FROM todos 
                WHERE completed = FALSE AND due_date < CURRENT_DATE AND user_id = %s
            """, (user_id,))
            overdue = cur.fetchone()['count']
            
            cur.execute("""
                SELECT category, COUNT(*) as count 
                FROM todos 
                WHERE user_id = %s
                GROUP BY category 
                ORDER BY count DESC
            """, (user_id,))
            by_category = {row['category']: row['count'] for row in cur.fetchall()}
            
            return {
                "total": total,
                "completed": completed,
                "pending": pending,
                "overdue": overdue,
                "by_category": by_category,
                "completion_rate": round((completed / total * 100) if total > 0 else 0, 1)
            }