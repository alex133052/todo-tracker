import os
import resend

# Настраиваем API ключ
resend.api_key = os.getenv("RESEND_API_KEY")

APP_URL = os.getenv("APP_URL", "http://localhost:8000")

# В режиме Sandbox (бесплатно) письма уходят только на ТВОЙ email, который ты указал при регистрации Resend
# Для тестов укажи здесь свою личную почту
TEST_EMAIL = "твоя_личная_почта@gmail.com" 

def send_email(to_email: str, subject: str, html_content: str):
    try:
        params = {
            "from": "onboarding@resend.dev", # Стандартный адрес для Sandbox
            "to": TEST_EMAIL, # В Sandbox отправляем только себе
            "subject": subject,
            "html": html_content
        }
        
        resend.Emails.send(params)
        print(f"✅ Email sent to {to_email} via Resend")
        return True
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def send_verification_email(email: str, token: str):
    link = f"{APP_URL}/verify?token={token}"
    html = """
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif;">
        <h1>Подтвердите почту</h1>
        <p>Нажмите ссылку: <a href="LINK_PLACEHOLDER">LINK_PLACEHOLDER</a></p>
    </body>
    </html>
    """.replace("LINK_PLACEHOLDER", link)
    
    return send_email(email, "Подтверждение регистрации", html)

def send_overdue_reminder(email: str, tasks: list):
    tasks_list = ""
    for t in tasks:
        tasks_list += f"<li>🔴 {t['title']} (до: {t['due_date']})</li>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: sans-serif;">
        <h2>⚠️ Просроченные задачи</h2>
        <ul>{tasks_list}</ul>
    </body>
    </html>
    """
    return send_email(email, "Напоминание: Просроченные задачи", html)