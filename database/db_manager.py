import psycopg2
import os
import pandas as pd
import streamlit as st

def get_connection():
    """クラウドデータベース(Supabase)へ接続する安全なコネクションを取得"""
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        port=st.secrets["postgres"]["port"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"]
    )

def init_db():
    """テーブルを作成する（クラウド上に自動で作られます）"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 定植テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teichaku (
            id SERIAL PRIMARY KEY,
            variety TEXT, house TEXT, bed TEXT, plant_date TEXT,
            quantity INTEGER, target_size TEXT, memo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. 環境テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kankyo (
            id SERIAL PRIMARY KEY,
            date TEXT, temp REAL, min_temp REAL, max_temp REAL,
            water_temp REAL, dli REAL, ec REAL, ph REAL, memo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 3. 収穫テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shukaku (
            id SERIAL PRIMARY KEY,
            shukaku_date TEXT, weight REAL, quantity INTEGER,
            quality TEXT, memo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

def insert_teichaku(variety, house, bed, plant_date, quantity, target_size, memo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO teichaku (variety, house, bed, plant_date, quantity, target_size, memo)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (variety, house, bed, plant_date, quantity, target_size, memo))
    conn.commit()
    cursor.close()
    conn.close()

def insert_kankyo(date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO kankyo (date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo))
    conn.commit()
    cursor.close()
    conn.close()

def insert_shukaku(shukaku_date, weight, quantity, quality, memo):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO shukaku (shukaku_date, weight, quantity, quality, memo)
        VALUES (%s, %s, %s, %s, %s)
    """, (shukaku_date, weight, quantity, quality, memo))
    conn.commit()
    cursor.close()
    conn.close()

def delete_kankyo_by_date(date_str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kankyo WHERE date = %s", (date_str,))
    conn.commit()
    cursor.close()
    conn.close()

def select_all_teichaku():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM teichaku ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def select_all_kankyo():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM kankyo ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def select_all_shukaku():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shukaku ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def export_all_to_excel(output_filename="サンチュ栽培データ.xlsx"):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM teichaku ORDER BY id DESC")
    df_teichaku = pd.DataFrame(cursor.fetchall(), columns=["id", "variety", "house", "bed", "plant_date", "quantity", "target_size", "memo", "created_at"])
    
    cursor.execute("SELECT * FROM kankyo ORDER BY id DESC")
    df_kankyo = pd.DataFrame(cursor.fetchall(), columns=["id", "date", "temp", "min_temp", "max_temp", "water_temp", "dli", "ec", "ph", "memo", "created_at"])
    
    cursor.execute("SELECT * FROM shukaku ORDER BY id DESC")
    df_shukaku = pd.DataFrame(cursor.fetchall(), columns=["id", "shukaku_date", "weight", "quantity", "quality", "memo", "created_at"])
    
    cursor.close()
    conn.close()
    
    with pd.ExcelWriter(output_filename, engine="openpyxl") as writer:
        df_teichaku.to_excel(writer, sheet_name="定植管理", index=False)
        df_kankyo.to_excel(writer, sheet_name="環境データ", index=False)
        df_shukaku.to_excel(writer, sheet_name="収穫実績", index=False)