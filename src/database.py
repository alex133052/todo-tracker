import psycopg2
import os
from psycopg2.extras import RealDictCursor  # <--- ДОБАВИТЬ ЭТОТ ИМПОРТ

class TodoDatabase:
    def __init__(self):
        host = os.getenv("DATABASE_HOST", "localhost")
        password = os.getenv("DATABASE_PASSWORD", "secret")
        db_name = os.getenv("DATABASE_NAME", "postgres")  # Используем существующую БД
        user = os.getenv("DATABASE_USER", "postgres")
        
        self.dsn = f"dbname={db_name} user={user} password={password} host={host} port=5432"
        self._conn = None

    def _get_connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
            # Важно: устанавливаем factory для курсора, чтобы возвращались словари
            self._conn.cursor_factory = RealDictCursor
        return self._conn

    def init_db(self):
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def create_todo(self, title: str, description: str) -> dict:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO todos (title, description) VALUES (%s, %s) RETURNING id, title, description, completed",
                (title, description)
            )
            conn.commit()
            # fetchone() теперь вернёт словарь благодаря RealDictCursor
            return dict(cur.fetchone())

    def get_all_todos(self) -> list:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, description, completed FROM todos ORDER BY id DESC")
            # fetchall() вернёт список словарей
            return [dict(row) for row in cur.fetchall()]

    def update_todo(self, todo_id: int, completed: bool) -> bool:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE todos SET completed = %s WHERE id = %s", (completed, todo_id))
            conn.commit()
            return cur.rowcount > 0

    def delete_todo(self, todo_id: int) -> bool:
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = %s", (todo_id,))
            conn.commit()
            return cur.rowcount > 0