from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql
import uuid
import time
from datetime import datetime, timedelta
import json
from .db_config import DB_CONFIG

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    return pymysql.connect(**DB_CONFIG)

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
        INSERT INTO orders 
        (order_public_id, user_id, products, order_status, created_at)
        VALUES (%s, %s, %s, %s, %s)
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
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (userId,))

    rows = cursor.fetchall()

    cursor.execute("SELECT product_id, name FROM products")
    product_lookup = {row["product_id"]: row["name"] for row in cursor.fetchall()}

    conn.close()

    data = []
    for r in rows:
        product_ids = json.loads(r["products"])
        product_names = [product_lookup.get(pid, "Necunoscut") for pid in product_ids]

        data.append({
            "order_id": r["order_id"],
            "order_public_id": r["order_public_id"],
            "user_id": r["user_id"],
            "products": ", ".join(product_names),
            "order_status": r["order_status"],
            "created_at": r["created_at"]
        })

    return data


@app.post("/register-user")
def register_user(req: RegisterRequest):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users_login_info WHERE name = %s", (req.name,))
    row = cursor.fetchone()

    if row:
        user_id = row["user_id"]
    else:
        created_at = int(time.time())
        cursor.execute(
            "INSERT INTO users_login_info (name, created_at) VALUES (%s, %s)",
            (req.name, created_at)
        )
        conn.commit()
        user_id = cursor.lastrowid

    conn.close()

    return {
        "status": "ok",
        "user_id": user_id,
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

    cursor.execute("SELECT * FROM orders WHERE order_status = 'completed'")
    rows = cursor.fetchall()

    conn.close()
    return rows


@app.get("/admin/pending-orders")
def pending_orders():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM orders WHERE order_status = 'pending'")
    rows = cursor.fetchall()

    conn.close()
    return rows


@app.get("/admin/orders-last-week")
def orders_last_week():
    conn = get_db()
    cursor = conn.cursor()

    one_week_ago = int(time.time()) - 7 * 86400

    cursor.execute("""
        SELECT created_at FROM orders WHERE created_at >= %s
    """, (one_week_ago,))

    rows = cursor.fetchall()
    conn.close()

    counts = {}
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        counts[day] = 0

    for row in rows:
        day = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d")
        if day in counts:
            counts[day] += 1

    dates = list(reversed(list(counts.keys())))
    values = list(reversed(list(counts.values())))

    return {"dates": dates, "counts": values}
