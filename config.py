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
