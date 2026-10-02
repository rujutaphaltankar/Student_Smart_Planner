"""
Configuration settings for Student Smart Planner.
Edit the values below (or set matching environment variables)
to match your local MySQL setup.
"""

import os


class Config:
    # Secret key used to sign session cookies. Change this in production.
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-for-viva-demo")

    # MySQL connection settings
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "root123")
    MYSQL_DB = os.environ.get("MYSQL_DB", "student_smart_planner")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

    # Optional SMTP settings for email reminder summaries.
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_SENDER = os.environ.get("SMTP_SENDER", "noreply@studentplanner.local")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
