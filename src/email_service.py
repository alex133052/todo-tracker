import requests
import os

UNISENDER_API_KEY = os.getenv("UNISENDER_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@todo-tracker.app")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")

API_URL = "https://go2.unisender.ru/api/v3/emails/transactional"

def send_email(to_email: str, subject: str, html_content: str):
    """Отправляет email через UniSender Go API"""
    headers = {
        "Authorization": f"Api-Key {UNISENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": {"name": "Todo Tracker Pro", "email": EMAIL_FROM},
        "to": [{"email": to_email}],
        "subject": subject,
        "html": html_content
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        print(f"✅ Email sent to {to_email} via UniSender API")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        if hasattr(response, 'text'):
            print(f"📄 Response: {response.text}")
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
        tasks_list += f"<li style='margin: 5px 0;'>🔴 <b>{t['title']}</b> (срок: {t['due_date']})</li>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif; color: #333;">
        <h2 style="color: #d9534f;">⚠️ У вас есть просроченные задачи!</h2>
        <p>Напоминаем, что следующие задачи не выполнены в срок:</p>
        <ul style="padding-left: 20px;">
            {tasks_list}
        </ul>
        <p>Пожалуйста, зайдите в приложение и обновите статус.</p>
    </body>
    </html>
    """
    return send_email(email, "Напоминание: Просроченные задачи", html)