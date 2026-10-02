"""
Student Smart Planner
======================
A Flask + MySQL web application that helps students manage subjects,
tasks/assignments, exams, and study schedules from one dashboard.

Run with:  python app.py
"""

import smtplib
from calendar import monthrange
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config

app = Flask(__name__)
app.config.from_object(Config)


def get_next_due_date(current_due_date, recurrence_type, recurrence_interval=1):
    """Return the next occurrence date for a recurring task."""
    if not recurrence_type or recurrence_type == "none":
        return current_due_date

    step = max(1, int(recurrence_interval or 1))

    if recurrence_type == "daily":
        return current_due_date + timedelta(days=step)
    if recurrence_type == "weekly":
        return current_due_date + timedelta(days=7 * step)
    if recurrence_type == "monthly":
        month = current_due_date.month - 1 + step
        year = current_due_date.year + month // 12
        month = month % 12 + 1
        last_day = monthrange(year, month)[1]
        day = min(current_due_date.day, last_day)
        return current_due_date.replace(year=year, month=month, day=day)
    return current_due_date


def calculate_grade_letter(score):
    """Return a letter grade based on a percentage score."""
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "F"

    if value >= 85:
        return "A"
    if value >= 70:
        return "B"
    if value >= 50:
        return "C"
    if value >= 35:
        return "D"
    return "F"


def build_reminder_items(tasks, exams, today=None):
    """Create a normalized reminder list from tasks and exams."""
    reference_day = today or date.today()
    reminders = []

    def safe_url(endpoint):
        try:
            from flask import current_app
            current_app._get_current_object()
            return url_for(endpoint)
        except RuntimeError:
            return "/tasks" if endpoint == "tasks" else "/exams"

    for task in tasks or []:
        if task.get("status") == "Completed":
            continue
        due_date = task.get("due_date")
        if not due_date:
            continue
        reminder_days = int(task.get("reminder_days_before") or 1)
        reminder_date = due_date - timedelta(days=reminder_days)
        if reminder_date >= reference_day:
            reminders.append({
                "title": task.get("title"),
                "detail": f"Task due on {due_date}",
                "reminder_date": reminder_date,
                "kind": "task",
                "link": safe_url("tasks"),
                "subject_name": task.get("subject_name") or "General",
            })

    for exam in exams or []:
        exam_date = exam.get("exam_date")
        if not exam_date:
            continue
        reminder_days = int(exam.get("reminder_days_before") or 3)
        reminder_date = exam_date - timedelta(days=reminder_days)
        if reminder_date >= reference_day:
            reminders.append({
                "title": exam.get("exam_name") or "Exam",
                "detail": f"Exam on {exam_date}",
                "reminder_date": reminder_date,
                "kind": "exam",
                "link": safe_url("exams"),
                "subject_name": exam.get("subject_name") or "General",
            })

    reminders.sort(key=lambda item: item["reminder_date"])
    return reminders


def build_reminder_email_body(reminders, user_name="Student"):
    """Build the plain-text email body for upcoming reminders."""
    if not reminders:
        return (
            f"Hi {user_name},\n\n"
            "You currently have no upcoming reminders in Student Smart Planner.\n\n"
            "Open the app to plan your next study session."
        )

    lines = [
        f"Hi {user_name},",
        "",
        f"You have {len(reminders)} reminder(s) coming up:",
        "",
    ]

    for index, reminder in enumerate(reminders, start=1):
        reminder_date = reminder.get("reminder_date")
        if hasattr(reminder_date, "isoformat"):
            reminder_date = reminder_date.isoformat()
        lines.append(
            f"{index}. {reminder.get('title', 'Untitled')} ({reminder.get('kind', 'task').title()}) - {reminder_date}"
        )
        lines.append(f"   {reminder.get('detail', 'No additional details available.')}")

    lines.extend([
        "",
        "Please review your planner and prepare in advance.",
        "",
        "Best,",
        "Student Smart Planner",
    ])
    return "\n".join(lines)


def send_reminder_email(user_email, user_name, reminders):
    """Send a plain-text reminder summary by SMTP when the app is configured for email."""
    smtp_host = app.config.get("SMTP_HOST")
    if not smtp_host or not user_email:
        return False

    sender = app.config.get("SMTP_SENDER") or app.config.get("SMTP_USERNAME") or "noreply@studentplanner.local"
    subject = f"Upcoming reminders: {len(reminders)} item(s)"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = user_email
    message["Subject"] = subject
    message.set_content(build_reminder_email_body(reminders, user_name))

    try:
        with smtplib.SMTP(smtp_host, app.config.get("SMTP_PORT", 587), timeout=10) as server:
            if app.config.get("SMTP_USE_TLS", True):
                server.starttls()
            username = app.config.get("SMTP_USERNAME")
            password = app.config.get("SMTP_PASSWORD")
            if username and password:
                server.login(username, password)
            server.send_message(message)
        return True
    except Exception:
        return False


