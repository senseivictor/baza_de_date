import os
import json
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from decimal import Decimal

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=DESKTOPPAV;"
    "Database=victor_dwh;"
    "Trusted_Connection=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")

OUTPUT_DIR = "json_reports"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Clasă pentru a permite serializarea obiectelor Decimal (MONEY din SQL Server) în JSON
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def process_and_save(file_name, query, description):
    print(f"\n--- {description} ---")
    with engine.connect() as conn:
        try:
            result = conn.execute(text(query)).fetchall()
            if result:
                output_data = []
                for row in result:
                    row_dict = dict(row._mapping)
                    
                    if "metadata" in row_dict and row_dict["metadata"]:
                        try:
                            meta = json.loads(row_dict["metadata"])
                            row_dict["metadata_parsed"] = meta
                            
                            if isinstance(meta, dict):
                                row_dict["detalii_tehnice"] = {
                                    "browser_utilizat": meta.get("browser", "Necunoscut"),
                                    "sistem_operare": meta.get("os", "Necunoscut"),
                                    "campanie_sursa": meta.get("source", "Direct")
                                }
                        except:
                            pass
                    
                    if "IstoricMetadata" in row_dict and row_dict["IstoricMetadata"]:
                        try:
                            row_dict["IstoricMetadata"] = json.loads(row_dict["IstoricMetadata"])
                        except:
                            pass
                            
                    output_data.append(row_dict)

                path = f"{OUTPUT_DIR}/{file_name}.json"
                with open(path, "w", encoding='utf-8') as f:
                    json.dump(output_data, f, indent=4, ensure_ascii=False, cls=DecimalEncoder)
                
                print(f"Succes! Date salvate în: {path}")
                print(f"Total rânduri procesate: {len(output_data)}")
            else:
                print("Nu s-au găsit date pentru intervalul selectat (Ultimul Trimestru).")
        except Exception as e:
            print(f"Eroare la execuția query-ului: {e}")

def menu_json():
    while True:
        print("\n" + "="*45)
        print("   MENIU ANALIZĂ SEMANTICĂ JSON (OPTIMIZAT Q4)")
        print("="*45)
        print("1. Analiză Tehnică Complexă (Ultima comandă - Ultimele 90 zile)")
        print("2. Istoric context Utilizator Top (Limitat la 3 luni)")
        print("3. Analiză Surse Trafic Premium (Filtru Timp + Volum)")
        print("4. Rulează toate analizele (Filtru Trimestru)")
        print("0. Ieșire")
        
        opt = input("\nAlege opțiunea: ")
        
        trei_luni_sql = "CONVERT(VARCHAR(8), DATEADD(month, -3, GETDATE()), 112)"
        
        if opt == "1":
            q = f"""
            SELECT TOP 1 
                p.name AS Produs, 
                f.sales_amount, 
                f.metadata,
                u.nume AS Client,
                l.region AS Regiune
            FROM FactOrderItems f
            INNER JOIN DimProduct p ON f.product_id = p.product_id
            INNER JOIN DimUser u ON f.user_id = u.user_id
            INNER JOIN DimLocation l ON f.location_id = l.location_id
            WHERE f.metadata IS NOT NULL 
              AND f.time_id >= {trei_luni_sql}
            ORDER BY f.time_id DESC, f.fact_id DESC
            """
            process_and_save("complex_tech_last_order", q, "Analiză Detaliată Ultima Comandă (Recent)")
            
        elif opt == "2":
            q = f"""
            SELECT TOP 1 u.nume, 
                   (SELECT f.metadata 
                    FROM FactOrderItems f 
                    WHERE f.user_id = u.user_id 
                      AND f.time_id >= {trei_luni_sql}
                    FOR JSON PATH) as IstoricMetadata
            FROM DimUser u
            JOIN FactOrderItems f ON u.user_id = f.user_id
            GROUP BY u.user_id, u.nume
            ORDER BY COUNT(f.fact_id) DESC
            """
            process_and_save("utilizator_top_recent", q, "Context Utilizator Top (Ultimele 3 luni)")

        elif opt == "3":
            q = f"""
            SELECT TOP 100 f.fact_id, f.sales_amount, f.metadata
            FROM FactOrderItems f
            WHERE f.metadata IS NOT NULL
              AND f.time_id >= {trei_luni_sql}
            ORDER BY f.sales_amount DESC
            """
            process_and_save("sursa_trafic_recenta", q, "Top Surse Trafic (Recent)")

        elif opt == "4":
            menu_json_auto_run_all()
        elif opt == "0":
            break
        else:
            print("Opțiune incorectă!")

def menu_json_auto_run_all():
    print("Se rulează setul de rapoarte optimizate pentru ultimul trimestru...")
    trei_luni_sql = "CONVERT(VARCHAR(8), DATEADD(month, -3, GETDATE()), 112)"
    
    q_list = [
        ("ultima_comanda_complex", f"SELECT TOP 1 p.name, f.sales_amount, f.metadata FROM FactOrderItems f JOIN DimProduct p ON f.product_id = p.product_id WHERE f.metadata IS NOT NULL AND f.time_id >= {trei_luni_sql} ORDER BY f.time_id DESC, f.fact_id DESC"),
        ("utilizator_top_trimestru", f"SELECT TOP 1 u.nume, (SELECT f.metadata FROM FactOrderItems f WHERE f.user_id = u.user_id AND f.time_id >= {trei_luni_sql} FOR JSON PATH) as IstoricMetadata FROM DimUser u JOIN FactOrderItems f ON u.user_id = f.user_id GROUP BY u.user_id, u.nume ORDER BY COUNT(f.fact_id) DESC"),
        ("trafic_recent", f"SELECT TOP 50 f.fact_id, f.sales_amount, f.metadata FROM FactOrderItems f WHERE f.metadata IS NOT NULL AND f.time_id >= {trei_luni_sql} ORDER BY f.sales_amount DESC")
    ]
    
    for name, query in q_list:
        process_and_save(name, query, f"Auto-Raport: {name}")

if __name__ == "__main__":
    menu_json()