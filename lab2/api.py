from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import uuid
import time
from datetime import datetime, timedelta
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "lab2/lab2.db"


def get_db():
    return sqlite3.connect(DB_PATH)


class OrderRequest(BaseModel):
    user_id: int
    products: list[int]

class RegisterRequest(BaseModel):
    name: str

@app.post("/process-order")
def process_order(order: OrderRequest):
    conn = get_db()
    cursor = conn.cursor()

    order_public_id = str(uuid.uuid4())
    created_at = int(time.time())

    cursor.execute("""
        INSERT INTO orders (order_public_id, user_id, products, order_status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        order_public_id,
        order.user_id,
        json.dumps(order.products),
        "completed",
        created_at
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "Comanda a fost procesată!",
        "order_public_id": order_public_id
    }


@app.get("/get-orders")
def get_orders(userId: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_id, order_public_id, user_id, products, order_status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (userId,))

    rows = cursor.fetchall()

    cursor.execute("SELECT product_id, name FROM products")
    product_lookup = {row[0]: row[1] for row in cursor.fetchall()} # creeaza dictionar cheie - valoare

    conn.close()

    data = []
    for r in rows:
        product_ids = json.loads(r[3])

        product_names = [product_lookup.get(pid, "Necunoscut") for pid in product_ids]
        product_string = ", ".join(product_names)

        data.append({
            "order_id": r[0],
            "order_public_id": r[1],
            "user_id": r[2],
            "products": product_string,
            "order_status": r[4],
            "created_at": r[5]
        })

    return data

@app.post("/register-user")
def register_user(req: RegisterRequest):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users_login_info WHERE name = ?", (req.name,))
    row = cursor.fetchone()

    if row: 
        user_id = row[0]
    else:
        created = int(time.time())
        cursor.execute(
            "INSERT INTO users_login_info (name, created_at) VALUES (?, ?)",
            (req.name, created)
        )
        user_id = cursor.lastrowid
        conn.commit()

    conn.close()

    return {
        "status": "ok",
        "user_id": user_id
    }


@app.get("/admin/latest-order")
def latest_order():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders ORDER BY created_at DESC LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    return row


@app.get("/admin/completed-orders")
def completed_orders():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders WHERE order_status = 'completed'
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.get("/admin/pending-orders")
def pending_orders():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders WHERE order_status = 'pending'
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.get("/admin/orders-last-week")
def orders_last_week():
    conn = get_db()
    cursor = conn.cursor()

    one_week_ago = int(time.time()) - 7 * 86400

    cursor.execute("""
        SELECT created_at FROM orders WHERE created_at >= ?
    """, (one_week_ago,))

    rows = cursor.fetchall()
    conn.close()

    counts = {}
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        counts[day] = 0

    for (ts,) in rows:
        day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        if day in counts:
            counts[day] += 1

    dates = list(reversed(list(counts.keys())))
    values = list(reversed(list(counts.values())))

    return {"dates": dates, "counts": values}