# ------------------------------------------------------------
# Database helper
# ------------------------------------------------------------
def ensure_schema(connection):
    """Ensure required tables and columns exist for the current app version."""
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        "SELECT COUNT(*) AS total FROM information_schema.tables WHERE table_schema = %s AND table_name = 'notes'",
        (app.config["MYSQL_DB"],),
    )
    if cursor.fetchone()["total"] == 0:
        cursor.execute(
            """
            CREATE TABLE notes (
                note_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                subject_id INT,
                title VARCHAR(150) NOT NULL,
                content TEXT,
                resource_url VARCHAR(255),
                tags VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE SET NULL
            )
            """
        )

    cursor.execute(
        "SELECT COUNT(*) AS total FROM information_schema.tables WHERE table_schema = %s AND table_name = 'grades'",
        (app.config["MYSQL_DB"],),
    )
    if cursor.fetchone()["total"] == 0:
        cursor.execute(
            """
            CREATE TABLE grades (
                grade_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                subject_id INT,
                assessment_name VARCHAR(150) NOT NULL,
                score DECIMAL(5,2) NOT NULL,
                max_score DECIMAL(5,2) NOT NULL,
                grade_date DATE NOT NULL,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE SET NULL
            )
            """
        )

    cursor.execute(
        "SELECT COUNT(*) AS total FROM information_schema.tables WHERE table_schema = %s AND table_name = 'study_groups'",
        (app.config["MYSQL_DB"],),
    )
    if cursor.fetchone()["total"] == 0:
        cursor.execute(
            """
            CREATE TABLE study_groups (
                group_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                group_name VARCHAR(150) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE group_members (
                group_member_id INT AUTO_INCREMENT PRIMARY KEY,
                group_id INT NOT NULL,
                user_id INT NOT NULL,
                role ENUM('admin', 'member') NOT NULL DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_group_member (group_id, user_id),
                FOREIGN KEY (group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """
        )

    cursor.execute(
        "SELECT COUNT(*) AS total FROM information_schema.columns WHERE table_schema = %s AND table_name = 'users' AND column_name = 'role'",
        (app.config["MYSQL_DB"],),
    )
    if cursor.fetchone()["total"] == 0:
        cursor.execute("ALTER TABLE users ADD COLUMN role ENUM('student', 'teacher', 'admin') NOT NULL DEFAULT 'student'")

    for table_name, column_specs in {
        "tasks": [
            ("is_recurring", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("recurrence_type", "ENUM('daily', 'weekly', 'monthly') NULL DEFAULT NULL"),
            ("recurrence_interval", "INT NOT NULL DEFAULT 1"),
            ("reminder_days_before", "INT NOT NULL DEFAULT 1"),
        ],
        "exams": [
            ("reminder_days_before", "INT NOT NULL DEFAULT 3"),
        ],
    }.items():
        for column_name, column_def in column_specs:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
                """,
                (app.config["MYSQL_DB"], table_name, column_name),
            )
            if cursor.fetchone()["total"] == 0:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    connection.commit()
    cursor.close()


def get_db_connection():
    """Open a new MySQL connection using settings from config.py."""
    connection_options = {
        "host": app.config["MYSQL_HOST"],
        "user": app.config["MYSQL_USER"],
        "password": app.config["MYSQL_PASSWORD"],
        "port": app.config["MYSQL_PORT"],
    }

    try:
        connection = mysql.connector.connect(
            **connection_options,
            database=app.config["MYSQL_DB"],
        )
        ensure_schema(connection)
        return connection
    except mysql.connector.Error as error:
        if error.errno != 1049:
            raise

        setup_connection = mysql.connector.connect(**connection_options)
        setup_cursor = setup_connection.cursor()
        schema_path = Path(__file__).resolve().parent / "database" / "schema.sql"
        schema_statements = schema_path.read_text(encoding="utf-8").split(";")
        for statement in schema_statements:
            if statement.strip():
                setup_cursor.execute(statement)
        setup_connection.commit()
        setup_cursor.close()
        setup_connection.close()

        connection = mysql.connector.connect(
            **connection_options,
            database=app.config["MYSQL_DB"],
        )
        ensure_schema(connection)
        return connection


# ------------------------------------------------------------
# Auth helper decorator
# ------------------------------------------------------------
def login_required(view_func):
    """Redirect to login page if the user is not authenticated."""
    from functools import wraps

    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


# ------------------------------------------------------------
# Home
# ------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ------------------------------------------------------------
# Registration
# ------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "student").strip().lower()
        if role not in {"student", "teacher", "admin"}:
            role = "student"

        # ---- Validation ----
        if not full_name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for duplicate email
        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("An account with this email already exists.", "danger")
            cursor.close()
            conn.close()
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            (full_name, email, password_hash, role),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ------------------------------------------------------------
# Login
# ------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "danger")
            return render_template("login.html")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["user_id"]
            session["full_name"] = user["full_name"]
            session["role"] = user.get("role", "student")
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ------------------------------------------------------------
# Demo login
# ------------------------------------------------------------
@app.route("/demo")
def demo_login():
    demo_email = "demo@studentplanner.local"
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT user_id, full_name, role FROM users WHERE email = %s", (demo_email,))
    user = cursor.fetchone()

    if user:
        user_id = user["user_id"]
        full_name = user["full_name"]
        role = user.get("role", "student")
    else:
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            ("Demo Student", demo_email, generate_password_hash("demo123"), "student"),
        )
        user_id = cursor.lastrowid
        full_name = "Demo Student"
        role = "student"

    cursor.execute("SELECT COUNT(*) AS total FROM subjects WHERE user_id = %s", (user_id,))
    has_subjects = cursor.fetchone()["total"] > 0

    if not has_subjects:
        subjects = [
            (user_id, "Computer Science", "CS101", "Dr. Mehta", "Algorithms and data structures"),
            (user_id, "Web Development", "WD201", "Prof. Shah", "Modern web application development"),
            (user_id, "Database Systems", "DB301", "Dr. Rao", "Relational databases and SQL"),
            (user_id, "Software Engineering", "SE205", "Prof. Kulkarni", "Software design and testing"),
        ]
        cursor.executemany(
            """INSERT INTO subjects
               (user_id, subject_name, subject_code, teacher_name, description)
               VALUES (%s, %s, %s, %s, %s)""",
            subjects,
        )
        cursor.execute(
            "SELECT subject_id, subject_name FROM subjects WHERE user_id = %s ORDER BY subject_id",
            (user_id,),
        )
        subject_ids = {row["subject_name"]: row["subject_id"] for row in cursor.fetchall()}
        tomorrow = date.today() + timedelta(days=1)

        cursor.executemany(
            """INSERT INTO tasks
               (user_id, subject_id, title, description, due_date, priority, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (user_id, subject_ids["Web Development"], "Build Flask Portfolio", "Create the project portfolio page", tomorrow, "High", "Pending"),
                (user_id, subject_ids["Computer Science"], "Algorithms Practice Set", "Complete the recursion exercises", date.today() + timedelta(days=3), "Medium", "Pending"),
                (user_id, subject_ids["Database Systems"], "SQL Query Worksheet", "Finish joins and aggregation queries", date.today() - timedelta(days=2), "Low", "Completed"),
            ],
        )
        cursor.executemany(
            """INSERT INTO exams
               (user_id, subject_id, exam_name, exam_date, exam_time, venue, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [
                (user_id, subject_ids["Computer Science"], "Data Structures Midterm", date.today() + timedelta(days=4), "10:00:00", "Room 204", "Bring a calculator"),
                (user_id, subject_ids["Web Development"], "Web Technology Quiz", date.today() + timedelta(days=9), "14:00:00", "Lab 3", "Covers Flask and templates"),
            ],
        )
        cursor.execute(
            """INSERT INTO study_sessions
               (user_id, subject_id, topic, session_date, start_time, duration_minutes, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, subject_ids["Computer Science"], "Binary trees and recursion", date.today(), "10:00:00", 90, "Review before the midterm"),
        )

    conn.commit()
    cursor.close()
    conn.close()

    session.clear()
    session["user_id"] = user_id
    session["full_name"] = full_name
    session["role"] = role
    flash("Demo account loaded. You are using the full planner system.", "success")
    return redirect(url_for("dashboard"))


