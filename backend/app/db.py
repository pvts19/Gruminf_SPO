import os
import sqlite3

from app.security import hash_password

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "salon.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('client', 'admin'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    species TEXT NOT NULL,
    breed TEXT NOT NULL DEFAULT '',
    weight REAL NOT NULL CHECK (weight > 0)
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL CHECK (price > 0),
    duration INTEGER NOT NULL CHECK (duration > 0),
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id),
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    price INTEGER NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'done', 'cancelled'))
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    # стартовые данные: админ и несколько услуг
    if conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (email, password_hash, name, phone, role) VALUES (?, ?, ?, ?, 'admin')",
            ("admin@salon.ru", hash_password("admin123"), "Администратор", "+79990000000"),
        )
    if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO services (title, description, price, duration) VALUES (?, ?, ?, ?)",
            [
                ("Гигиеническая стрижка", "Стрижка когтей, чистка ушей, подрезка шерсти", 1200, 60),
                ("Комплексный груминг", "Мытьё, сушка, стрижка, когти, уши", 3000, 120),
                ("Мытьё и сушка", "Мытьё шампунем и сушка феном", 1500, 60),
                ("Стрижка когтей", "Только когти", 400, 30),
            ],
        )
    conn.commit()
    conn.close()
