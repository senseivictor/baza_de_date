import sqlite3
from datetime import datetime
import uuid

# Connect to SQLite database
conn = sqlite3.connect("api/database.db")
cursor = conn.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS users_login_info (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users_additional_info (
    user_id INTEGER PRIMARY KEY NOT NULL,
    username TEXT NOT NULL,
    name TEXT NOT NULL,
    surname TEXT NOT NULL,
    picture TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    address TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS verification_codes (
    email TEXT PRIMARY KEY NOT NULL,
    code INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    order_public_id TEXT NOT NULL,
    user_id INTEGER,
    order_status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    is_guest BOOLEAN NOT NULL DEFAULT 1
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_public_id TEXT NOT NULL,
    items TEXT NOT NULL,
    total_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    processor TEXT,
    processor_txn_id TEXT,
    status TEXT,
    created_at INTEGER NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    order_public_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    result_id TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    task_status TEXT NOT NULL DEFAULT 'pending'
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    brand TEXT NOT NULL,
    image_url TEXT NOT NULL
);
""")

now = int(datetime.now().timestamp())
order_uuid = str(uuid.uuid4())

cursor.execute("""
INSERT INTO users_login_info (email, password, platform, created_at)
VALUES ('alice@example.com', 'password123', 'email', ?)
""", (now,))

cursor.execute("""
INSERT INTO users_additional_info (user_id, username, name, surname, picture, phone_number, address, updated_at)
VALUES (1, 'alice_w', 'Alice', 'Wonder', 'https://example.com/pic1.jpg', '1234567890', '123 Wonderland Ave', ?)
""", (now,))

cursor.execute("""
INSERT INTO verification_codes (email, code, created_at)
VALUES ('alice@example.com', 123456, ?)
""", (now,))

cursor.execute("""
INSERT INTO orders (order_public_id, user_id, order_status, created_at, updated_at, is_guest)
VALUES (?, 1, 'pending', ?, ?, 0)
""", (order_uuid, now, now))

cursor.execute("""
INSERT INTO receipts (order_public_id, items, total_amount, currency, processor, processor_txn_id, status, created_at)
VALUES (?, '{"items": ["caricature"]}', 49.99, 'USD', 'Stripe', 'txn_12345', 'paid', ?)
""", (order_uuid, now))

cursor.execute("""
INSERT INTO tasks (order_id, order_public_id, task_type, result_id, created_at, task_status)
VALUES (1, ?, 'caricature', '', ?, 'pending')
""", (order_uuid, now))

products = [
    ("caricature", "Custom caricature drawing", "BrandA", "https://example.com/caricature.jpg"),
    ("song", "Personalized song creation", "BrandB", "https://example.com/song.jpg"),
    ("voiceover", "Professional voiceover recording", "BrandC", "https://example.com/voiceover.jpg"),
]

cursor.executemany("""
INSERT INTO products (name, description, brand, image_url)
VALUES (?, ?, ?, ?)
""", products)

conn.commit()
conn.close()

print("Tables created and database populated successfully!")