# ------------------------------------------------------------
# Logout
# ------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ------------------------------------------------------------
# Dashboard
# ------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM subjects WHERE user_id = %s", (user_id,))
    total_subjects = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Pending'",
        (user_id,),
    )
    pending_tasks = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Completed'",
        (user_id,),
    )
    completed_tasks = cursor.fetchone()["total"]

    total_tasks = pending_tasks + completed_tasks
    completion_percentage = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0

    cursor.execute(
        """SELECT t.*, s.subject_name FROM tasks t
           LEFT JOIN subjects s ON t.subject_id = s.subject_id
           WHERE t.user_id = %s AND t.status = 'Pending'
           ORDER BY t.due_date ASC LIMIT 5""",
        (user_id,),
    )
    upcoming_deadlines = cursor.fetchall()

    cursor.execute(
        """SELECT e.*, s.subject_name FROM exams e
           LEFT JOIN subjects s ON e.subject_id = s.subject_id
           WHERE e.user_id = %s AND e.exam_date >= CURDATE()
           ORDER BY e.exam_date ASC LIMIT 5""",
        (user_id,),
    )
    upcoming_exams = cursor.fetchall()
    for exam in upcoming_exams:
        exam["days_remaining"] = (exam["exam_date"] - date.today()).days

    cursor.execute(
        """SELECT t.*, s.subject_name FROM tasks t
           LEFT JOIN subjects s ON t.subject_id = s.subject_id
           WHERE t.user_id = %s AND t.status = 'Pending'
           ORDER BY t.due_date ASC""",
        (user_id,),
    )
    reminder_tasks = cursor.fetchall()

    cursor.execute(
        """SELECT e.*, s.subject_name FROM exams e
           LEFT JOIN subjects s ON e.subject_id = s.subject_id
           WHERE e.user_id = %s AND e.exam_date >= CURDATE()
           ORDER BY e.exam_date ASC""",
        (user_id,),
    )
    reminder_exams = cursor.fetchall()
    upcoming_reminders = build_reminder_items(reminder_tasks, reminder_exams, date.today())[:5]

    cursor.execute(
        """SELECT ss.*, s.subject_name FROM study_sessions ss
           LEFT JOIN subjects s ON ss.subject_id = s.subject_id
           WHERE ss.user_id = %s AND ss.session_date = CURDATE()
           ORDER BY ss.start_time ASC""",
        (user_id,),
    )
    todays_schedule = cursor.fetchall()

    cursor.execute(
        """SELECT t.*, s.subject_name FROM tasks t
           LEFT JOIN subjects s ON t.subject_id = s.subject_id
           WHERE t.user_id = %s AND t.priority = 'High' AND t.status = 'Pending'
           ORDER BY t.due_date ASC LIMIT 5""",
        (user_id,),
    )
    high_priority_tasks = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        total_subjects=total_subjects,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        completion_percentage=completion_percentage,
        upcoming_deadlines=upcoming_deadlines,
        upcoming_exams=upcoming_exams,
        todays_schedule=todays_schedule,
        high_priority_tasks=high_priority_tasks,
        upcoming_reminders=upcoming_reminders,
        today=date.today(),
    )


# ==============================================================
# SUBJECTS
# ==============================================================
@app.route("/subjects")
@login_required
def subjects():
    user_id = session["user_id"]
    search_query = request.args.get("q", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if search_query:
        like_query = f"%{search_query}%"
        cursor.execute(
            """SELECT * FROM subjects WHERE user_id = %s
               AND (subject_name LIKE %s OR subject_code LIKE %s OR teacher_name LIKE %s)
               ORDER BY subject_name""",
            (user_id, like_query, like_query, like_query),
        )
    else:
        cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))

    subject_list = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("subjects.html", subjects=subject_list, search_query=search_query)


