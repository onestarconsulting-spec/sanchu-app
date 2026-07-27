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
    """テーブルを作成・拡張する"""
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
    
    # 2. 環境・気象データテーブル（気象庁全項目対応）
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 既存テーブルへのカラム安全追加（Supabaseの自動拡張）
    columns = [
        ("press_land", "REAL"), ("press_sea", "REAL"),
        ("humidity_mean", "REAL"), ("humidity_min", "REAL"),
        ("wind_speed_mean", "REAL"), ("wind_speed_max", "REAL"), ("wind_dir_max", "TEXT"),
        ("wind_speed_instant", "REAL"), ("wind_dir_instant", "TEXT"),
        ("sunshine_hours", "REAL"), ("precip_total", "REAL"), ("precip_max_1h", "REAL"), ("precip_max_10m", "REAL"),
        ("snow_depth_sum", "REAL"), ("snow_depth_max", "REAL")
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE kankyo ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
        except:
            pass

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

def insert_kankyo_full(data_dict):
    """気象庁データ含めた全項目の一括保存・更新"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO kankyo (
            date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo,
            press_land, press_sea, humidity_mean, humidity_min,
            wind_speed_mean, wind_speed_max, wind_dir_max, wind_speed_instant, wind_dir_instant,
            sunshine_hours, precip_total, precip_max_1h, precip_max_10m, snow_depth_sum, snow_depth_max
        ) VALUES (
            %(date)s, %(temp)s, %(min_temp)s, %(max_temp)s, %(water_temp)s, %(dli)s, %(ec)s, %(ph)s, %(memo)s,
            %(press_land)s, %(press_sea)s, %(humidity_mean)s, %(humidity_min)s,
            %(wind_speed_mean)s, %(wind_speed_max)s, %(wind_dir_max)s, %(wind_speed_instant)s, %(wind_dir_instant)s,
            %(sunshine_hours)s, %(precip_total)s, %(precip_max_1h)s, %(precip_max_10m)s, %(snow_depth_sum)s, %(snow_depth_max)s
        )
        ON CONFLICT (date) DO UPDATE SET
            temp = EXCLUDED.temp, min_temp = EXCLUDED.min_temp, max_temp = EXCLUDED.max_temp,
            dli = EXCLUDED.dli, press_land = EXCLUDED.press_land, press_sea = EXCLUDED.press_sea,
            humidity_mean = EXCLUDED.humidity_mean, humidity_min = EXCLUDED.humidity_min,
            wind_speed_mean = EXCLUDED.wind_speed_mean, wind_speed_max = EXCLUDED.wind_speed_max,
            wind_dir_max = EXCLUDED.wind_dir_max, wind_speed_instant = EXCLUDED.wind_speed_instant,
            wind_dir_instant = EXCLUDED.wind_dir_instant, sunshine_hours = EXCLUDED.sunshine_hours,
            precip_total = EXCLUDED.precip_total, precip_max_1h = EXCLUDED.precip_max_1h,
            precip_max_10m = EXCLUDED.precip_max_10m, snow_depth_sum = EXCLUDED.snow_depth_sum,
            snow_depth_max = EXCLUDED.snow_depth_max;
    """, data_dict)
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
    cursor.execute("SELECT * FROM shukaku ORDER BY id DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
