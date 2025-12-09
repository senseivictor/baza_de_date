from fastapi import FastAPI, HTTPException
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

# --- Modele Pydantic ---
class OrderRequest(BaseModel):
    user_id: int
    products: list[int]

class RegisterRequest(BaseModel):
    name: str

# Modele CRUD
class UserCreate(BaseModel):
    name: str
class UserUpdate(BaseModel):
    user_id: int
    name: str | None = None
    created_at: int | None = None
class ProductCreate(BaseModel):
    name: str
    price: float
class ProductUpdate(BaseModel):
    product_id: int
    name: str | None = None
    price: float | None = None
class OrderCreate(BaseModel):
    user_id: int
    products: str 
    order_status: str
    order_public_id: str | None = None
    created_at: int | None = None
class OrderUpdate(BaseModel):
    order_id: int
    user_id: int | None = None
    products: str | None = None
    order_status: str | None = None
    order_public_id: str | None = None
    created_at: int | None = None

# Configurare CRUD
TABLE_MODELS = {
    "users_login_info": {"add": UserCreate, "update": UserUpdate, "primary_key": "user_id"},
    "products": {"add": ProductCreate, "update": ProductUpdate, "primary_key": "product_id"},
    "orders": {"add": OrderCreate, "update": OrderUpdate, "primary_key": "order_id"}
}

# --- RUTE NOI PENTRU OBIECTIVE ---

@app.get("/admin/stats/order-status")
def stats_order_status():
    """Obiectiv 2: Statistica comenzi finalizate vs nefinalizate"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT order_status, COUNT(*) as count FROM orders GROUP BY order_status")
    rows = cursor.fetchall()
    conn.close()
    
    # Formatăm pentru frontend: {"completed": 10, "pending": 5}
    stats = {row['order_status']: row['count'] for row in rows}
    return stats

@app.get("/admin/stats/new-users-last-week")
def stats_new_users():
    """Obiectiv 4: Statistica utilizatori noi ultima saptamana"""
    conn = get_db()
    cursor = conn.cursor()
    one_week_ago = int(time.time()) - 7 * 86400
    
    cursor.execute("SELECT created_at FROM users_login_info WHERE created_at >= %s", (one_week_ago,))
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

@app.get("/admin/stats/products-popularity")
def stats_products():
    """Obiectiv 5: Statistica comenzi pe tipul de produse"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Luăm toate comenzile
    cursor.execute("SELECT products FROM orders")
    orders = cursor.fetchall()
    
    # 2. Luăm numele produselor pentru mapare
    cursor.execute("SELECT product_id, name FROM products")
    products_db = cursor.fetchall()
    product_map = {p['product_id']: p['name'] for p in products_db}
    conn.close()

    product_counts = {}

    for order in orders:
        try:
            # products este stocat ca string JSON "[1, 2]"
            prod_ids = json.loads(order['products'])
            if isinstance(prod_ids, list):
                for pid in prod_ids:
                    p_name = product_map.get(pid, f"ID {pid}")
                    product_counts[p_name] = product_counts.get(p_name, 0) + 1
            elif isinstance(prod_ids, int): # Fallback pentru legacy data
                 p_name = product_map.get(prod_ids, f"ID {prod_ids}")
                 product_counts[p_name] = product_counts.get(p_name, 0) + 1
        except:
            continue

    return product_counts

# --- RESTUL RUTELOR EXISTENTE (Păstrate pentru compatibilitate) ---

@app.post("/admin/crud/{table_name}/{action}")
def crud_operation(table_name: str, action: str, payload: dict):
    if table_name not in TABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Tabelă necunoscută: {table_name}")
    if action not in ["add", "update", "delete"]:
        raise HTTPException(status_code=404, detail=f"Acțiune necunoscută: {action}")

    model_config = TABLE_MODELS[table_name]
    primary_key = model_config["primary_key"]
    conn = get_db()
    cursor = conn.cursor()

    try:
        if action == "delete":
            pk_value = payload.get(primary_key)
            if not pk_value:
                raise HTTPException(status_code=400, detail=f"ID necesar.")
            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key} = %s", (pk_value,))
            if cursor.rowcount == 0: raise HTTPException(status_code=404, detail="Inregistrare negasita.")
            conn.commit()
            return {"status": "success", "action": "deleted"}

        elif action == "add":
            AddSchema = model_config["add"]
            validated_data = AddSchema(**payload)
            data_dict = validated_data.model_dump()
            
            # Defaults
            if table_name == "orders":
                if not data_dict.get('order_public_id'): data_dict['order_public_id'] = str(uuid.uuid4())
                if not data_dict.get('created_at'): data_dict['created_at'] = int(time.time())
            elif table_name == "users_login_info":
                if not data_dict.get('created_at'): data_dict['created_at'] = int(time.time())

            fields = ", ".join(data_dict.keys())
            placeholders = ", ".join(["%s"] * len(data_dict))
            values = tuple(data_dict.values())
            cursor.execute(f"INSERT INTO {table_name} ({fields}) VALUES ({placeholders})", values)
            conn.commit()
            return {"status": "success", "action": "added", "id": cursor.lastrowid}

        elif action == "update":
            UpdateSchema = model_config["update"]
            validated_data = UpdateSchema(**payload)
            data_dict = validated_data.model_dump(exclude_none=True)
            pk_value = data_dict.pop(primary_key, None)
            
            if not pk_value: raise HTTPException(status_code=400, detail="ID necesar.")
            if not data_dict: raise HTTPException(status_code=400, detail="Fara date de actualizat.")
            
            set_clauses = [f"{key} = %s" for key in data_dict.keys()]
            values = list(data_dict.values())
            values.append(pk_value)
            
            cursor.execute(f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {primary_key} = %s", tuple(values))
            conn.commit()
            return {"status": "success", "action": "updated"}

    except pymysql.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Eroare SQL: {e}")
    finally:
        conn.close()

@app.post("/process-order")
def process_order(order: OrderRequest):
    conn = get_db()
    cursor = conn.cursor()
    order_public_id = str(uuid.uuid4())
    created_at = int(time.time())
    cursor.execute("INSERT INTO orders (order_public_id, user_id, products, order_status, created_at) VALUES (%s, %s, %s, %s, %s)", 
                   (order_public_id, order.user_id, json.dumps(order.products), "completed", created_at))
    conn.commit()
    conn.close()
    return {"status": "success", "order_public_id": order_public_id}

@app.get("/get-orders")
def get_orders(userId: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC", (userId,))
    rows = cursor.fetchall()
    
    cursor.execute("SELECT product_id, name FROM products")
    product_lookup = {row["product_id"]: row["name"] for row in cursor.fetchall()}
    conn.close()

    data = []
    for r in rows:
        try:
            p_ids = json.loads(r["products"])
            p_names = [product_lookup.get(pid, "Unknown") for pid in p_ids]
        except: p_names = ["Error"]
        
        data.append({
            "order_id": r["order_id"],
            "user_id": r["user_id"],
            "products": ", ".join(p_names),
            "order_status": r["order_status"],
            "created_at": r["created_at"]
        })
    return data

@app.get("/admin/latest-order")
def latest_order():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 1")
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
    cursor.execute("SELECT created_at FROM orders WHERE created_at >= %s", (one_week_ago,))
    rows = cursor.fetchall()
    conn.close()
    counts = {}
    for i in range(7):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        counts[day] = 0
    for row in rows:
        day = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d")
        if day in counts: counts[day] += 1
    return {"dates": list(reversed(list(counts.keys()))), "counts": list(reversed(list(counts.values())))}