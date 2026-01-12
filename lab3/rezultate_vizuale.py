import os
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

conn_str = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=DESKTOPPAV;"
    "Database=victor_dwh;"
    "Trusted_Connection=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")

# Director pentru salvarea graficelor
OUTPUT_DIR = "graphs_output"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Filtru global pentru ultimele 3 luni (format YYYYMMDD pentru time_id)
TREI_LUNI_SQL = "CONVERT(VARCHAR(8), DATEADD(month, -3, GETDATE()), 112)"

def report_venituri_servicii():
    """Raport 1: Venituri per Tip de Serviciu (Bar Chart)"""
    print("\n[1] Raport: Venituri per Tip de Serviciu (Ultimele 3 luni)")
    q = f"""
    SELECT p.name as Serviciu, SUM(f.sales_amount) as TotalIncasari, COUNT(f.fact_id) as NrComenzi
    FROM FactOrderItems f
    JOIN DimProduct p ON f.product_id = p.product_id
    WHERE f.time_id >= {TREI_LUNI_SQL}
    GROUP BY p.name
    ORDER BY TotalIncasari DESC
    """
    df = pd.read_sql(text(q), engine)
    
    if not df.empty:
        print(df.to_string(index=False))
        plt.figure(figsize=(10, 5))
        plt.bar(df['Serviciu'], df['TotalIncasari'], color='plum')
        plt.title('Venituri per Tip de Serviciu Digital (Ultimul Trimestru)')
        plt.ylabel('Suma')
        plt.savefig(f"{OUTPUT_DIR}/venituri_servicii.png")
        print(f"--> Grafic salvat: {OUTPUT_DIR}/venituri_servicii.png")
    else:
        print("Nu există date de vânzări în ultimele 3 luni.")

def report_distributie_regiuni():
    """Raport 2: Distribuția Comenzilor pe Regiuni (Pie Chart)"""
    print("\n[2] Raport: Distribuția Comenzilor pe Regiuni (Top 5 - Ultimele 3 luni)")
    q = f"""
    SELECT TOP 5 l.region as Regiune, COUNT(f.fact_id) as ComenziActive
    FROM FactOrderItems f
    JOIN DimLocation l ON f.location_id = l.location_id
    WHERE f.time_id >= {TREI_LUNI_SQL}
    GROUP BY l.region
    ORDER BY ComenziActive DESC
    """
    df = pd.read_sql(text(q), engine)
    
    if not df.empty:
        print(df.to_string(index=False))
        plt.figure(figsize=(8, 8))
        plt.pie(df['ComenziActive'], labels=df['Regiune'], autopct='%1.1f%%', startangle=140)
        plt.title('Top Regiuni după Volumul de Comenzi (Recent)')
        plt.savefig(f"{OUTPUT_DIR}/regiuni_top_pie.png")
        print(f"--> Grafic salvat: {OUTPUT_DIR}/regiuni_top_pie.png")
    else:
        print("Nu există date geografice pentru ultimele 3 luni.")

def report_evolutie_vanzari():
    """Raport 3: Evoluția Vânzărilor în Timp (Line Chart)"""
    print("\n[3] Raport: Evoluția Vânzărilor în ultimele 3 luni")
    q = f"""
    SELECT f.time_id as Perioada, SUM(f.sales_amount) as Vanzari
    FROM FactOrderItems f
    WHERE f.time_id >= {TREI_LUNI_SQL}
    GROUP BY f.time_id
    ORDER BY f.time_id
    """
    df = pd.read_sql(text(q), engine)
    
    if not df.empty:
        # Convertim ID-ul numeric (YYYYMMDD) în string formatat (DD.MM.YYYY)
        def format_date_id(date_id):
            s = str(int(date_id))
            if len(s) == 8:
                return f"{s[6:8]}.{s[4:6]}.{s[0:4]}"
            return s

        df['Data_Formata'] = df['Perioada'].apply(format_date_id)
        
        print(df[['Data_Formata', 'Vanzari']].to_string(index=False))
        
        plt.figure(figsize=(12, 6))
        plt.plot(df['Data_Formata'], df['Vanzari'], marker='o', linestyle='-', color='green', linewidth=2)
        plt.title('Evoluție Vânzări Zilnice (Ultimele 3 Luni)')
        plt.xlabel('Data')
        plt.ylabel('Vânzări')
        plt.xticks(rotation=45)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.savefig(f"{OUTPUT_DIR}/evolutie_vanzari.png")
        print(f"--> Grafic salvat: {OUTPUT_DIR}/evolutie_vanzari.png")
    else:
        print("Nu există date cronologice pentru ultimele 3 luni.")

def main_menu():
    while True:
        print("\n" + "="*45)
        print("   MENIU ANALIZĂ VIZUALĂ DWH (3 LUNI)")
        print("="*45)
        print("1. Venituri per Tip de Serviciu (Bar Chart)")
        print("2. Distribuție pe Regiuni (Pie Chart)")
        print("3. Evoluție Vânzări (Line Chart)")
        print("4. Rulează toate rapoartele")
        print("0. Ieșire")
        
        opt = input("\nAlege opțiunea: ")
        
        if opt == "1":
            report_venituri_servicii()
        elif opt == "2":
            report_distributie_regiuni()
        elif opt == "3":
            report_evolutie_vanzari()
        elif opt == "4":
            report_venituri_servicii()
            report_distributie_regiuni()
            report_evolutie_vanzari()
        elif opt == "0":
            print("Ieșire program...")
            break
        else:
            print("Opțiune invalidă!")

if __name__ == "__main__":
    main_menu()