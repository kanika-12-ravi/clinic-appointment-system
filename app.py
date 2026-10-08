from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
import sqlite3
from email_service import send_booking_email

app = Flask(__name__)
app.secret_key = "change-this-to-any-random-text"

TIME_SLOTS = [
    "10:00 AM", "11:00 AM", "12:00 PM",
    "02:00 PM", "03:00 PM", "04:00 PM",
]


def get_db():
    conn = sqlite3.connect("clinic.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'patient'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            specialty TEXT NOT NULL,
            fees INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'booked'
        )
    """)
    # Safety net: the database itself refuses two 'booked' appointments
    # for the same doctor, date and time slot
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS unique_booking
        ON appointments (doctor_id, date, time_slot)
        WHERE status = 'booked'
    """)

    # Create a default admin account (only the first time)
    admin = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("admin@clinic.com",)
    ).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("Admin", "admin@clinic.com", generate_password_hash("admin123"), "admin"),
        )

    conn.commit()
    conn.close()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        hashed = generate_password_hash(password)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed),
            )
            conn.commit()
            conn.close()
            return render_template("register.html", success="Account created successfully!")
        except sqlite3.IntegrityError:
            return render_template("register.html", error="This email is already registered.")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT id, name, password, role FROM users WHERE email = ?", (email,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["email"] = email
            return redirect("/dashboard")

        return render_template("login.html", error="Wrong email or password.")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    return render_template("dashboard.html", name=session["name"], role=session["role"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/doctors")
def doctors():
    if "user_id" not in session:
        return redirect("/login")

    search = request.args.get("specialty", "").strip()
    conn = get_db()
    rows = conn.execute(
        """
        SELECT doctors.id, users.name, doctors.specialty, doctors.fees
        FROM doctors JOIN users ON doctors.user_id = users.id
        WHERE doctors.specialty LIKE ?
        """,
        ("%" + search + "%",),
    ).fetchall()
    conn.close()
    return render_template("doctors.html", doctors=rows, search=search)


@app.route("/book/<int:doctor_id>", methods=["GET", "POST"])
def book(doctor_id):
    # Only logged-in patients can book
    if session.get("role") != "patient":
        return redirect("/login")

    conn = get_db()
    doctor = conn.execute(
        """
        SELECT doctors.id, users.name, doctors.specialty, doctors.fees
        FROM doctors JOIN users ON doctors.user_id = users.id
        WHERE doctors.id = ?
        """,
        (doctor_id,),
    ).fetchone()

    if not doctor:
        conn.close()
        return redirect("/doctors")

    min_date = date.today().isoformat()
    error = None
    success = None

    if request.method == "POST":
        chosen_date = request.form["date"]
        time_slot = request.form["time_slot"]

        # Check 1: the date must be valid and not in the past
        try:
            parsed = datetime.strptime(chosen_date, "%Y-%m-%d").date()
        except ValueError:
            parsed = None

        if parsed is None or parsed < date.today():
            error = "Please choose today or a future date."
        elif time_slot not in TIME_SLOTS:
            error = "Please choose a valid time slot."
        else:
            # Check 2: is this doctor already booked at that date and time?
            doctor_busy = conn.execute(
                """
                SELECT id FROM appointments
                WHERE doctor_id = ? AND date = ? AND time_slot = ? AND status = 'booked'
                """,
                (doctor_id, chosen_date, time_slot),
            ).fetchone()

            # Check 3: does this patient already have another visit at that time?
            patient_busy = conn.execute(
                """
                SELECT id FROM appointments
                WHERE patient_id = ? AND date = ? AND time_slot = ? AND status = 'booked'
                """,
                (session["user_id"], chosen_date, time_slot),
            ).fetchone()

            if doctor_busy:
                error = "Sorry, this slot is already booked. Please choose another time."
            elif patient_busy:
                error = "You already have an appointment at this time."
            else:
                try:
                    conn.execute(
                        """
                        INSERT INTO appointments (patient_id, doctor_id, date, time_slot)
                        VALUES (?, ?, ?, ?)
                        """,
                        (session["user_id"], doctor_id, chosen_date, time_slot),
                    )
                    conn.commit()
                    success = "Appointment booked successfully!"
                    send_booking_email(session["name"], session.get("email"), doctor["name"], doctor["specialty"], chosen_date, time_slot)
                except sqlite3.IntegrityError:
                    error = "Sorry, this slot was just taken. Please choose another time."

    conn.close()
    return render_template(
        "book.html",
        doctor=doctor,
        slots=TIME_SLOTS,
        min_date=min_date,
        error=error,
        success=success,
    )


@app.route("/my-appointments")
def my_appointments():
    if session.get("role") != "patient":
        return redirect("/login")

    conn = get_db()
    rows = conn.execute(
        """
        SELECT appointments.id, appointments.date, appointments.time_slot,
               appointments.status, users.name AS doctor_name, doctors.specialty
        FROM appointments
        JOIN doctors ON appointments.doctor_id = doctors.id
        JOIN users ON doctors.user_id = users.id
        WHERE appointments.patient_id = ?
        """,
        (session["user_id"],),
    ).fetchall()
    conn.close()

    # Newest date first; inside one date, earlier time first
    rows = sorted(rows, key=lambda r: TIME_SLOTS.index(r["time_slot"]))
    rows = sorted(rows, key=lambda r: r["date"], reverse=True)
    return render_template("my_appointments.html", appointments=rows)


@app.route("/cancel/<int:appointment_id>")
def cancel(appointment_id):
    if session.get("role") != "patient":
        return redirect("/login")

    conn = get_db()
    # The patient_id check makes sure you can cancel only your own appointment
    conn.execute(
        """
        UPDATE appointments SET status = 'cancelled'
        WHERE id = ? AND patient_id = ? AND status = 'booked'
        """,
        (appointment_id, session["user_id"]),
    )
    conn.commit()
    conn.close()
    return redirect("/my-appointments")


@app.route("/doctor")
def doctor_dashboard():
    # Only logged-in doctors can open this page
    if session.get("role") != "doctor":
        return redirect("/login")

    conn = get_db()
    doc = conn.execute(
        "SELECT id FROM doctors WHERE user_id = ?", (session["user_id"],)
    ).fetchone()

    if not doc:
        conn.close()
        return redirect("/dashboard")

    rows = conn.execute(
        """
        SELECT appointments.id, appointments.date, appointments.time_slot,
               appointments.status, users.name AS patient_name
        FROM appointments
        JOIN users ON appointments.patient_id = users.id
        WHERE appointments.doctor_id = ?
        """,
        (doc["id"],),
    ).fetchall()
    conn.close()

    # Earliest date first; inside one date, earlier time first
    rows = sorted(rows, key=lambda r: (r["date"], TIME_SLOTS.index(r["time_slot"])))
    pending = sum(1 for r in rows if r["status"] == "booked")
    return render_template(
        "doctor_dashboard.html",
        name=session["name"],
        appointments=rows,
        pending=pending,
    )


@app.route("/complete/<int:appointment_id>")
def complete(appointment_id):
    if session.get("role") != "doctor":
        return redirect("/login")

    conn = get_db()
    doc = conn.execute(
        "SELECT id FROM doctors WHERE user_id = ?", (session["user_id"],)
    ).fetchone()

    if doc:
        # The doctor_id check makes sure a doctor can complete only their own appointments
        conn.execute(
            """
            UPDATE appointments SET status = 'completed'
            WHERE id = ? AND doctor_id = ? AND status = 'booked'
            """,
            (appointment_id, doc["id"]),
        )
        conn.commit()
    conn.close()
    return redirect("/doctor")


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if session.get("role") != "admin":
        return redirect("/login")

    error = None
    success = None

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        specialty = request.form["specialty"]
        fees = request.form["fees"]

        try:
            conn = get_db()
            cur = conn.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, 'doctor')",
                (name, email, generate_password_hash(password)),
            )
            conn.execute(
                "INSERT INTO doctors (user_id, specialty, fees) VALUES (?, ?, ?)",
                (cur.lastrowid, specialty, fees),
            )
            conn.commit()
            conn.close()
            success = "Doctor added successfully!"
        except sqlite3.IntegrityError:
            error = "This email is already registered."

    conn = get_db()
    rows = conn.execute(
        """
        SELECT doctors.id, users.name, doctors.specialty, doctors.fees
        FROM doctors JOIN users ON doctors.user_id = users.id
        """
    ).fetchall()
    conn.close()
    return render_template("admin.html", doctors=rows, error=error, success=success)


@app.route("/admin/delete/<int:doctor_id>")
def delete_doctor(doctor_id):
    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()
    doc = conn.execute("SELECT user_id FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if doc:
        conn.execute("DELETE FROM appointments WHERE doctor_id = ?", (doctor_id,))
        conn.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (doc["user_id"],))
        conn.commit()
    conn.close()
    return redirect("/admin")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)