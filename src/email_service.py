import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
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
        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
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
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
            .container { max-width: 600px; margin: 0 auto; padding: 20px; }
            .button { 
                display: inline-block; 
                background: #667eea; 
                color: white; 
                padding: 12px 24px; 
                text-decoration: none; 
                border-radius: 5px;
                margin: 20px 0;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Подтвердите свою почту</h1>
            <p>Привет! Спасибо за регистрацию в Todo Tracker Pro.</p>
            <p>Нажмите кнопку ниже, чтобы подтвердить свой email:</p>
            <a href="LINK_PLACEHOLDER" class="button">Подтвердить email</a>
            <p>Или скопируйте эту ссылку: LINK_PLACEHOLDER</p>
        </div>
    </body>
    </html>
    """.replace("LINK_PLACEHOLDER", link)
    
    return send_email(email, "Подтверждение регистрации", html)

def send_overdue_reminder(email: str, tasks: list):
    tasks_list = ""
    for t in tasks:
        tasks_list += f"<li>{t['title']} (до: {t['due_date']})</li>"
    
    html = """
    <!DOCTYPE html>
    <html>
    <body>
        <h1>У вас есть просроченные задачи!</h1>
        <ul>TASKS_PLACEHOLDER</ul>
    </body>
    </html>
    """.replace("TASKS_PLACEHOLDER", tasks_list)
    
    return send_email(email, "Напоминание: просроченные задачи", html)