@app.route("/subjects/add", methods=["POST"])
@login_required
def add_subject():
    user_id = session["user_id"]
    subject_name = request.form.get("subject_name", "").strip()
    subject_code = request.form.get("subject_code", "").strip()
    teacher_name = request.form.get("teacher_name", "").strip()
    description = request.form.get("description", "").strip()

    if not subject_name:
        flash("Subject name is required.", "danger")
        return redirect(url_for("subjects"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO subjects (user_id, subject_name, subject_code, teacher_name, description)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, subject_name, subject_code, teacher_name, description),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Subject added successfully.", "success")
    return redirect(url_for("subjects"))


@app.route("/subjects/edit/<int:subject_id>", methods=["POST"])
@login_required
def edit_subject(subject_id):
    user_id = session["user_id"]
    subject_name = request.form.get("subject_name", "").strip()
    subject_code = request.form.get("subject_code", "").strip()
    teacher_name = request.form.get("teacher_name", "").strip()
    description = request.form.get("description", "").strip()

    if not subject_name:
        flash("Subject name is required.", "danger")
        return redirect(url_for("subjects"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE subjects SET subject_name=%s, subject_code=%s, teacher_name=%s, description=%s
           WHERE subject_id=%s AND user_id=%s""",
        (subject_name, subject_code, teacher_name, description, subject_id, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Subject updated successfully.", "success")
    return redirect(url_for("subjects"))


@app.route("/subjects/delete/<int:subject_id>", methods=["POST"])
@login_required
def delete_subject(subject_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subjects WHERE subject_id=%s AND user_id=%s", (subject_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Subject deleted.", "info")
    return redirect(url_for("subjects"))


# ==============================================================
# TASKS
# ==============================================================
@app.route("/tasks")
@login_required
def tasks():
    user_id = session["user_id"]

    subject_filter = request.args.get("subject_id", "")
    priority_filter = request.args.get("priority", "")
    status_filter = request.args.get("status", "")
    due_date_filter = request.args.get("due_date", "")
    search_query = request.args.get("q", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """SELECT t.*, s.subject_name FROM tasks t
               LEFT JOIN subjects s ON t.subject_id = s.subject_id
               WHERE t.user_id = %s"""
    params = [user_id]

    if subject_filter:
        query += " AND t.subject_id = %s"
        params.append(subject_filter)
    if priority_filter:
        query += " AND t.priority = %s"
        params.append(priority_filter)
    if status_filter:
        query += " AND t.status = %s"
        params.append(status_filter)
    if due_date_filter:
        query += " AND t.due_date = %s"
        params.append(due_date_filter)
    if search_query:
        query += " AND (t.title LIKE %s OR t.description LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY t.due_date ASC"
    cursor.execute(query, tuple(params))
    task_list = cursor.fetchall()

    today = date.today()
    for task in task_list:
        task["is_overdue"] = task["status"] == "Pending" and task["due_date"] < today

    cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))
    subject_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "tasks.html",
        tasks=task_list,
        subjects=subject_list,
        subject_filter=subject_filter,
        priority_filter=priority_filter,
        status_filter=status_filter,
        due_date_filter=due_date_filter,
        search_query=search_query,
    )


@app.route("/tasks/add", methods=["POST"])
@login_required
def add_task():
    user_id = session["user_id"]
    title = request.form.get("title", "").strip()
    subject_id = request.form.get("subject_id") or None
    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "")
    priority = request.form.get("priority", "Medium")
    reminder_days_before = int(request.form.get("reminder_days_before") or 1)
    recurrence_type = request.form.get("recurrence_type", "").strip().lower() or None
    recurrence_interval = max(1, int(request.form.get("recurrence_interval") or 1))

    if not title or not due_date:
        flash("Task title and due date are required.", "danger")
        return redirect(url_for("tasks"))

    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("SELECT subject_id FROM subjects WHERE subject_id = %s AND user_id = %s", (subject_id, user_id))
        if not cursor.fetchone():
            cursor.close(); conn.close()
            flash("Please choose one of your subjects.", "danger")
            return redirect(url_for("tasks"))

    cursor.execute(
        """INSERT INTO tasks (user_id, subject_id, title, description, due_date, priority, status,
           is_recurring, recurrence_type, recurrence_interval, reminder_days_before)
           VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s, %s, %s, %s)""",
        (user_id, subject_id, title, description, due_date, priority, bool(recurrence_type), recurrence_type, recurrence_interval, reminder_days_before),
    )
    conn.commit()
    cursor.close(); conn.close()

    flash("Task added successfully.", "success")
    return redirect(url_for("tasks"))


@app.route("/tasks/edit/<int:task_id>", methods=["POST"])
@login_required
def edit_task(task_id):
    user_id = session["user_id"]
    title = request.form.get("title", "").strip()
    subject_id = request.form.get("subject_id") or None
    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "")
    priority = request.form.get("priority", "Medium")
    status = request.form.get("status", "Pending")
    reminder_days_before = int(request.form.get("reminder_days_before") or 1)
    recurrence_type = request.form.get("recurrence_type", "").strip().lower() or None
    recurrence_interval = max(1, int(request.form.get("recurrence_interval") or 1))

    if not title or not due_date:
        flash("Task title and due date are required.", "danger")
        return redirect(url_for("tasks"))

    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("SELECT subject_id FROM subjects WHERE subject_id = %s AND user_id = %s", (subject_id, user_id))
        if not cursor.fetchone():
            cursor.close(); conn.close()
            flash("Please choose one of your subjects.", "danger")
            return redirect(url_for("tasks"))

    cursor.execute(
        """UPDATE tasks SET subject_id=%s, title=%s, description=%s, due_date=%s,
           priority=%s, status=%s, is_recurring=%s, recurrence_type=%s,
           recurrence_interval=%s, reminder_days_before=%s
           WHERE task_id=%s AND user_id=%s""",
        (subject_id, title, description, due_date, priority, status, bool(recurrence_type), recurrence_type, recurrence_interval, reminder_days_before, task_id, user_id),
    )
    conn.commit()
    cursor.close(); conn.close()

    flash("Task updated successfully.", "success")
    return redirect(url_for("tasks"))


@app.route("/tasks/complete/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM tasks WHERE task_id=%s AND user_id=%s",
        (task_id, user_id),
    )
    task = cursor.fetchone()

    if task:
        recurrence_type = task.get("recurrence_type")
        if task.get("is_recurring") and recurrence_type:
            next_due_date = get_next_due_date(task["due_date"], recurrence_type)
            cursor.execute(
                """INSERT INTO tasks (user_id, subject_id, title, description, due_date, priority, status,
                   is_recurring, recurrence_type, recurrence_interval, reminder_days_before)
                   VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s, %s, %s, %s)""",
                (
                    user_id,
                    task["subject_id"],
                    task["title"],
                    task["description"],
                    next_due_date,
                    task["priority"],
                    True,
                    recurrence_type,
                    task.get("recurrence_interval") or 1,
                    task.get("reminder_days_before") or 1,
                ),
            )
            flash("Task marked complete and a new recurring task was scheduled.", "success")
        else:
            flash("Task marked as completed.", "success")

        cursor.execute(
            "UPDATE tasks SET status='Completed' WHERE task_id=%s AND user_id=%s",
            (task_id, user_id),
        )

    conn.commit(); cursor.close(); conn.close()
    return redirect(url_for("tasks"))


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE task_id=%s AND user_id=%s", (task_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Task deleted.", "info")
    return redirect(url_for("tasks"))


# ==============================================================
# EXAMS
# ==============================================================
@app.route("/exams")
@login_required
def exams():
    user_id = session["user_id"]
    search_query = request.args.get("q", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """SELECT e.*, s.subject_name FROM exams e
               LEFT JOIN subjects s ON e.subject_id = s.subject_id
               WHERE e.user_id = %s"""
    params = [user_id]

    if search_query:
        query += " AND (e.exam_name LIKE %s OR s.subject_name LIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    query += " ORDER BY e.exam_date ASC"
    cursor.execute(query, tuple(params))
    exam_list = cursor.fetchall()

    today = date.today()
    for exam in exam_list:
        exam["days_remaining"] = (exam["exam_date"] - today).days

    cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))
    subject_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("exams.html", exams=exam_list, subjects=subject_list, search_query=search_query)


@app.route("/exams/<int:exam_id>")
@login_required
def exam_detail(exam_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT e.*, s.subject_name FROM exams e
           LEFT JOIN subjects s ON e.subject_id = s.subject_id
           WHERE e.exam_id = %s AND e.user_id = %s""",
        (exam_id, user_id),
    )
    exam = cursor.fetchone()
    cursor.close()
    conn.close()

    if not exam:
        flash("Exam not found.", "warning")
        return redirect(url_for("exams"))

    exam["days_remaining"] = (exam["exam_date"] - date.today()).days
    return render_template("exam_detail.html", exam=exam)


