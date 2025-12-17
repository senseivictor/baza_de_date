from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pyodbc # Inlocuitor pentru pymysql
import uuid
import time
from datetime import datetime, timedelta
import json
# Importul de configurare ar trebui să fie funcțional în mediul local
from .db_config import DB_CONFIG 

# --- Inițializare FastAPI ---
app = FastAPI(
    title="DWH Admin API",
    description="Backend pentru operațiuni CRUD și Rapoarte DWH conectat la SQL Server."
)

# Adaugă middleware-ul CORS pentru a permite accesul din frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    """Funcție helper pentru a obține conexiunea la baza de date SQL Server (pyodbc)."""
    try:
        # DB_CONFIG ar trebui sa contina:
        # DRIVER: '{ODBC Driver 17 for SQL Server}'
        # SERVER: 'server_address'
        # DATABASE: 'db_name'
        # UID: 'user'
        # PWD: 'password'
        
        conn_str = (
            f"DRIVER={DB_CONFIG['DRIVER']};"
            f"SERVER={DB_CONFIG['SERVER']};"
            f"DATABASE={DB_CONFIG['DATABASE']};"
            f"UID={DB_CONFIG['UID']};"
            f"PWD={DB_CONFIG['PWD']}"
        )
        conn = pyodbc.connect(conn_str)
        # Setează atributul row_as_dict pentru a returna rândurile ca dicționare
        conn.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
        conn.setencoding(encoding='utf-8')
        return conn
    except pyodbc.Error as ex:
        sqlstate = ex.args[0]
        raise HTTPException(status_code=500, detail=f"Eroare de conexiune SQL Server ({sqlstate}): {ex}")


# ==========================================
# 1. MODELE PYDANTIC PENTRU TABELE DWH (Neschimbate)
# ==========================================

# --- DimUser ---
class DimUserCreate(BaseModel):
    nume: str
    location_id: int | None = None
    created_at: int | None = None

class DimUserUpdate(BaseModel):
    user_id: int
    nume: str | None = None
    location_id: int | None = None
    created_at: int | None = None

# --- DimProduct ---
class DimProductCreate(BaseModel):
    name: str
    price: float

class DimProductUpdate(BaseModel):
    product_id: int
    name: str | None = None
    price: float | None = None

# --- DimOrder ---
class DimOrderCreate(BaseModel):
    user_id: int
    products: str 
    order_status: str
    status_id: int
    order_public_id: str | None = None
    created_at: int | None = None
    created_time_id: int | None = None

class DimOrderUpdate(BaseModel):
    order_id: int
    user_id: int | None = None
    products: str | None = None
    order_status: str | None = None
    status_id: int | None = None
    order_public_id: str | None = None
    created_at: int | None = None
    created_time_id: int | None = None

# --- DimLocation ---
class DimLocationCreate(BaseModel):
    country: str
    region: str

class DimLocationUpdate(BaseModel):
    location_id: int
    country: str | None = None
    region: str | None = None

# --- DimStatus ---
class DimStatusCreate(BaseModel):
    status_name: str
    is_final: int

class DimStatusUpdate(BaseModel):
    status_id: int
    status_name: str | None = None
    is_final: int | None = None

# --- FactOrderItems ---
class FactOrderItemsCreate(BaseModel):
    order_id: int
    user_id: int
    product_id: int
    time_id: int
    status_id: int
    location_id: int
    sales_amount: float
    profit_margin: float
    discount_amount: float | None = 0.0

class FactOrderItemsUpdate(BaseModel):
    fact_id: int
    order_id: int | None = None
    user_id: int | None = None
    product_id: int | None = None
    time_id: int | None = None
    status_id: int | None = None
    location_id: int | None = None
    sales_amount: float | None = None
    profit_margin: float | None = None
    discount_amount: float | None = None


# ==========================================
# 2. DICTIONARUL TABELOR DWH PENTRU CRUD (Neschimbat)
# ==========================================
TABLE_MODELS = {
    "DimUser": {"add": DimUserCreate, "update": DimUserUpdate, "primary_key": "user_id"},
    "DimProduct": {"add": DimProductCreate, "update": DimProductUpdate, "primary_key": "product_id"},
    "DimOrder": {"add": DimOrderCreate, "update": DimOrderUpdate, "primary_key": "order_id"},
    "DimLocation": {"add": DimLocationCreate, "update": DimLocationUpdate, "primary_key": "location_id"},
    "DimStatus": {"add": DimStatusCreate, "update": DimStatusUpdate, "primary_key": "status_id"},
    "FactOrderItems": {"add": FactOrderItemsCreate, "update": FactOrderItemsUpdate, "primary_key": "fact_id"},
}

