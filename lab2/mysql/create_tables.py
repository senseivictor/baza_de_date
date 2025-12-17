import pymysql
from db_config import DB_CONFIG

conn = pymysql.connect(**DB_CONFIG)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users_login_info (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at INT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id INT AUTO_INCREMENT PRIMARY KEY,
    order_public_id VARCHAR(255) NOT NULL,
    user_id INT,
    products TEXT NOT NULL,
    order_status VARCHAR(255) NOT NULL,
    created_at INT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users_login_info(user_id)
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    price DECIMAL(10,2) NOT NULL
);
""")

# -----------------------------
# Insert initial products
# -----------------------------
products = [
    ("Caricature", 29.99),
    ("Voiceover", 49.99),
    ("Song", 79.99)
]

cursor.executemany("""
INSERT IGNORE INTO products (name, price)
VALUES (%s, %s)
""", products)

conn.commit()
conn.close()

print("MySQL tables created and products inserted.")
