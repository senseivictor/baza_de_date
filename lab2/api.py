from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql
import uuid
import time
from datetime import datetime, timedelta
import json
from .db_config import DB_CONFIG # Asumând că db_config există

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    """Stabilește și returnează o conexiune la baza de date."""
    # Asigură-te că cursorul este de tip dicționar pentru a returna rânduri ca dict
    return pymysql.connect(**DB_CONFIG)

# --- Modele Pydantic pentru Operațiile CRUD ---

# Utilizatori
class UserCreate(BaseModel):
    name: str

class UserUpdate(BaseModel):
    user_id: int
    name: str | None = None
    # created_at nu este necesar, dar îl lăsăm opțional
    created_at: int | None = None 

# Produse
class ProductCreate(BaseModel):
    name: str
    price: float

class ProductUpdate(BaseModel):
    product_id: int
    name: str | None = None
    price: float | None = None

# Comenzi
class OrderCreate(BaseModel):
    user_id: int
    products: str # Lista de ID-uri de produse sub formă de string JSON (ex: "[1, 2]")
    order_status: str
    order_public_id: str | None = None # Opțional, poate fi generat de server
    created_at: int | None = None # Opțional, poate fi generat de server

class OrderUpdate(BaseModel):
    order_id: int
    user_id: int | None = None
    products: str | None = None # Lista de ID-uri de produse sub formă de string JSON
    order_status: str | None = None
    order_public_id: str | None = None
    created_at: int | None = None

# Modelele existente
class OrderRequest(BaseModel):
    user_id: int
    products: list[int]

class RegisterRequest(BaseModel):
    name: str

# --- RUTĂ GENERICĂ CRUD PENTRU ADMIN ---

TABLE_MODELS = {
    "users_login_info": {
        "add": UserCreate,
        "update": UserUpdate,
        "primary_key": "user_id"
    },
    "products": {
        "add": ProductCreate,
        "update": ProductUpdate,
        "primary_key": "product_id"
    },
    "orders": {
        "add": OrderCreate,
        "update": OrderUpdate,
        "primary_key": "order_id"
    }
}

@app.post("/admin/crud/{table_name}/{action}")
def crud_operation(table_name: str, action: str, payload: dict):
    """
    Ruta generică pentru operațiile CRUD (Add, Update, Delete) pe tabele.
    """
    if table_name not in TABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Tabelă necunoscută: {table_name}")

    if action not in ["add", "update", "delete"]:
        raise HTTPException(status_code=404, detail=f"Acțiune CRUD necunoscută: {action}")

    model_config = TABLE_MODELS[table_name]
    primary_key = model_config["primary_key"]
    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. DELETE
        if action == "delete":
            pk_value = payload.get(primary_key)
            if not pk_value:
                raise HTTPException(status_code=400, detail=f"ID-ul primar ({primary_key}) este necesar pentru ștergere.")

            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key} = %s", (pk_value,))
            if cursor.rowcount == 0:
                 raise HTTPException(status_code=404, detail=f"Înregistrarea cu {primary_key}={pk_value} nu a fost găsită.")
            conn.commit()
            return {"status": "success", "action": "deleted", primary_key: pk_value, "table": table_name}

        # 2. ADD (Create)
        elif action == "add":
            # Validarea Pydantic
            AddSchema = model_config["add"]
            validated_data = AddSchema(**payload)
            
            data_dict = validated_data.model_dump()
            print(data_dict)
            # Gestionare valori implicite
            if table_name == "orders":
                if 'order_public_id' not in data_dict or not data_dict['order_public_id']:
                    data_dict['order_public_id'] = str(uuid.uuid4())
                if 'created_at' not in data_dict or not data_dict['created_at']:
                    data_dict['created_at'] = int(time.time())
            elif table_name == "users_login_info":
                if 'created_at' not in data_dict or not data_dict['created_at']:
                    data_dict['created_at'] = int(time.time())

            fields = ", ".join(data_dict.keys())
            placeholders = ", ".join(["%s"] * len(data_dict))
            values = tuple(data_dict.values())

            query = f"INSERT INTO {table_name} ({fields}) VALUES ({placeholders})"
            cursor.execute(query, values)
            conn.commit()
            
            new_id = cursor.lastrowid
            return {"status": "success", "action": "added", "table": table_name, primary_key: new_id, "data_inserted": data_dict}

        # 3. UPDATE
        elif action == "update":
            # Validarea Pydantic
            UpdateSchema = model_config["update"]
            validated_data = UpdateSchema(**payload)
            
            data_dict = validated_data.model_dump(exclude_none=True)
            
            pk_value = data_dict.pop(primary_key, None)
            
            if not pk_value:
                raise HTTPException(status_code=400, detail=f"ID-ul primar ({primary_key}) este necesar pentru actualizare.")

            if not data_dict:
                raise HTTPException(status_code=400, detail="Nu s-au furnizat câmpuri de actualizat.")
            
            set_clauses = []
            set_values = []
            
            for key, value in data_dict.items():
                set_clauses.append(f"{key} = %s")
                set_values.append(value)

            query = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {primary_key} = %s"
            set_values.append(pk_value)

            cursor.execute(query, tuple(set_values))
            
            if cursor.rowcount == 0:
                 raise HTTPException(status_code=404, detail=f"Înregistrarea cu {primary_key}={pk_value} nu a fost găsită sau nu a fost actualizată.")
            
            conn.commit()
            return {"status": "success", "action": "updated", primary_key: pk_value, "fields_updated": data_dict}

    except pymysql.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Eroare SQL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Eroare de procesare a datelor: {str(e)}")
    finally:
        conn.close()

# --- RUTEE EXISTENTE ---

@app.post("/process-order")
def process_order(order: OrderRequest):
    conn = get_db()
    cursor = conn.cursor()

    order_public_id = str(uuid.uuid4())
    created_at = int(time.time())

    # Verificare Produse - Asigură-te că produsele sunt stocate ca string JSON
    products_json = json.dumps(order.products)

    cursor.execute("""
        INSERT INTO orders 
        (order_public_id, user_id, products, order_status, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        order_public_id,
        order.user_id,
        products_json,
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
        try:
            product_ids = json.loads(r["products"])
            product_names = [product_lookup.get(pid, "Necunoscut") for pid in product_ids]
        except json.JSONDecodeError:
            product_names = ["Eroare format produse"]

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