# ==========================================
# 3. RUTA GENERICĂ CRUD (Adaptată pentru pyodbc/SQL Server)
# ==========================================

def execute_query(cursor, query, params=None, fetch_all=False):
    """Funcție helper pentru a executa interogări și a returna dicționare."""
    if params is None:
        params = []
    
    cursor.execute(query, params)
    
    if query.strip().upper().startswith(("SELECT", "WITH")):
        # Extrage numele coloanelor pentru a crea dicționare
        columns = [column[0] for column in cursor.description]
        if fetch_all:
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            row = cursor.fetchone()
            return dict(zip(columns, row)) if row else None
    return None

@app.post("/admin/crud/{table_name}/{action}")
def crud_operation(table_name: str, action: str, payload: dict = Body(...)):
    """Operatii CRUD generice pe tabelele DWH, adaptate pentru SQL Server/pyodbc."""
    if table_name not in TABLE_MODELS:
        raise HTTPException(status_code=404, detail=f"Tabelă DWH necunoscută: {table_name}")
    
    model_config = TABLE_MODELS[table_name]
    primary_key = model_config["primary_key"]
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        if action == "delete":
            pk_value = payload.get(primary_key)
            if not pk_value: raise HTTPException(status_code=400, detail=f"ID-ul principal ({primary_key}) necesar pentru ștergere.")
            cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key} = ?", (pk_value,))
            conn.commit()
            return {"status": "success", "action": "deleted", "id": pk_value}

        elif action == "add":
            AddSchema = model_config["add"]
            validated = AddSchema(**payload).model_dump(exclude_none=True)
            
            # Logica de setare ID-uri/timp automat
            if table_name == "DimOrder":
                if 'order_public_id' not in validated: validated['order_public_id'] = str(uuid.uuid4())
                if 'created_at' not in validated: validated['created_at'] = int(time.time())
            elif table_name == "DimUser":
                if 'created_at' not in validated: validated['created_at'] = int(time.time())
            
            # Pentru SQL Server, trebuie să excludem coloanele Identity
            is_identity = table_name in ["DimUser", "DimProduct", "DimOrder", "DimStatus", "FactOrderItems"]
            if primary_key in validated and is_identity and table_name != "DimLocation":
                validated.pop(primary_key, None)

            cols = ", ".join(validated.keys())
            vals = tuple(validated.values())
            plhs = ", ".join(["?"] * len(vals)) # Placeholder '?' pentru pyodbc
            
            # Interogarea de inserare
            insert_query = f"INSERT INTO {table_name} ({cols}) VALUES ({plhs})"
            cursor.execute(insert_query, vals)
            
            # Obține ID-ul inserat pentru SQL Server (IDENTITY_INSERT ON nu este necesar aici)
            last_id = None
            if is_identity:
                cursor.execute("SELECT SCOPE_IDENTITY() AS new_id")
                last_id = cursor.fetchone()[0]

            conn.commit()
            return {"status": "success", "action": "added", "data": validated, "inserted_id": last_id}

        elif action == "update":
            UpdSchema = model_config["update"]
            validated = UpdSchema(**payload).model_dump(exclude_none=True)
            pk = validated.pop(primary_key, None)
            
            if not pk: raise HTTPException(status_code=400, detail=f"ID-ul principal ({primary_key}) necesar pentru actualizare.")
            
            clauses = [f"{k}=?" for k in validated.keys()]
            vals = list(validated.values()) + [pk]
            
            if not clauses: return {"status": "warning", "action": "no_update", "detail": "Nu s-au furnizat câmpuri de actualizat."}
            
            update_query = f"UPDATE {table_name} SET {', '.join(clauses)} WHERE {primary_key}=?"
            cursor.execute(update_query, tuple(vals))
            conn.commit()
            return {"status": "success", "action": "updated", "id": pk}

    except pyodbc.Error as e:
        conn.rollback()
        sqlstate = e.args[0]
        raise HTTPException(status_code=400, detail=f"Eroare SQL Server ({sqlstate}): {str(e)}")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Eroare necunoscută: {str(e)}")
    finally:
        conn.close()