@app.route("/exams/add", methods=["POST"])
@login_required
def add_exam():
    user_id = session["user_id"]
    exam_name = request.form.get("exam_name", "").strip()
    subject_id = request.form.get("subject_id") or None
    exam_date = request.form.get("exam_date", "")
    exam_time = request.form.get("exam_time") or None
    venue = request.form.get("venue", "").strip()
    notes = request.form.get("notes", "").strip()
    reminder_days_before = int(request.form.get("reminder_days_before") or 3)

    if not exam_name or not exam_date:
        flash("Exam name and date are required.", "danger")
        return redirect(url_for("exams"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO exams (user_id, subject_id, exam_name, exam_date, exam_time, venue, notes, reminder_days_before)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (user_id, subject_id, exam_name, exam_date, exam_time, venue, notes, reminder_days_before),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Exam added successfully.", "success")
    return redirect(url_for("exams"))


@app.route("/exams/edit/<int:exam_id>", methods=["POST"])
@login_required
def edit_exam(exam_id):
    user_id = session["user_id"]
    exam_name = request.form.get("exam_name", "").strip()
    subject_id = request.form.get("subject_id") or None
    exam_date = request.form.get("exam_date", "")
    exam_time = request.form.get("exam_time") or None
    venue = request.form.get("venue", "").strip()
    notes = request.form.get("notes", "").strip()
    reminder_days_before = int(request.form.get("reminder_days_before") or 3)

    if not exam_name or not exam_date:
        flash("Exam name and date are required.", "danger")
        return redirect(url_for("exams"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE exams SET subject_id=%s, exam_name=%s, exam_date=%s, exam_time=%s,
           venue=%s, notes=%s, reminder_days_before=%s WHERE exam_id=%s AND user_id=%s""",
        (subject_id, exam_name, exam_date, exam_time, venue, notes, reminder_days_before, exam_id, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Exam updated successfully.", "success")
    return redirect(url_for("exams"))


@app.route("/exams/delete/<int:exam_id>", methods=["POST"])
@login_required
def delete_exam(exam_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM exams WHERE exam_id=%s AND user_id=%s", (exam_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Exam deleted.", "info")
    return redirect(url_for("exams"))


# ==============================================================
# STUDY SCHEDULE
# ==============================================================
@app.route("/schedule")
@login_required
def schedule():
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT ss.*, s.subject_name FROM study_sessions ss
           LEFT JOIN subjects s ON ss.subject_id = s.subject_id
           WHERE ss.user_id = %s
           ORDER BY ss.session_date ASC, ss.start_time ASC""",
        (user_id,),
    )
    sessions = cursor.fetchall()

    cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))
    subject_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("schedule.html", sessions=sessions, subjects=subject_list)


@app.route("/schedule/add", methods=["POST"])
@login_required
def add_session():
    user_id = session["user_id"]
    subject_id = request.form.get("subject_id") or None
    topic = request.form.get("topic", "").strip()
    session_date = request.form.get("session_date", "")
    start_time = request.form.get("start_time", "")
    duration_minutes = request.form.get("duration_minutes", "")
    notes = request.form.get("notes", "").strip()

    if not session_date or not start_time or not duration_minutes:
        flash("Date, start time, and duration are required.", "danger")
        return redirect(url_for("schedule"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO study_sessions (user_id, subject_id, topic, session_date, start_time, duration_minutes, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, subject_id, topic, session_date, start_time, duration_minutes, notes),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Study session added.", "success")
    return redirect(url_for("schedule"))


@app.route("/schedule/edit/<int:session_id>", methods=["POST"])
@login_required
def edit_session(session_id):
    user_id = session["user_id"]
    subject_id = request.form.get("subject_id") or None
    topic = request.form.get("topic", "").strip()
    session_date = request.form.get("session_date", "")
    start_time = request.form.get("start_time", "")
    duration_minutes = request.form.get("duration_minutes", "")
    notes = request.form.get("notes", "").strip()

    if not session_date or not start_time or not duration_minutes:
        flash("Date, start time, and duration are required.", "danger")
        return redirect(url_for("schedule"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE study_sessions SET subject_id=%s, topic=%s, session_date=%s, start_time=%s,
           duration_minutes=%s, notes=%s WHERE session_id=%s AND user_id=%s""",
        (subject_id, topic, session_date, start_time, duration_minutes, notes, session_id, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Study session updated.", "success")
    return redirect(url_for("schedule"))


@app.route("/schedule/delete/<int:session_id>", methods=["POST"])
@login_required
def delete_session(session_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM study_sessions WHERE session_id=%s AND user_id=%s", (session_id, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Study session deleted.", "info")
    return redirect(url_for("schedule"))


# ==============================================================
# CALENDAR
# ==============================================================
@app.route("/calendar")
@login_required
def calendar_view():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    events = []

    cursor.execute("SELECT title, due_date FROM tasks WHERE user_id = %s", (user_id,))
    for row in cursor.fetchall():
        events.append({
            "title": f"Task: {row['title']}",
            "start": row["due_date"].isoformat(),
            "type": "task",
        })

    cursor.execute("SELECT exam_name, exam_date FROM exams WHERE user_id = %s", (user_id,))
    for row in cursor.fetchall():
        events.append({
            "title": f"Exam: {row['exam_name']}",
            "start": row["exam_date"].isoformat(),
            "type": "exam",
        })

    cursor.execute("SELECT topic, session_date FROM study_sessions WHERE user_id = %s", (user_id,))
    for row in cursor.fetchall():
        events.append({
            "title": f"Study: {row['topic'] or 'Session'}",
            "start": row["session_date"].isoformat(),
            "type": "study",
        })

    cursor.close()
    conn.close()

    return render_template("calendar.html", events=events)


@app.route("/pomodoro")
@login_required
def pomodoro():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Pending'", (user_id,))
    pending_tasks = cursor.fetchone()["total"]
    cursor.execute("SELECT SUM(duration_minutes) AS total_minutes FROM study_sessions WHERE user_id = %s", (user_id,))
    total_minutes = cursor.fetchone()["total_minutes"] or 0
    cursor.close(); conn.close()
    return render_template("pomodoro.html", pending_tasks=pending_tasks, total_minutes=total_minutes)


@app.route("/grades")
@login_required
def grades():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT g.*, s.subject_name FROM grades g
           LEFT JOIN subjects s ON g.subject_id = s.subject_id
           WHERE g.user_id = %s ORDER BY g.grade_date DESC""",
        (user_id,),
    )
    grade_list = cursor.fetchall()
    for grade in grade_list:
        grade["percentage"] = round((grade["score"] / grade["max_score"]) * 100, 1) if grade["max_score"] else 0
        grade["letter_grade"] = calculate_grade_letter(grade["percentage"])

    cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))
    subject_list = cursor.fetchall()
    cursor.execute("SELECT AVG((score / max_score) * 100) AS average FROM grades WHERE user_id = %s", (user_id,))
    average_score = cursor.fetchone()["average"] or 0
    cursor.close(); conn.close()
    return render_template(
        "grades.html",
        grades=grade_list,
        subjects=subject_list,
        average_score=round(float(average_score), 1),
        overall_letter=calculate_grade_letter(average_score),
    )


@app.route("/grades/add", methods=["POST"])
@login_required
def add_grade():
    user_id = session["user_id"]
    subject_id = request.form.get("subject_id") or None
    assessment_name = request.form.get("assessment_name", "").strip()
    score = request.form.get("score", "")
    max_score = request.form.get("max_score", "")
    grade_date = request.form.get("grade_date", "")
    remarks = request.form.get("remarks", "").strip()

    if not assessment_name or not score or not max_score or not grade_date:
        flash("Assessment name, score, maximum score, and date are required.", "danger")
        return redirect(url_for("grades"))

    try:
        score_value = float(score)
        max_score_value = float(max_score)
    except ValueError:
        flash("Scores must be numeric values.", "danger")
        return redirect(url_for("grades"))

    if max_score_value <= 0:
        flash("Maximum score must be greater than zero.", "danger")
        return redirect(url_for("grades"))

    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO grades (user_id, subject_id, assessment_name, score, max_score, grade_date, remarks)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, subject_id, assessment_name, score_value, max_score_value, grade_date, remarks),
    )
    conn.commit(); cursor.close(); conn.close()
    flash("Grade saved successfully.", "success")
    return redirect(url_for("grades"))


