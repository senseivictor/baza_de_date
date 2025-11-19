import sqlite3

conn = sqlite3.connect("lab2/lab2.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users_login_info (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
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


conn.commit()
conn.close()

print("Tabelele au fost create")