# ==========================================
# 4. RUTE PENTRU RAPOARTE DWH (Adaptate pentru SQL Server)
# Conversia de la UNIX_TIMESTAMP la datetime pentru SQL Server
# ==========================================

# SQL Server folosește DATEADD(second, [timestamp], '1970-01-01') pentru a converti UNIX_TIMESTAMP
def get_sqls_time_conversion(timestamp_param):
    """Returnează sintaxa SQL Server pentru a converti un timestamp UNIX în datetime."""
    return f"DATEADD(second, {timestamp_param}, '1970-01-01')"


# 1. Produsul cu cel mai mare și cel mai mic volum de vânzări
@app.get("/admin/reports/top-low-sales")
def top_low_sales(
    start: int = Query(..., description="Start Timestamp"), 
    end: int = Query(..., description="End Timestamp")
):
    """Report 1: Produsul cu cel mai mare și cel mai mic volum de vânzări (Sales Amount)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        start_date_sql = get_sqls_time_conversion(start)
        end_date_sql = get_sqls_time_conversion(end)
        
        # Folosim ROW_NUMBER() pentru a simula LIMIT sau OFFSET (deși putem folosi TOP pentru simplitate)
        query = f"""
            SELECT 
                DP.name AS ProductName, 
                SUM(FOI.sales_amount) AS TotalSales
            FROM FactOrderItems FOI
            JOIN DimProduct DP ON FOI.product_id = DP.product_id
            JOIN DimTime DT ON FOI.time_id = DT.time_id
            WHERE DT.full_date >= {start_date_sql} AND DT.full_date <= {end_date_sql}
            GROUP BY DP.name
            ORDER BY TotalSales DESC;
        """
        results = execute_query(cursor, query, fetch_all=True)

        if not results:
            return {"message": "Nu există date în FactOrderItems pentru perioada selectată."}

        top_product = results[0]
        low_product = results[-1]
        
        return {
            "TopProduct": top_product,
            "LowProduct": low_product,
            "AllResults": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la generarea raportului 1: {str(e)}")
    finally:
        conn.close()

# 2. Trimestrul cu cel mai mare profit total
@app.get("/admin/reports/top-quarter-profit")
def top_quarter_profit(
    start: int = Query(..., description="Start Timestamp"), 
    end: int = Query(..., description="End Timestamp")
):
    """Report 2: Trimestrul cu cel mai mare profit total."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        start_date_sql = get_sqls_time_conversion(start)
        end_date_sql = get_sqls_time_conversion(end)

        query = f"""
            SELECT TOP 1 
                CONCAT(DT.year, '-Q', DT.quarter) AS Quarter,
                SUM(FOI.sales_amount * FOI.profit_margin) AS TotalProfit
            FROM FactOrderItems FOI
            JOIN DimTime DT ON FOI.time_id = DT.time_id
            WHERE DT.full_date >= {start_date_sql} AND DT.full_date <= {end_date_sql}
            GROUP BY DT.year, DT.quarter
            ORDER BY TotalProfit DESC;
        """
        result = execute_query(cursor, query)

        if not result:
            return {"message": "Nu s-a găsit profit în FactOrderItems pentru perioada selectată."}

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la generarea raportului 2: {str(e)}")
    finally:
        conn.close()

