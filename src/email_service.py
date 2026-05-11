import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))  # <-- Должно быть SMTP_PORT
SMTP_USER = os.getenv("SMTP_USER", "")         # <-- А это SMTP_USER
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

def send_email(to_email: str, subject: str, html_content: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def send_verification_email(email: str, token: str):
    link = f"{APP_URL}/verify?token={token}"
    html = f"""
    <h1>Подтверди свою почту</h1>
    <p>Привет! Нажми кнопку ниже, чтобы подтвердить email:</p>
    <a href="{link}" style="background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Подтвердить</a>
    <p>Или перейди по ссылке: {link}</p>
    """
    return send_email(email, "Подтверждение регистрации", html)

def send_overdue_reminder(email: str, tasks: list):
    tasks_html = "".join([f"<li>{t['title']} (было до: {t['due_date']})</li>" for t in tasks])
    html = f"""
    <h1>У вас есть просроченные задачи! ⚠️</h1>
    <p>Напоминаем о следующих задачах:</p>
    <ul>{tasks_html}</ul>
    <p>Успейте выполнить их!</p>
    """
    return send_email(email, "Напоминание: просроченные задачи", html)