@app.route("/grades/edit/<int:grade_id>", methods=["POST"])
@login_required
def edit_grade(grade_id):
    user_id = session["user_id"]
    subject_id = request.form.get("subject_id") or None
    assessment_name = request.form.get("assessment_name", "").strip()
    score = request.form.get("score", "")
    max_score = request.form.get("max_score", "")
    grade_date = request.form.get("grade_date", "")
    remarks = request.form.get("remarks", "").strip()

    if not assessment_name or not score or not max_score or not grade_date:
        flash("Assessment name, score, maximum score, and date are required.", "danger")
        return redirect(url_for("grades"))

    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute(
        """UPDATE grades SET subject_id=%s, assessment_name=%s, score=%s, max_score=%s, grade_date=%s, remarks=%s
           WHERE grade_id=%s AND user_id=%s""",
        (subject_id, assessment_name, float(score), float(max_score), grade_date, remarks, grade_id, user_id),
    )
    conn.commit(); cursor.close(); conn.close()
    flash("Grade updated successfully.", "success")
    return redirect(url_for("grades"))


@app.route("/grades/delete/<int:grade_id>", methods=["POST"])
@login_required
def delete_grade(grade_id):
    user_id = session["user_id"]
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM grades WHERE grade_id=%s AND user_id=%s", (grade_id, user_id))
    conn.commit(); cursor.close(); conn.close()
    flash("Grade deleted.", "info")
    return redirect(url_for("grades"))