# 3. Top 10 Utilizatori după numărul de comenzi distincte
@app.get("/admin/reports/top-10-users-orders")
def top_10_users_orders(
    start: int = Query(..., description="Start Timestamp"), 
    end: int = Query(..., description="End Timestamp")
):
    """Report 3: Top 10 Utilizatori după numărul de comenzi distincte."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        start_date_sql = get_sqls_time_conversion(start)
        end_date_sql = get_sqls_time_conversion(end)
        
        query = f"""
            SELECT TOP 10 
                DU.nume AS UserName,
                COUNT(DISTINCT FOI.order_id) AS DistinctOrderCount
            FROM FactOrderItems FOI
            JOIN DimUser DU ON FOI.user_id = DU.user_id
            JOIN DimTime DT ON FOI.time_id = DT.time_id
            WHERE DT.full_date >= {start_date_sql} AND DT.full_date <= {end_date_sql}
            GROUP BY DU.nume
            ORDER BY DistinctOrderCount DESC;
        """
        results = execute_query(cursor, query, fetch_all=True)
        
        if not results:
            return {"message": "Nu s-au găsit comenzi distincte în FactOrderItems pentru perioada selectată."}
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la generarea raportului 3: {str(e)}")
    finally:
        conn.close()

# 4. Procentul mediu de discount (Weekend vs. Zile Săptămânale)
@app.get("/admin/reports/avg-discount-weekend-vs-weekday")
def avg_discount_weekend_vs_weekday(
    start: int = Query(..., description="Start Timestamp"), 
    end: int = Query(..., description="End Timestamp")
):
    """Report 4: Procentul mediu de discount, împărțit pe Weekend vs Zile Săptămânale."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        start_date_sql = get_sqls_time_conversion(start)
        end_date_sql = get_sqls_time_conversion(end)

        query = f"""
            SELECT 
                CASE
                    WHEN DT.is_weekend = 1 THEN 'Weekend'
                    ELSE 'Zi de Saptamana'
                END AS Perioada,
                AVG(FOI.discount_amount / FOI.sales_amount) * 100 AS Procent_Mediu_Discount
            FROM FactOrderItems FOI
            JOIN DimTime DT ON FOI.time_id = DT.time_id
            WHERE DT.full_date >= {start_date_sql} AND DT.full_date <= {end_date_sql}
            AND FOI.sales_amount > 0 
            GROUP BY DT.is_weekend
            ORDER BY DT.is_weekend DESC;
        """
        results = execute_query(cursor, query, fetch_all=True)

        if not results:
            return {"message": "Nu s-au găsit date de discount în FactOrderItems pentru perioada selectată."}
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la generarea raportului 4: {str(e)}")
    finally:
        conn.close()

# 5. Clasificarea Produselor după Volumul Total de Vânzări
@app.get("/admin/reports/product-sales-classification")
def product_sales_classification(
    start: int = Query(..., description="Start Timestamp"), 
    end: int = Query(..., description="End Timestamp")
):
    """Report 5: Clasificarea Produselor (Top, Mediu, Slab) după Volumul Total de Vânzări (Sales Amount)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        start_date_sql = get_sqls_time_conversion(start)
        end_date_sql = get_sqls_time_conversion(end)
        
        # Clasificarea produselor în SQL Server folosind funcții de fereastră sau CTE-uri
        query = f"""
            WITH ProductSales AS (
                SELECT 
                    DP.name AS ProductName, 
                    SUM(FOI.sales_amount) AS TotalSales
                FROM FactOrderItems FOI
                JOIN DimProduct DP ON FOI.product_id = DP.product_id
                JOIN DimTime DT ON FOI.time_id = DT.time_id
                WHERE DT.full_date >= {start_date_sql} AND DT.full_date <= {end_date_sql}
                GROUP BY DP.name
            ),
            SalesStats AS (
                SELECT AVG(TotalSales) AS AvgSales, MAX(TotalSales) AS MaxSales FROM ProductSales
            )
            SELECT
                PS.ProductName,
                PS.TotalSales,
                CASE
                    -- Presupune că MaxSales și AvgSales există
                    WHEN PS.TotalSales >= (SS.AvgSales + (SS.MaxSales - SS.AvgSales) / 2) THEN 'Top Seller'
                    WHEN PS.TotalSales >= SS.AvgSales THEN 'Average Seller'
                    ELSE 'Low Seller'
                END AS Classification
            FROM ProductSales PS
            CROSS JOIN SalesStats SS
            ORDER BY PS.TotalSales DESC;
        """
        results = execute_query(cursor, query, fetch_all=True)

        if not results:
            return {"message": "Nu există date de vânzări în FactOrderItems pentru perioada selectată."}
            
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Eroare la generarea raportului 5: {str(e)}")
    finally:
        conn.close()

# ==========================================
# 5. RUTE LEGACY/PLACEHOLDER (Adaptate pentru SQL Server)
# ==========================================

def resolve_product_names(conn, product_ids_json):
    """Funcție helper pentru a rezolva ID-urile de produs în nume (OLTP/SQL Server)."""
    if not product_ids_json:
        return []
    
    try:
        p_ids = json.loads(product_ids_json)
        if isinstance(p_ids, int): p_ids = [p_ids]
        
        cursor = conn.cursor()
        if not p_ids: return []
        
        placeholders = ', '.join(['?'] * len(p_ids))
        query = f"SELECT product_id, name FROM products WHERE product_id IN ({placeholders})"
        
        cursor.execute(query, tuple(p_ids))
        
        # Extrage rezultatele ca dicționare
        columns = [column[0] for column in cursor.description]
        product_lookup = {row[0]: row[1] for row in cursor.fetchall()} # Assuming product_id is the first column
        
        return [product_lookup.get(pid, f"ID Necunoscut {pid}") for pid in p_ids]
    except Exception:
        return ["Eroare la parsarea ID-urilor de produs"]

@app.get("/admin/latest-order")
def latest_order():
    """Obține cea mai recentă comandă din tabela OLTP veche 'orders' (SQL Server)."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Folosim TOP 1 și alias-uri
        query = """
            SELECT TOP 1 o.order_id, o.order_public_id, o.products, o.order_status, o.created_at, u.name as user_name
            FROM orders o
            JOIN users_login_info u ON o.user_id = u.user_id
            ORDER BY o.created_at DESC
        """
        order = execute_query(cursor, query)
        
        if not order:
            return {"message": "Nu s-a găsit nicio comandă în tabela OLTP.", "data": None}
        
        product_names = resolve_product_names(conn, order.get('products'))
        
        order['products'] = ", ".join(product_names)
        order['date'] = datetime.fromtimestamp(order['created_at']).strftime("%Y-%m-%d %H:%M:%S")
        return {"warning": "Aceste date provin din tabela OLTP veche. Folosiți /admin/reports/ pentru DWH.", "data": order}
    finally:
        conn.close()

