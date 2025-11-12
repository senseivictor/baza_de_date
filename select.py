import sqlite3

def get_orders_by_user_id(user_id, db_path="lab1.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT order_id, order_public_id, order_status, products, created_at
        FROM orders
        WHERE user_id = ?;
    """, (user_id,))
    
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        print(f"Nici o comanda gasita pentru user_id {user_id}.")
        return

    print(f"Orders for user_id {user_id}:")
    for o in orders:
        print({
            "order_id": o[0],
            "order_public_id": o[1],
            "order_status": o[2],
            "created_at": o[3],
        })

if __name__ == "__main__":
    user_id = int(input("Introduceti id-ul de utilizator: "))
    get_orders_by_user_id(user_id)
