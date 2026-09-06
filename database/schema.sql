-- ============================================================
-- Student Smart Planner - Database Schema
-- ============================================================
-- Run this file once to create the database and all tables.
-- Usage (from MySQL shell):
--     SOURCE schema.sql;
-- or from terminal:
--     mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS student_smart_planner;
USE student_smart_planner;

-- ------------------------------------------------------------
-- Table: users
-- Stores registered student accounts.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Table: subjects
-- Each subject belongs to exactly one user.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_name VARCHAR(100) NOT NULL,
    subject_code VARCHAR(30),
    teacher_name VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- Table: tasks
-- Assignments / projects / to-dos linked to a subject.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tasks (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_id INT,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    due_date DATE NOT NULL,
    priority ENUM('High', 'Medium', 'Low') NOT NULL DEFAULT 'Medium',
    status ENUM('Pending', 'Completed') NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- Table: exams
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exams (
    exam_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_id INT,
    exam_name VARCHAR(150) NOT NULL,
    exam_date DATE NOT NULL,
    exam_time TIME,
    venue VARCHAR(150),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- Table: study_sessions
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS study_sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    subject_id INT,
    topic VARCHAR(150),
    session_date DATE NOT NULL,
    start_time TIME NOT NULL,
    duration_minutes INT NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- Helpful indexes for common lookups/filters
-- ------------------------------------------------------------
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_exams_user ON exams(user_id);
CREATE INDEX idx_exams_date ON exams(exam_date);
CREATE INDEX idx_sessions_user ON study_sessions(user_id);
CREATE INDEX idx_sessions_date ON study_sessions(session_date);
CREATE INDEX idx_subjects_user ON subjects(user_id);
