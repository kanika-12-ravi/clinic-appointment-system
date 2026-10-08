# Clinic Appointment Booking System

A web application where patients book doctor appointments online, doctors manage their appointments, and an admin manages doctors.

## Features
- Patient: register, login, search doctors by specialty, book a time slot, view and cancel appointments
- Doctor: login, view own appointments, mark them as completed
- Admin: add and delete doctors
- Double-booking prevention: a doctor cannot be booked twice at the same date and time
- Email confirmation sent to the patient after booking (Gmail SMTP)
- Passwords stored as hashes, role-based access control

## Tech Stack
Python, Flask, SQLite, HTML, CSS

## How to Run
1. Install Python 3
2. Install Flask: `pip install flask`
3. Run: `python app.py`
4. Open http://127.0.0.1:5000
   
## Email Setup (optional)
1. Create a Gmail App Password (Google Account > Security > App passwords)
2. Create a file named `config.py` next to `app.py` with:
   EMAIL_ADDRESS = "yourname@gmail.com"
   EMAIL_APP_PASSWORD = "your-16-letter-app-password"
3. If `config.py` is missing, the app still works but sends no emails.

   
## Default Admin Login (for testing only)
- Email: admin@clinic.com
- Password: admin123

## Database Tables
- users (id, name, email, password, role)
- doctors (id, user_id, specialty, fees)
- appointments (id, patient_id, doctor_id, date, time_slot, status)

## Future Improvements
- Email/SMS reminders
- Forgot password
- Doctor availability calendar
- Online payment

## Author
[Your name], MCA graduate
