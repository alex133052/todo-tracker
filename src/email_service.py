import os
import resend

# Настраиваем API ключ
resend.api_key = os.getenv("RESEND_API_KEY")

APP_URL = os.getenv("APP_URL", "http://localhost:8000")

# В Sandbox режиме письма уходят только на email, указанный при регистрации Resend
# Укажи здесь свою личную почту (на которую зарегистрировал Resend)
TEST_EMAIL = "alex1330@gmail.com"  # ← ЗАМЕНИ НА СВОЮ!

def send_email(to_email: str, subject: str, html_content: str):
    try:
        params = {
            "from": "onboarding@resend.dev",  # Стандартный адрес для Sandbox
            "to": to_email,  # ИЗМЕНЕНИЕ ЗДЕСЬ: отправляем тому, кто просил (to_email), а не себе
            "subject": subject,
            "html": html_content
        }
        
        resend.Emails.send(params)
        print(f"✅ Email sent via Resend")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def send_verification_email(email: str, token: str):
    link = f"{APP_URL}/verify?token={token}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif;">
        <h1>📧 Подтвердите свою почту</h1>
        <p>Привет! Спасибо за регистрацию в Todo Tracker Pro.</p>
        <p><a href="{link}" style="background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0;">Подтвердить email</a></p>
        <p>Или скопируй ссылку: {link}</p>
    </body>
    </html>
    """
    
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