def get_orders_by_status(conn, status: str):
    """Funcție helper pentru rutele completed/pending orders (OLTP/SQL Server)."""
    cursor = conn.cursor()
    query = """
        SELECT TOP 50 o.order_id, o.order_public_id, o.created_at, u.name as user_name, o.products
        FROM orders o
        JOIN users_login_info u ON o.user_id = u.user_id
        WHERE o.order_status = ?
        ORDER BY o.created_at DESC
    """
    orders = execute_query(cursor, query, params=[status], fetch_all=True)
    
    for order in orders:
        order['date'] = datetime.fromtimestamp(order['created_at']).strftime("%Y-%m-%d %H:%M")
        order['products'] = ", ".join(resolve_product_names(conn, order.get('products')))
    
    return {"warning": "Aceste date provin din tabela OLTP veche. Folosiți /admin/reports/ pentru DWH.", "status": status, "count": len(orders), "orders": orders}

@app.get("/admin/completed-orders")
def completed_orders():
    """Obține ultimele 50 de comenzi finalizate din tabela OLTP (SQL Server)."""
    conn = get_db()
    try:
        return get_orders_by_status(conn, "completed")
    finally:
        conn.close()

@app.get("/admin/pending-orders")
def pending_orders():
    """Obține ultimele 50 de comenzi în așteptare din tabela OLTP (SQL Server)."""
    conn = get_db()
    try:
        return get_orders_by_status(conn, "pending")
    finally:
        conn.close()

@app.get("/admin/orders-last-week")
def orders_last_week():
    """Numărul de comenzi pe ultimele 7 zile (OLTP/SQL Server)."""
    end_ts = int(time.time())
    start_dt = datetime.fromtimestamp(end_ts) - timedelta(days=6)
    start_ts = int(start_dt.timestamp())
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT created_at FROM orders 
            WHERE created_at >= ? AND created_at <= ?
        """
        cursor.execute(query, (start_ts, end_ts))
        
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        counts = {}
        for i in range(7):
            day_dt = start_dt + timedelta(days=i)
            day_str = day_dt.strftime("%Y-%m-%d")
            counts[day_str] = 0
            
        for row in rows:
            day = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d")
            if day in counts:
                counts[day] += 1
            
        dates = list(counts.keys())
        counts_list = list(counts.values())
        
        return {"warning": "OLTP Data. Folosiți DWH reports.", "dates": dates, "counts": counts_list}
    finally:
        conn.close()

# Rutele vechi de statistică OLTP
@app.get("/admin/stats/user-orders")
def get_user_orders_by_name_old(
    name: str, 
    start: int = Query(..., description="Start Timestamp"), 
    end: int = Query(..., description="End Timestamp")
):
    """Avertisment: Această rută folosește tabele OLTP vechi. Recomandat: Rapoarte DWH."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id, name FROM users_login_info WHERE name = ?", (name,))
        user = execute_query(cursor, "SELECT user_id, name FROM users_login_info WHERE name = ?", params=[name])
        
        if not user:
            raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit.")
        
        user_id = user['user_id']
        query = """
             SELECT order_id, order_public_id, products, order_status, created_at 
             FROM orders 
             WHERE user_id = ? AND created_at >= ? AND created_at <= ?
             ORDER BY created_at DESC
        """
        orders = execute_query(cursor, query, params=[user_id, start, end], fetch_all=True)
        
        result = []
        for r in orders:
            p_names = resolve_product_names(conn, r["products"])
            result.append({
                "order_id": r["order_id"],
                "products": ", ".join(p_names),
                "status": r["order_status"],
                "date": datetime.fromtimestamp(r["created_at"]).strftime("%Y-%m-%d %H:%M")
            })
        return {"warning": "OLTP Data. Folosiți DWH reports.", "user": name, "count": len(result), "orders": result}
    finally:
        conn.close()

