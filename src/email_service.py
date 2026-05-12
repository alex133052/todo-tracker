import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# НАСТРОЙКИ ПОЧТЫ (берутся из переменных окружения Render)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

def send_email(to_email: str, subject: str, html_content: str):
    """Отправляет email с HTML содержимым"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email

    # Добавляем HTML часть
    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        # Для порта 465 используем SMTP_SSL
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            # Для порта 587 используем STARTTLS
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()  # Шифруем соединение
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
                
        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def send_verification_email(email: str, token: str):
    """Отправляет письмо с подтверждением регистрации"""
    link = f"{APP_URL}/verify?token={token}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{ 
                display: inline-block; 
                background: #667eea; 
                color: white; 
                padding: 12px 24px; 
                text-decoration: none; 
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Подтвердите свою почту</h1>
            <p>Привет! Спасибо за регистрацию в Todo Tracker Pro.</p>
            <p>Нажмите кнопку ниже, чтобы подтвердить свой email:</p>
            <a href="{link}" class="button">Подтвердить email</a>
            <p>Или скопируйте эту ссылку в браузер:</p>
            <p><a href="{link}">{link}</a></p>
            <div class="footer">
                <p>Если вы не регистрировались, просто проигнорируйте это письмо.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email(email, "Подтверждение регистрации в Todo Tracker Pro", html)

def send_overdue_reminder(email: str, tasks: list):
    """Отправляет напоминание о просроченных задачах"""
    tasks_html = "".join([
        f"<li style='margin: 10px 0; padding: 10px; background: #f9f9f9; border-left: 4px solid #f44336;'>{t['title']} (было до: {t['due_date']})</li>" 
        for t in tasks
    ])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .warning {{ background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚠️ У вас есть просроченные задачи!</h1>
            <div class="warning">
                <p>Напоминаем о следующих задачах:</p>
            </div>
            <ul style="list-style: none; padding: 0;">
                {tasks_html}
            </ul>
            <p>Успейте выполнить их как можно скорее!</p>
            <p><a href="{APP_URL}" style="color