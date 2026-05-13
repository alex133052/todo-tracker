import os
import resend

# Настраиваем API ключ
resend.api_key = os.getenv("RESEND_API_KEY")

APP_URL = os.getenv("APP_URL", "http://localhost:8000")

# Email аккаунта Resend (на который разрешена отправка в Sandbox)
TEST_EMAIL = "alexi330@gmail.com"  # ← Твой email из Resend

def send_email(to_email: str, subject: str, html_content: str):
    """
    В Sandbox режиме Resend отправляет письма ТОЛЬКО на verified email.
    Поэтому все письма шлем на TEST_EMAIL, но в логах показываем оригинального получателя.
    """
    try:
        params = {
            "from": "onboarding@resend.dev",
            "to": TEST_EMAIL,  # ← Всегда шлем на ПРОВЕРЕННЫЙ email
            "subject": subject,
            "html": html_content
        }
        
        resend.Emails.send(params)
        print(f"✅ Email sent to {TEST_EMAIL} via Resend (original recipient: {to_email})")
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