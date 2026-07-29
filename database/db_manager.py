import psycopg2
import os
import pandas as pd
import hashlib
import streamlit as st

def get_connection():
    """クラウドデータベース(Supabase)へ接続するコネクションを取得"""
    return psycopg2.connect(
        host=st.secrets["postgres"]["host"],
        database=st.secrets["postgres"]["database"],
        port=st.secrets["postgres"]["port"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
        sslmode="require"
    )

def hash_password(password):
    """パスワードをSHA-256でハッシュ暗号化"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_db():
    """テーブルを作成・拡張し、初期管理者ユーザーを用意する"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 0. ユーザー管理テーブル（display_name追加）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;")
    except:
        pass
        
    # 初期管理者アカウント (admin / admin123 / 管理者)
    cursor.execute("SELECT id FROM users WHERE username = 'admin';")
    if not cursor.fetchone():
        default_hash = hash_password("admin123")
        cursor.execute("""
            INSERT INTO users (username, password_hash, role, display_name)
            VALUES ('admin', %s, 'admin', '管理者');
        """, (default_hash,))
    else:
        cursor.execute("UPDATE users SET display_name = '管理者' WHERE username = 'admin' AND (display_name IS NULL OR display_name = '');")

    # 1. 定植テーブル（created_by追加）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teichaku (
            id SERIAL PRIMARY KEY,
            variety TEXT, house TEXT, bed TEXT, plant_date TEXT,
            quantity INTEGER, target_size TEXT, memo TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE teichaku ADD COLUMN IF NOT EXISTS created_by TEXT;")
    except:
        pass
    
    # 2. 環境・気象データテーブル（created_by追加）
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
            house_temp REAL, created_by TEXT,
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
        ("house_temp", "REAL"), ("created_by", "TEXT")
    ]
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE kankyo ADD COLUMN IF NOT EXISTS {col_name} {col_type};")
        except:
            pass

    # クリーンアップ
    try:
        cursor.execute("""
            UPDATE kankyo 
            SET water_temp = NULL, ec = NULL, ph = NULL, house_temp = NULL
            WHERE memo IS NULL OR memo NOT LIKE '%手動入力%';
        """)
    except:
        pass

    # 3. 収穫テーブル（created_by追加）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shukaku (
            id SERIAL PRIMARY KEY,
            shukaku_date TEXT, house TEXT, bed TEXT, weight REAL, quantity INTEGER,
            quality TEXT, memo TEXT, variety TEXT, created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for c_name, c_type in [("house", "TEXT"), ("bed", "TEXT"), ("variety", "TEXT"), ("created_by", "TEXT")]:
        try:
            cursor.execute(f"ALTER TABLE shukaku ADD COLUMN IF NOT EXISTS {c_name} {c_type};")
        except:
            pass
    
    conn.commit()
    cursor.close()
    conn.close()

# ----------------------------------------------------
# ユーザー認証・管理用関数
# ----------------------------------------------------
def authenticate_user(username, password):
    """ログイン認証（氏名display_nameも含めて返す）"""
    conn = get_connection()
    cursor = conn.cursor()
    p_hash = hash_password(password)
    cursor.execute("SELECT id, username, role, COALESCE(display_name, username) FROM users WHERE username = %s AND password_hash = %s;", (username, p_hash))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return {"id": user[0], "username": user[1], "role": user[2], "display_name": user[3]}
    return None

def insert_user(username, password, role="user", display_name=""):
    """新規ユーザー追加（氏名保存対応）"""
    conn = get_connection()
    cursor = conn.cursor()
    p_hash = hash_password(password)
    disp = display_name if display_name else username
    try:
        cursor.execute("INSERT INTO users (username, password_hash, role, display_name) VALUES (%s, %s, %s, %s);", (username, p_hash, role, disp))
        conn.commit()
        res = True
    except Exception as e:
        res = False
    cursor.close()
    conn.close()
    return res

def select_all_users():
    """全ユーザー一覧取得"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, COALESCE(display_name, username), created_at FROM users ORDER BY id ASC;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s;", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

# ----------------------------------------------------
# 各種データ操作関数（自動で操作者氏名を記録）
# ----------------------------------------------------
def insert_teichaku(variety, house, bed, plant_date, quantity, target_size, memo, created_by=""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO teichaku (variety, house, bed, plant_date, quantity, target_size, memo, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (variety, house, bed, plant_date, quantity, target_size, memo, created_by))
    conn.commit()
    cursor.close()
    conn.close()

def sync_auto_climate_data(data_dict):
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

def update_house_manual_kankyo(date_str, house_temp, water_temp, ec, ph, user_memo, created_by=""):
    conn = get_connection()
    cursor = conn.cursor()
    memo_str = f"手動入力: {user_memo}" if user_memo else "手動入力"
    cursor.execute("SELECT id FROM kankyo WHERE date = %s", (date_str,))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute("""
            UPDATE kankyo SET
                house_temp = %s, water_temp = %s, ec = %s, ph = %s, memo = %s, created_by = %s
            WHERE date = %s;
        """, (house_temp, water_temp, ec, ph, memo_str, created_by, date_str))
    else:
        cursor.execute("""
            INSERT INTO kankyo (date, house_temp, water_temp, ec, ph, memo, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (date_str, house_temp, water_temp, ec, ph, memo_str, created_by))
        
    conn.commit()
    cursor.close()
    conn.close()

def insert_shukaku_and_clear_teichaku(shukaku_date, house, bed, weight, quality, memo, created_by=""):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT variety FROM teichaku WHERE house = %s AND bed = %s ORDER BY id DESC LIMIT 1;", (house, bed))
    row = cursor.fetchone()
    variety = row[0] if row and row[0] else "サンチュ"
    
    cursor.execute("""
        INSERT INTO shukaku (shukaku_date, house, bed, weight, quantity, quality, memo, variety, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (shukaku_date, house, bed, weight, 0, quality, memo, variety, created_by))
    
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
    cursor.execute("SELECT id, variety, house, bed, plant_date, quantity, target_size, memo, created_at, COALESCE(created_by, '') FROM teichaku ORDER BY id DESC")
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
        SELECT id, shukaku_date, house, bed, weight, quantity, quality, memo, created_at, variety, COALESCE(created_by, '') 
        FROM shukaku 
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows