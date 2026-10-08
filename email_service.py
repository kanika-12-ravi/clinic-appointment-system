import smtplib
from email.message import EmailMessage

try:
    from config import EMAIL_ADDRESS, EMAIL_APP_PASSWORD
except ImportError:
    EMAIL_ADDRESS = None
    EMAIL_APP_PASSWORD = None


def send_email(to_address, subject, body):
    # If email settings are missing, skip quietly (the app still works)
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD or not to_address:
        return False

    try:
        msg = EmailMessage()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Email error:", e)
        return False


def send_booking_email(patient_name, patient_email, doctor_name, specialty, date, time_slot):
    body = (
        "Hello " + patient_name + ",\n\n"
        "Your appointment is confirmed.\n"
        "Doctor: " + doctor_name + " (" + specialty + ")\n"
        "Date: " + date + "\n"
        "Time: " + time_slot + "\n\n"
        "Thank you,\nCity Clinic"
    )
    return send_email(patient_email, "Appointment confirmed - City Clinic", body)