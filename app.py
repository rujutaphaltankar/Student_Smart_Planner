"""
Student Smart Planner
======================
A Flask + MySQL web application that helps students manage subjects,
tasks/assignments, exams, and study schedules from one dashboard.

Run with:  python app.py
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config

app = Flask(__name__)
app.config.from_object(Config)


# ------------------------------------------------------------
# Database helper
# ------------------------------------------------------------
def get_db_connection():
    """Open a new MySQL connection using settings from config.py."""
    connection_options = {
        "host": app.config["MYSQL_HOST"],
        "user": app.config["MYSQL_USER"],
        "password": app.config["MYSQL_PASSWORD"],
        "port": app.config["MYSQL_PORT"],
    }

    try:
        return mysql.connector.connect(
            **connection_options,
            database=app.config["MYSQL_DB"],
        )
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

        return mysql.connector.connect(
            **connection_options,
            database=app.config["MYSQL_DB"],
        )


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
            "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)",
            (full_name, email, password_hash),
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

    cursor.execute("SELECT user_id, full_name FROM users WHERE email = %s", (demo_email,))
    user = cursor.fetchone()

    if user:
        user_id = user["user_id"]
        full_name = user["full_name"]
    else:
        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (%s, %s, %s)",
            ("Demo Student", demo_email, generate_password_hash("demo123")),
        )
        user_id = cursor.lastrowid
        full_name = "Demo Student"

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

    if not title or not due_date:
        flash("Task title and due date are required.", "danger")
        return redirect(url_for("tasks"))

    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("SELECT subject_id FROM subjects WHERE subject_id = %s AND user_id = %s", (subject_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            flash("Please choose one of your subjects.", "danger")
            return redirect(url_for("tasks"))

    cursor.execute(
        """INSERT INTO tasks (user_id, subject_id, title, description, due_date, priority, status)
           VALUES (%s, %s, %s, %s, %s, %s, 'Pending')""",
        (user_id, subject_id, title, description, due_date, priority),
    )
    conn.commit()
    cursor.close()
    conn.close()

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

    if not title or not due_date:
        flash("Task title and due date are required.", "danger")
        return redirect(url_for("tasks"))

    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("SELECT subject_id FROM subjects WHERE subject_id = %s AND user_id = %s", (subject_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            flash("Please choose one of your subjects.", "danger")
            return redirect(url_for("tasks"))

    cursor.execute(
        """UPDATE tasks SET subject_id=%s, title=%s, description=%s, due_date=%s,
           priority=%s, status=%s WHERE task_id=%s AND user_id=%s""",
        (subject_id, title, description, due_date, priority, status, task_id, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Task updated successfully.", "success")
    return redirect(url_for("tasks"))


@app.route("/tasks/complete/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET status='Completed' WHERE task_id=%s AND user_id=%s",
        (task_id, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    flash("Task marked as completed.", "success")
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

    if not exam_name or not exam_date:
        flash("Exam name and date are required.", "danger")
        return redirect(url_for("exams"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO exams (user_id, subject_id, exam_name, exam_date, exam_time, venue, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, subject_id, exam_name, exam_date, exam_time, venue, notes),
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

    if not exam_name or not exam_date:
        flash("Exam name and date are required.", "danger")
        return redirect(url_for("exams"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE exams SET subject_id=%s, exam_name=%s, exam_date=%s, exam_time=%s,
           venue=%s, notes=%s WHERE exam_id=%s AND user_id=%s""",
        (subject_id, exam_name, exam_date, exam_time, venue, notes, exam_id, user_id),
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
