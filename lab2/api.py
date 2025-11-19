from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import uuid
import time
import json

app = FastAPI()

# Allow local HTML pages to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "lab2/lab2.db"


def get_db():
    return sqlite3.connect(DB_PATH)


# ----------- REQUEST MODEL ------------
class OrderRequest(BaseModel):
    user_id: int
    products: list[int]


# ----------- POST /process-order ------------
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


# ----------- GET /get-orders ------------
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
    conn.close()

    data = []
    for r in rows:
        data.append({
            "order_id": r[0],
            "order_public_id": r[1],
            "user_id": r[2],
            "products": r[3],
            "order_status": r[4],
            "created_at": r[5]
        })

    return data
