import psycopg2
import os
from psycopg2.extras import RealDictCursor
from datetime import datetime

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
            # 1. Создаём таблицу, если её нет
            cur.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. ДОБАВЛЯЕМ новые колонки, если их нет (важно для обновления!)
            # Проверяем и добавляем column 'category'
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='todos' AND column_name='category'
            """)
            if not cur.fetchone():
                cur.execute("ALTER TABLE todos ADD COLUMN category TEXT DEFAULT 'Общее'")
                
            # Проверяем и добавляем column 'due_date'
            cur.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='todos' AND column_name='due_date'
            """)
            if not cur.fetchone():
                cur.execute("ALTER TABLE todos ADD COLUMN due_date DATE")
                
            conn.commit()

    def create_todo(self, title: str, description: str, category: str = "Общее", due_date: str = None) -> dict:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO todos (title, description, category, due_date) 
                   VALUES (%s, %s, %s, %s) 
                   RETURNING id, title, description, category, due_date, completed, created_at""",
                (title, description, category, due_date if due_date else None)
            )
            conn.commit()
            return dict(cur.fetchone())

    def get_all_todos(self) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, description, category, due_date, completed, created_at 
                FROM todos 
                ORDER BY 
                    CASE WHEN completed THEN 1 ELSE 0 END,
                    due_date ASC NULLS LAST,
                    created_at DESC
            """)
            return [dict(row) for row in cur.fetchall()]

    def get_todos_by_category(self, category: str) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, description, category, due_date, completed, created_at 
                FROM todos 
                WHERE category = %s
                ORDER BY due_date ASC NULLS LAST
            """, (category,))
            return [dict(row) for row in cur.fetchall()]

    def search_todos(self, query: str) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            search_term = f"%{query}%"
            cur.execute("""
                SELECT id, title, description, category, due_date, completed, created_at 
                FROM todos 
                WHERE title ILIKE %s OR description ILIKE %s
                ORDER BY created_at DESC
            """, (search_term, search_term))
            return [dict(row) for row in cur.fetchall()]

    def get_categories(self) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT category FROM todos ORDER BY category")
            return [row['category'] for row in cur.fetchall()]

    def update_todo(self, todo_id: int, **kwargs) -> dict:
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
        query = f"""
            UPDATE todos 
            SET {', '.join(updates)} 
            WHERE id = %s 
            RETURNING id, title, description, category, due_date, completed, created_at
        """
        
        with conn.cursor() as cur:
            cur.execute(query, values)
            conn.commit()
            result = cur.fetchone()
            return dict(result) if result else None

    def delete_todo(self, todo_id: int) -> bool:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
            conn.commit()
            return cur.rowcount > 0

    def get_statistics(self) -> dict:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM todos")
            total = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) FROM todos WHERE completed = TRUE")
            completed = cur.fetchone()['count']
            
            cur.execute("SELECT COUNT(*) FROM todos WHERE completed = FALSE")
            pending = cur.fetchone()['count']
            
            cur.execute("""
                SELECT COUNT(*) FROM todos 
                WHERE completed = FALSE AND due_date < CURRENT_DATE
            """)
            overdue = cur.fetchone()['count']
            
            cur.execute("""
                SELECT category, COUNT(*) as count 
                FROM todos 
                GROUP BY category 
                ORDER BY count DESC
            """)
            by_category = {row['category']: row['count'] for row in cur.fetchall()}
            
            return {
                "total": total,
                "completed": completed,
                "pending": pending,
                "overdue": overdue,
                "by_category": by_category,
                "completion_rate": round((completed / total * 100) if total > 0 else 0, 1)
            }