@app.route("/groups")
@login_required
def groups():
    user_id = session["user_id"]
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT sg.*, gm.role, u.full_name as created_by_name
           FROM study_groups sg
           JOIN group_members gm ON gm.group_id = sg.group_id
           LEFT JOIN users u ON u.user_id = sg.user_id
           WHERE gm.user_id = %s ORDER BY sg.created_at DESC""",
        (user_id,),
    )
    my_groups = cursor.fetchall()

    for group in my_groups:
        cursor.execute(
            """SELECT gm.role, u.full_name, u.email
               FROM group_members gm
               JOIN users u ON u.user_id = gm.user_id
               WHERE gm.group_id = %s ORDER BY u.full_name""",
            (group["group_id"],),
        )
        group["members"] = cursor.fetchall()

    cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))
    subject_list = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("groups.html", groups=my_groups, subjects=subject_list)


@app.route("/groups/add", methods=["POST"])
@login_required
def add_group():
    user_id = session["user_id"]
    group_name = request.form.get("group_name", "").strip()
    description = request.form.get("description", "").strip()

    if not group_name:
        flash("Group name is required.", "danger")
        return redirect(url_for("groups"))

    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO study_groups (user_id, group_name, description) VALUES (%s, %s, %s)",
        (user_id, group_name, description),
    )
    group_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, 'admin')",
        (group_id, user_id),
    )
    conn.commit(); cursor.close(); conn.close()
    flash("Study group created.", "success")
    return redirect(url_for("groups"))


@app.route("/groups/<int:group_id>/add-member", methods=["POST"])
@login_required
def add_group_member(group_id):
    user_id = session["user_id"]
    member_email = request.form.get("member_email", "").strip().lower()

    if not member_email:
        flash("Please enter a member email.", "danger")
        return redirect(url_for("groups"))

    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, full_name FROM users WHERE email = %s", (member_email,))
    member = cursor.fetchone()
    if not member:
        cursor.close(); conn.close()
        flash("No matching user found for that email.", "warning")
        return redirect(url_for("groups"))

    if member["user_id"] == user_id:
        cursor.close(); conn.close()
        flash("You are already a member of the group.", "info")
        return redirect(url_for("groups"))

    cursor.execute(
        "SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, member["user_id"]),
    )
    existing = cursor.fetchone()
    if existing:
        cursor.close(); conn.close()
        flash("This user is already in the study group.", "info")
        return redirect(url_for("groups"))

    cursor.execute(
        "INSERT INTO group_members (group_id, user_id, role) VALUES (%s, %s, 'member')",
        (group_id, member["user_id"]),
    )
    conn.commit(); cursor.close(); conn.close()
    flash("Member added to the study group.", "success")
    return redirect(url_for("groups"))


@app.route("/groups/<int:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
    user_id = session["user_id"]
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id))
    conn.commit(); cursor.close(); conn.close()
    flash("You left the study group.", "info")
    return redirect(url_for("groups"))


@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s", (user_id,))
    total_tasks = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Pending'", (user_id,))
    pending_tasks = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Completed'", (user_id,))
    completed_tasks = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM exams WHERE user_id = %s", (user_id,))
    total_exams = cursor.fetchone()["total"]
    cursor.execute("SELECT AVG((score / max_score) * 100) AS average FROM grades WHERE user_id = %s", (user_id,))
    average_grade = cursor.fetchone()["average"] or 0
    cursor.execute("SELECT COUNT(*) AS total FROM study_sessions WHERE user_id = %s", (user_id,))
    total_sessions = cursor.fetchone()["total"]
    cursor.execute("SELECT * FROM tasks WHERE user_id = %s ORDER BY due_date ASC LIMIT 10", (user_id,))
    task_rows = cursor.fetchall()
    cursor.close(); conn.close()

    return render_template(
        "reports.html",
        total_tasks=total_tasks,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks,
        total_exams=total_exams,
        average_grade=round(float(average_grade), 1),
        total_sessions=total_sessions,
        tasks=task_rows,
    )


@app.route("/reports/export.csv")
@login_required
def export_reports_csv():
    user_id = session["user_id"]
    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT task_id, title, due_date, status, priority FROM tasks WHERE user_id = %s ORDER BY due_date ASC", (user_id,))
    tasks = cursor.fetchall()
    cursor.execute("SELECT grade_id, assessment_name, score, max_score, grade_date FROM grades WHERE user_id = %s ORDER BY grade_date DESC", (user_id,))
    grades = cursor.fetchall()
    cursor.close(); conn.close()

    csv_lines = ["type,identifier,name,date,status,score,max_score"]

    for task in tasks:
        csv_lines.append(
            f"task,{task['task_id']},{task['title']},{task['due_date']},{task['status']},,,"
        )
    for grade in grades:
        csv_lines.append(
            f"grade,{grade['grade_id']},{grade['assessment_name']},{grade['grade_date']},,,{grade['score']},{grade['max_score']}"
        )

    csv_content = "\n".join(csv_lines)
    return Response(csv_content, mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=student-smart-planner-report.csv"})


@app.route("/teacher-board")
@login_required
def teacher_board():
    if session.get("role") not in {"teacher", "admin"}:
        flash("This area is only available to teachers and administrators.", "warning")
        return redirect(url_for("dashboard"))

    conn = get_db_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT u.user_id, u.full_name, u.email, u.role,
                  (SELECT COUNT(*) FROM tasks t WHERE t.user_id = u.user_id) AS task_total,
                  (SELECT COUNT(*) FROM grades g WHERE g.user_id = u.user_id) AS grade_total,
                  (SELECT COUNT(*) FROM study_sessions ss WHERE ss.user_id = u.user_id) AS study_total
           FROM users u
           WHERE u.role = 'student'
           ORDER BY u.full_name ASC"""
    )
    student_rows = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("teacher_board.html", students=student_rows)


