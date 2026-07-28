import psycopg2
import os
import pandas as pd
import streamlit as st

def get_connection():
    """クラウドデータベース(Supabase)へ接続するコネクションを取得"""
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        port=st.secrets["postgres"]["port"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"]
    )

def init_db():
    """テーブルを作成・拡張し、過去の偽データを一括完全削除する"""
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
    
    # 2. 環境・気象データテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kankyo (
            id SERIAL PRIMARY KEY,
            date TEXT UNIQUE,
            temp REAL, min_temp REAL, max_temp REAL,
            water_temp REAL, dli REAL, ec REAL, ph REAL, memo TEXT,
            press_land REAL, press_sea REAL,
            humidity_mean REAL, humidity_min REAL,
            wind_speed_mean REAL, wind_speed_max REAL, wind_dir_max TEXT,
            wind_speed_instant REAL, wind_dir_instant TEXT,
            sunshine_hours REAL, precip_total REAL, precip_max_1h REAL, precip_max_10m REAL,
            snow_depth_sum REAL, snow_depth_max REAL,
            house_temp REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    columns = [
        ("press_land", "REAL"), ("press_sea", "REAL"),
        ("humidity_mean", "REAL"), ("humidity_min", "REAL"),
        ("wind_speed_mean", "REAL"), ("wind_speed_max", "REAL"), ("wind_dir_max", "TEXT"),
        ("wind_speed_instant", "REAL"), ("wind_dir_instant", "TEXT"),
        ("sunshine_hours", "REAL"), ("precip_total", "REAL"), ("precip_max_1h", "REAL"), ("precip_max_10m", "REAL"),
        ("snow_depth_sum", "REAL"), ("snow_depth_max", "REAL"),
        ("house_temp", "REAL")
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE kankyo ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
        except:
            pass

    # ★【強力クリーンアップ】手動入力（memo='手動入力'）以外の過去の偽水温・EC・pHデータを強制クリア
    try:
        cursor.execute("""
            UPDATE kankyo 
            SET water_temp = NULL, ec = NULL, ph = NULL, house_temp = NULL
            WHERE memo IS NULL OR memo NOT LIKE '%手動入力%';
        """)
    except:
        pass

    # 3. 収穫テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shukaku (
            id SERIAL PRIMARY KEY,
            shukaku_date TEXT, house TEXT, bed TEXT, weight REAL, quantity INTEGER,
            quality TEXT, memo TEXT, variety TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for c_name, c_type in [("house", "TEXT"), ("bed", "TEXT"), ("variety", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE shukaku ADD COLUMN IF NOT EXISTS {c_name} {c_type};")
        except:
            pass
    
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

def sync_auto_climate_data(data_dict):
    """外気象データのみを更新（水温・ハウス内気温・EC・pHは一切流し込まない）"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM kankyo WHERE date = %s", (data_dict["date"],))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute("""
            UPDATE kankyo SET
                temp = %(temp)s, min_temp = %(min_temp)s, max_temp = %(max_temp)s,
                dli = %(dli)s, press_land = %(press_land)s, press_sea = %(press_sea)s,
                humidity_mean = %(humidity_mean)s, humidity_min = %(humidity_min)s,
                wind_speed_mean = %(wind_speed_mean)s, wind_speed_max = %(wind_speed_max)s,
                wind_dir_max = %(wind_dir_max)s, wind_speed_instant = %(wind_speed_instant)s,
                wind_dir_instant = %(wind_dir_instant)s, sunshine_hours = %(sunshine_hours)s,
                precip_total = %(precip_total)s, precip_max_1h = %(precip_max_1h)s,
                precip_max_10m = %(precip_max_10m)s, snow_depth_sum = %(snow_depth_sum)s,
                snow_depth_max = %(snow_depth_max)s
            WHERE date = %(date)s;
        """, data_dict)
    else:
        cursor.execute("""
            INSERT INTO kankyo (
                date, temp, min_temp, max_temp, dli, memo,
                press_land, press_sea, humidity_mean, humidity_min,
                wind_speed_mean, wind_speed_max, wind_dir_max, wind_speed_instant, wind_dir_instant,
                sunshine_hours, precip_total, precip_max_1h, precip_max_10m, snow_depth_sum, snow_depth_max
            ) VALUES (
                %(date)s, %(temp)s, %(min_temp)s, %(max_temp)s, %(dli)s, '気象庁自動同期',
                %(press_land)s, %(press_sea)s, %(humidity_mean)s, %(humidity_min)s,
                %(wind_speed_mean)s, %(wind_speed_max)s, %(wind_dir_max)s, %(wind_speed_instant)s, %(wind_dir_instant)s,
                %(sunshine_hours)s, %(precip_total)s, %(precip_max_1h)s, %(precip_max_10m)s, %(snow_depth_sum)s, %(snow_depth_max)s
            );
        """, data_dict)
        
    conn.commit()
    cursor.close()
    conn.close()

def update_house_manual_kankyo(date_str, house_temp, water_temp, ec, ph, user_memo):
    """手動入力のハウス個別データを安全に保存（memo='手動入力' フラグを付与）"""
    conn = get_connection()
    cursor = conn.cursor()
    
    memo_str = f"手動入力: {user_memo}" if user_memo else "手動入力"
    
    cursor.execute("SELECT id FROM kankyo WHERE date = %s", (date_str,))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute("""
            UPDATE kankyo SET
                house_temp = %s, water_temp = %s, ec = %s, ph = %s, memo = %s
            WHERE date = %s;
        """, (house_temp, water_temp, ec, ph, memo_str, date_str))
    else:
        cursor.execute("""
            INSERT INTO kankyo (date, house_temp, water_temp, ec, ph, memo)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (date_str, house_temp, water_temp, ec, ph, memo_str))
        
    conn.commit()
    cursor.close()
    conn.close()

def insert_shukaku_and_clear_teichaku(shukaku_date, house, bed, weight, quality, memo):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT variety FROM teichaku WHERE house = %s AND bed = %s ORDER BY id DESC LIMIT 1;", (house, bed))
    row = cursor.fetchone()
    variety = row[0] if row and row[0] else "サンチュ"
    
    cursor.execute("""
        INSERT INTO shukaku (shukaku_date, house, bed, weight, quantity, quality, memo, variety)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (shukaku_date, house, bed, weight, 0, quality, memo, variety))
    
    cursor.execute("""
        DELETE FROM teichaku 
        WHERE house = %s AND bed = %s;
    """, (house, bed))
    
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
    cursor.execute("SELECT * FROM kankyo ORDER BY date DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def select_all_shukaku():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, shukaku_date, house, bed, weight, quantity, quality, memo, created_at, variety 
        FROM shukaku 
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
