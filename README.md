# Student Smart Planner

A full-stack web application that helps students manage their academic
life — subjects, tasks/assignments, exams, and study schedules — from a
single, centralized dashboard.

Built as a Web Technology academic project using **Flask** and **MySQL**,
with a clean, beginner-friendly codebase suitable for a college viva.

---

## Features

- **Authentication** — registration, login, logout, hashed passwords, session-based access control. Each user sees only their own data.
- **Dashboard** — welcome message, subject/task counts, completion percentage, upcoming deadlines, upcoming exams, today's study schedule, high-priority tasks, and a progress chart.
- **Subjects** — add, edit, delete, and view subjects (name, code, teacher, description).
- **Tasks & Assignments** — full CRUD, priority levels (High/Medium/Low), status (Pending/Completed), filtering by subject/priority/status/due date, overdue highlighting.
- **Exam Tracker** — add exams with date, time, venue, and notes; shows days remaining and highlights exams coming up soon.
- **Study Schedule** — plan study sessions by subject, topic, date, time, and duration; edit/delete sessions.
- **Calendar** — a month-view calendar combining tasks, exams, and study sessions with color-coded indicators.
- **Progress Tracking** — doughnut chart (completed vs pending vs overdue) and bar chart (subject-wise completion) using Chart.js.
- **Search & Filters** — search subjects, tasks, and exams; filter tasks by subject, priority, status, and due date.
- **Light / Dark Mode** — toggle saved in the browser via `localStorage`.
- **Responsive UI** — sidebar navigation, cards, tables, modals, and mobile-friendly layout.

---

## Technology Stack

**Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js
**Backend:** Python, Flask
**Database:** MySQL
**Auth:** Flask sessions + Werkzeug password hashing

---

## System Requirements

- Python 3.9+
- MySQL Server 8.0+ (or MariaDB equivalent)
- pip (Python package manager)

---

## Project Structure

```
student-smart-planner/
├── app.py                  # Main Flask application (routes + logic)
├── config.py                # Configuration (DB credentials, secret key)
├── requirements.txt          # Python dependencies
├── database/
│   └── schema.sql             # MySQL table definitions
├── templates/                 # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── subjects.html
│   ├── tasks.html
│   ├── exams.html
│   ├── schedule.html
│   ├── calendar.html
│   ├── progress.html
│   └── profile.html
├── static/
│   ├── css/style.css
│   ├── js/script.js           # sidebar + theme toggle
│   ├── js/calendar.js         # calendar rendering
│   └── images/
└── README.md
```

---

## Installation Steps

1. **Clone or download** this project folder.

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate      # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Database Setup

1. Make sure MySQL Server is installed and running.

2. Log in to MySQL:
   ```bash
   mysql -u root -p
   ```

3. The application automatically creates the database and tables on its first connection. You can also run the schema file manually:
   ```bash
   mysql -u root -p < database/schema.sql
   ```
   (Or from inside the MySQL shell: `SOURCE database/schema.sql;`)

4. Open `config.py` and update the values to match your MySQL setup:
   ```python
   MYSQL_HOST = "localhost"
   MYSQL_USER = "root"
   MYSQL_PASSWORD = "your_mysql_password"
   MYSQL_DB = "student_smart_planner"
   MYSQL_PORT = 3306
   ```
   (Alternatively, set these as environment variables of the same name.)

---

## How to Run the Application

```bash
python app.py
```

The app will start on **http://127.0.0.1:5000/**. Open this URL in your
browser, register a new account, and log in to start using the planner.

---

## Screenshots

_Add screenshots of the Login page, Dashboard, Tasks page, Exam Tracker,
Calendar, and Progress page here once the app is running._

| Page | Screenshot |
|------|-----------|
| Login | _(add image)_ |
| Dashboard | _(add image)_ |
| Tasks | _(add image)_ |
| Exams | _(add image)_ |
| Calendar | _(add image)_ |
| Progress | _(add image)_ |

---

## Future Enhancements

- Email/SMS reminders for upcoming deadlines and exams
- File attachments for assignments (upload PDFs/notes)
- Export study schedule to Google Calendar / ICS file
- Pomodoro-style study timer integrated with the schedule
- Group/collaborative subject sharing between classmates
- Mobile app version (Flutter/React Native) using the same backend
- Analytics on best study times based on past sessions

---

## Notes for Viva / Demonstration

- Passwords are hashed using Werkzeug's `generate_password_hash` /
  `check_password_hash` — plain text passwords are never stored.
- All database queries are scoped by `user_id` from the session, so one
  user cannot view or modify another user's data.
- SQL queries use parameterized statements (`%s` placeholders) throughout
  to prevent SQL injection.
- The codebase intentionally avoids AI/ML or other unrelated technologies,
  keeping the focus on core web development concepts: routing, templating,
  CRUD operations, authentication, and relational database design.