@app.get("/admin/stats/order-status")
def stats_order_status_old(start: int = Query(...), end: int = Query(...)):
    """Avertisment: Această rută folosește tabele OLTP vechi. Recomandat: Rapoarte DWH."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT order_status, COUNT(*) as count 
            FROM orders 
            WHERE created_at >= ? AND created_at <= ?
            GROUP BY order_status
        """
        rows = execute_query(cursor, query, params=[start, end], fetch_all=True)
        return {"warning": "OLTP Data. Folosiți DWH reports.", "data": {row['order_status']: row['count'] for row in rows}}
    finally:
        conn.close()

@app.get("/admin/stats/daily-orders")
def stats_daily_orders_old(start: int = Query(...), end: int = Query(...)):
    """Avertisment: Această rută folosește tabele OLTP vechi. Recomandat: Rapoarte DWH."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT created_at FROM orders 
            WHERE created_at >= ? AND created_at <= ?
        """
        cursor.execute(query, (start, end))
        
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        counts = {}
        for row in rows:
            day = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d")
            counts[day] = counts.get(day, 0) + 1
        
        dates = sorted(counts.keys())
        counts_list = [counts[d] for d in dates]

        return {"warning": "OLTP Data. Folosiți DWH reports.", "dates": dates, "counts": counts_list}
    finally:
        conn.close()

@app.get("/admin/stats/new-users")
def stats_new_users_old(start: int = Query(...), end: int = Query(...)):
    """Avertisment: Această rută folosește tabele OLTP vechi. Recomandat: Rapoarte DWH."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT created_at FROM users_login_info 
            WHERE created_at >= ? AND created_at <= ?
        """
        cursor.execute(query, (start, end))
        
        columns = [column[0] for column in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        counts = {}
        for row in rows:
            day = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d")
            counts[day] = counts.get(day, 0) + 1

        dates = sorted(counts.keys())
        counts_list = [counts[d] for d in dates]

        return {"warning": "OLTP Data. Folosiți DWH reports.", "dates": dates, "counts": counts_list}
    finally:
        conn.close()

@app.get("/admin/stats/products-popularity")
def stats_products_old(start: int = Query(...), end: int = Query(...)):
    """Avertisment: Această rută folosește tabele OLTP vechi. Recomandat: Rapoarte DWH."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        query = """
            SELECT products FROM orders 
            WHERE created_at >= ? AND created_at <= ?
        """
        cursor.execute(query, (start, end))
        columns = [column[0] for column in cursor.description]
        orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        
        product_map = {}
        cursor.execute("SELECT product_id, name FROM products")
        columns = [column[0] for column in cursor.description]
        products_db = [dict(zip(columns, row)) for row in cursor.fetchall()]
        product_map = {p['product_id']: p['name'] for p in products_db}
        
        product_counts = {}
        for order in orders:
            try:
                prod_ids = json.loads(order['products'])
                if isinstance(prod_ids, int): prod_ids = [prod_ids]
                for pid in prod_ids:
                    p_name = product_map.get(pid, f"ID {pid}")
                    product_counts[p_name] = product_counts.get(p_name, 0) + 1
            except:
                continue

        return {"warning": "OLTP Data. Folosiți DWH reports.", "data": product_counts}
    finally:
        conn.close()