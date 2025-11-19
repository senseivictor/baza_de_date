import sqlite3
import json
import time
import uuid
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("lab1/lab1.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users_login_info (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    order_public_id TEXT NOT NULL,
    user_id INTEGER,
    products TEXT NOT NULL,
    order_status TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL
);
""")

products = [
    ("Caricature", 29.99),
    ("Voiceover", 49.99),
    ("Song", 79.99)
]

cursor.executemany("""
INSERT OR IGNORE INTO products (name, price)
VALUES (?, ?)
""", products)


now = int(time.time())
users = [
    ("alice@example.com", "hashed_pw1", now),
    ("bob@example.com", "hashed_pw2", now),
    ("charlie@example.com", "hashed_pw3", now)
]

cursor.executemany("""
INSERT OR IGNORE INTO users_login_info (email, password, created_at)
VALUES (?, ?, ?)
""", users)

orders = []

for user_id in range(1, 4):
    base_dates = [int(time.time() - random.randint(0, 30) * 24 * 60 * 60) for _ in range(5)]
    for _ in range(10): # populez tabelul de comenzi cu cate 10 comenzi random pentru fiecare client
        order_public_id = str(uuid.uuid4())
        created_at = random.choice(base_dates)
        product_list = json.dumps([random.randint(1, 3) for _ in range(3)])
        orders.append((order_public_id, user_id, product_list, "finalizat", created_at))

cursor.executemany("""
INSERT INTO orders (order_public_id, user_id, products, order_status, created_at)
VALUES (?, ?, ?, ?, ?)
""", orders)

conn.commit()
conn.close()

print("Tabelele au fost create")