# ==============================================================
# NOTES & REMINDERS
# ==============================================================
@app.route("/reminders")
@login_required
def reminders():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """SELECT t.*, s.subject_name FROM tasks t
           LEFT JOIN subjects s ON t.subject_id = s.subject_id
           WHERE t.user_id = %s AND t.status = 'Pending'""",
        (user_id,),
    )
    tasks = cursor.fetchall()

    cursor.execute(
        """SELECT e.*, s.subject_name FROM exams e
           LEFT JOIN subjects s ON e.subject_id = s.subject_id
           WHERE e.user_id = %s""",
        (user_id,),
    )
    exams = cursor.fetchall()
    cursor.close(); conn.close()

    reminder_items = build_reminder_items(tasks, exams, date.today())
    return render_template("reminders.html", reminders=reminder_items)


@app.route("/reminders/send-email", methods=["POST"])
@login_required
def send_reminder_email_route():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT full_name, email FROM users WHERE user_id = %s",
        (user_id,),
    )
    user = cursor.fetchone()

    cursor.execute(
        """SELECT t.*, s.subject_name FROM tasks t
           LEFT JOIN subjects s ON t.subject_id = s.subject_id
           WHERE t.user_id = %s AND t.status = 'Pending'""",
        (user_id,),
    )
    tasks = cursor.fetchall()

    cursor.execute(
        """SELECT e.*, s.subject_name FROM exams e
           LEFT JOIN subjects s ON e.subject_id = s.subject_id
           WHERE e.user_id = %s""",
        (user_id,),
    )
    exams = cursor.fetchall()
    cursor.close(); conn.close()

    reminder_items = build_reminder_items(tasks, exams, date.today())

    if not user or not user.get("email"):
        flash("Add an email address to your profile before sending reminder emails.", "warning")
        return redirect(url_for("reminders"))

    if not app.config.get("SMTP_HOST"):
        flash("SMTP is not configured. Add SMTP_HOST and related values to enable email reminders.", "warning")
        return redirect(url_for("reminders"))

    if send_reminder_email(user["email"], user["full_name"], reminder_items):
        flash("Reminder email sent successfully.", "success")
    else:
        flash("Unable to send the reminder email. Check your SMTP configuration.", "danger")

    return redirect(url_for("reminders"))


@app.route("/notes")
@login_required
def notes():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """SELECT n.*, s.subject_name FROM notes n
           LEFT JOIN subjects s ON n.subject_id = s.subject_id
           WHERE n.user_id = %s
           ORDER BY n.updated_at DESC""",
        (user_id,),
    )
    note_list = cursor.fetchall()
    cursor.execute("SELECT * FROM subjects WHERE user_id = %s ORDER BY subject_name", (user_id,))
    subject_list = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("notes.html", notes=note_list, subjects=subject_list)


@app.route("/notes/add", methods=["POST"])
@login_required
def add_note():
    user_id = session["user_id"]
    subject_id = request.form.get("subject_id") or None
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    resource_url = request.form.get("resource_url", "").strip()
    tags = request.form.get("tags", "").strip()

    if not title:
        flash("Note title is required.", "danger")
        return redirect(url_for("notes"))

    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO notes (user_id, subject_id, title, content, resource_url, tags)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, subject_id, title, content, resource_url or None, tags),
    )
    conn.commit(); cursor.close(); conn.close()
    flash("Note saved successfully.", "success")
    return redirect(url_for("notes"))


@app.route("/notes/edit/<int:note_id>", methods=["POST"])
@login_required
def edit_note(note_id):
    user_id = session["user_id"]
    subject_id = request.form.get("subject_id") or None
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    resource_url = request.form.get("resource_url", "").strip()
    tags = request.form.get("tags", "").strip()

    if not title:
        flash("Note title is required.", "danger")
        return redirect(url_for("notes"))

    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute(
        """UPDATE notes SET subject_id=%s, title=%s, content=%s, resource_url=%s, tags=%s
           WHERE note_id=%s AND user_id=%s""",
        (subject_id, title, content, resource_url or None, tags, note_id, user_id),
    )
    conn.commit(); cursor.close(); conn.close()
    flash("Note updated successfully.", "success")
    return redirect(url_for("notes"))


@app.route("/notes/delete/<int:note_id>", methods=["POST"])
@login_required
def delete_note(note_id):
    user_id = session["user_id"]
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE note_id=%s AND user_id=%s", (note_id, user_id))
    conn.commit(); cursor.close(); conn.close()
    flash("Note deleted.", "info")
    return redirect(url_for("notes"))


@app.route("/health")
def health_check():
    return {"status": "ok", "service": "student-smart-planner"}, 200


# ==============================================================
# PROGRESS
# ==============================================================
@app.route("/progress")
@login_required
def progress():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Completed'",
        (user_id,),
    )
    completed = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Pending' AND due_date >= CURDATE()",
        (user_id,),
    )
    pending = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM tasks WHERE user_id = %s AND status = 'Pending' AND due_date < CURDATE()",
        (user_id,),
    )
    overdue = cursor.fetchone()["total"]

    total_tasks = completed + pending + overdue
    completion_percentage = round((completed / total_tasks) * 100, 1) if total_tasks else 0

    cursor.execute(
        """SELECT s.subject_name,
                  SUM(CASE WHEN t.status='Completed' THEN 1 ELSE 0 END) AS completed_count,
                  SUM(CASE WHEN t.status='Pending' THEN 1 ELSE 0 END) AS pending_count
           FROM subjects s
           LEFT JOIN tasks t ON s.subject_id = t.subject_id
           WHERE s.user_id = %s
           GROUP BY s.subject_id, s.subject_name""",
        (user_id,),
    )
    subject_progress = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "progress.html",
        completed=completed,
        pending=pending,
        overdue=overdue,
        completion_percentage=completion_percentage,
        subject_progress=subject_progress,
    )


# ==============================================================
# PROFILE
# ==============================================================
@app.route("/profile")
@login_required
def profile():
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT full_name, email, created_at FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("profile.html", user=user)


if __name__ == "__main__":
    app.run(debug=True)
