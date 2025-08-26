import os, smtplib, ssl
from email.message import EmailMessage
import os
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()  # <-- this loads your .env file


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")      # your email
SMTP_PASS = os.getenv("SMTP_PASS")      # app password
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER or "")

def send_email(to_email: str, subject: str, body: str) -> bool:
    if not to_email:
        return False
    if not (SMTP_USER and SMTP_PASS and FROM_EMAIL):
        print("[mailer] Email not configured. Set SMTP_USER/SMTP_PASS/FROM_EMAIL.")
        return False
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"[mailer] Sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print("[mailer] Send failed:", e)
        return False
