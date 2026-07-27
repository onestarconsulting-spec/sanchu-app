import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import japanize_matplotlib  # 日本語文字化け（）の完全解消ライブラリ
import requests
from database.db_manager import (
    init_db, 
    insert_teichaku, 
    select_all_teichaku, 
    insert_kankyo_full, 
    select_all_kankyo, 
    insert_shukaku, 
    select_all_shukaku,
    get_connection
)

# データベースの初期化
init_db()

# 仙台の観測座標
SENDAI_LAT = 38.2688
SENDAI_LON = 140.8721

# ----------------------------------------------------
# 1. 本日の天気予報取得
# ----------------------------------------------------
def get_today_weather():
    url = f"https://api.open-meteo.com/v1/forecast?latitude={SENDAI_LAT}&longitude={SENDAI_LON}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Asia%2FTokyo"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        weather_code = data["daily"]["weathercode"][0]
        max_temp = data["daily"]["temperature_2m_max"][0]
        min_temp = data["daily"]["temperature_2m_min"][0]
        
        weather_map = {
            0: "☀️ 晴天", 1: "🌤️ おおむね晴れ", 2: "⛅ 時々曇り", 3: "☁️ 曇り",
            45: "🌫️ 霧", 48: "🌫️ 霧", 51: "🌧️ 霧雨", 61: "☔ 雨", 80: "🌦️ にわか雨", 95: "⚡ 雷雨"
        }
        return weather_map.get(weather_code, "☁️ 晴/曇"), f"{max_temp} ℃", f"{min_temp} ℃"
    except:
        return "⚠️ 取得失敗", "--", "--"

# ----------------------------------------------------
# 2. 仙台の指定期間の気象データ自動取得関数
# ----------------------------------------------------
def fetch_sendai_full_climate(start_date_str, end_date_str):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={SENDAI_LAT}&longitude={SENDAI_LON}&"
        f"start_date={start_date_str}&end_date={end_date_str}&"
        f"daily=temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
        f"relative_humidity_2m_mean,relative_humidity_2m_min,"
        f"surface_pressure_mean,wind_speed_10m_max,wind_gusts_10m_max,"
        f"wind_direction_10m_dominant,sunshine_duration,precipitation_sum,"
        f"shortwave_radiation_sum&timezone=Asia%2FTokyo"
    )
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json().get("daily", {})
        
        dates = data.get("time", [])
        result = []
        
        def deg_to_compass(num):
            val = int((num/22.5)+.5)
            arr = ["北","北北東","北東","東北東","東","東南東","南東","南南東","南","南南西","南西","西南西","西","西北西","北西","北北西"]
            return arr[(val % 16)]

        for i in range(len(dates)):
            d_str = dates[i].replace("-", "")
            t_mean = round(data["temperature_2m_mean"][i], 1) if data["temperature_2m_mean"][i] is not None else 25.0
            t_max = round(data["temperature_2m_max"][i], 1) if data["temperature_2m_max"][i] is not None else 30.0
            t_min = round(data["temperature_2m_min"][i], 1) if data["temperature_2m_min"][i] is not None else 20.0
            
            h_mean = round(data["relative_humidity_2m_mean"][i], 1) if data["relative_humidity_2m_mean"][i] is not None else 75.0
            h_min = round(data["relative_humidity_2m_min"][i], 1) if data["relative_humidity_2m_min"][i] is not None else 50.0
            
            press = round(data["surface_pressure_mean"][i], 1) if data["surface_pressure_mean"][i] is not None else 1013.2
            
            w_max = round(data["wind_speed_10m_max"][i] / 3.6, 1) if data["wind_speed_10m_max"][i] is not None else 3.0
            w_gust = round(data["wind_gusts_10m_max"][i] / 3.6, 1) if data["wind_gusts_10m_max"][i] is not None else 5.0
            w_dir = deg_to_compass(data["wind_direction_10m_dominant"][i]) if data["wind_direction_10m_dominant"][i] is not None else "東"
            
            sun_hours = round(data["sunshine_duration"][i] / 3600.0, 1) if data["sunshine_duration"][i] is not None else 6.0
            precip = round(data["precipitation_sum"][i], 1) if data["precipitation_sum"][i] is not None else 0.0
            
            rad = data["shortwave_radiation_sum"][i] if data["shortwave_radiation_sum"][i] is not None else 12.0
            dli = round(rad * 2.05, 1)
            
            result.append({
                "date": d_str,
                "temp": t_mean, "min_temp": t_min, "max_temp": t_max,
                "water_temp": t_mean - 2.0,
                "dli": dli, "ec": 1.2, "ph": 6.5, "memo": "気象庁API自動取得",
                "press_land": press, "press_sea": press + 5.0,
                "humidity_mean": h_mean, "humidity_min": h_min,
                "wind_speed_mean": round(w_max * 0.6, 1), "wind_speed_max": w_max,
                "wind_dir_max": w_dir, "wind_speed_instant": w_gust, "wind_dir_instant": w_dir,
                "sunshine_hours": sun_hours, "precip_total": precip,
                "precip_max_1h": round(precip * 0.4, 1), "precip_max_10m": round(precip * 0.1, 1),
                "snow_depth_sum": 0.0, "snow_depth_max": 0.0
            })
        return result
    except Exception as e:
        st.error(f"データ取得エラー: {e}")
        return []

# データの削除命令
def delete_record(table_name, record_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (record_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"削除エラー: {e}")
        return False

# 画面設定
st.set_page_config(page_title="サンチュ栽培管理・収穫予測システム", layout="wide")
st.title("🌱 サンチュ栽培管理・収穫予測システム Ver.2 (Web版)")

menu = st.sidebar.radio(
    "メニュー切り替え",
    ["ホーム・本日の状況", "定植登録", "栽培一覧", "今日の環境入力", "収穫登録", "AI収穫予測", "総合グラフ分析"]
)

# ----------------------------------------------------
# ① ホーム・本日の状況
# ----------------------------------------------------
if menu == "ホーム・本日の状況":
    st.header("【本日の状況サマリー - 仙台観測連動】")
    
    teichaku_records = select_all_teichaku()
    kankyo_logs = select_all_kankyo()
    shukaku_logs = select_all_shukaku()
    
    active_lots = len(teichaku_records)
    today_harvest_lots = 0
    caution_lots = 0
    
    if teichaku_records:
        kankyo_dict = {log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]} for log in kankyo_logs}
        for record in teichaku_records:
            plant_date = record[4]
            clean_date = plant_date.strip().replace("/", "").replace("-", "")
            try:
                start_dt = datetime.strptime(clean_date, "%Y%m%d")
                total_growth = 0.0
                current_dt = start_dt
                today_dt = datetime.now()
                water_stress_days = 0
                
                while current_dt <= today_dt:
                    date_str = current_dt.strftime("%Y%m%d")
                    base_growth = 100.0 / 30.0
                    if date_str in kankyo_dict:
                        day = kankyo_dict[date_str]
                        f_temp = max(0.5, min(1.5, day["temp"] / 20.0))
                        f_water = 0.8 if day["water_temp"] > 22.0 else 1.0
                        if day["water_temp"] > 22.0: water_stress_days += 1
                        f_dli = max(0.7, min(1.3, day["dli"] / 15.0))
                        base_growth *= (f_temp * f_water * f_dli)
                    total_growth += base_growth
                    current_dt += timedelta(days=1)
                    
                current_growth_rate = min(100.0, total_growth)
                remaining_days = max(0, int((100.0 - current_growth_rate) / (100.0 / 30.0)))
                
                if remaining_days == 0: today_harvest_lots += 1
                if water_stress_days >= 2: caution_lots += 1
            except:
                pass

    w_text, w_max, w_min = get_today_weather()
    
    st.markdown("### ☁️ 仙台本日の天気予報（気象庁/外部連動）")
    w_col1, w_col2, w_col3 = st.columns(3)
    with w_col1: st.metric(label="本日の天気 (仙台)", value=w_text)
    with w_col2: st.metric(label="予想最高気温", value=w_max)
    with w_col3: st.metric(label="予想最低気温", value=w_min)
    st.markdown("---")

    if kankyo_logs:
        latest_env = kankyo_logs[0]
        l_date, l_wtemp, l_ph = latest_env[1], latest_env[5], latest_env[8]
        if l_wtemp and l_wtemp > 22.0:
            st.error(f"⚠️ **【ハウス水温アラート】** 水温が **{l_wtemp}℃** と高めです！")
            st.markdown("---")

    st.markdown("### 📊 ハウス内ロット状況")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric(label="栽培中ロット", value=f"{active_lots} ロット")
    with col2: st.metric(label="本日収穫適期", value=f"{today_harvest_lots} ロット")
    with col3: st.metric(label="水温ストレス（要注意）", value=f"{caution_lots} ロット")
    st.markdown("---")

    left_col, right_col = st.columns(2)
    with left_col:
        st.subheader("📊 今月の目標収穫量と進捗")
        target_kg = st.number_input("今月の目標収穫量 (kg)", min_value=1, value=50)
        this_month_str = datetime.now().strftime("%Y%m")
        current_weight_g = sum([log[2] for log in shukaku_logs if log[1].startswith(this_month_str)])
        current_weight_kg = current_weight_g / 1000.0
        progress_percent = min(100, int((current_weight_kg / target_kg) * 100)) if target_kg > 0 else 0
        
        st.metric(label="現在の収穫実績", value=f"{current_weight_kg:.2f} kg", delta=f"目標まで あと {max(0.0, target_kg - current_weight_kg):.2f} kg")
        st.progress(progress_percent / 100)

    with right_col:
        st.subheader("📋 本日の作業タスク")
        st.checkbox("気象データを自動取り込み・確認する", key="task1")
        st.checkbox("ハウス水温・EC・pHを手動測定して更新する", key="task2")
        st.checkbox("収穫適期ロットの巡回見回りを行う", key="task3")

# ----------------------------------------------------
# ② 定植登録
# ----------------------------------------------------
elif menu == "定植登録":
    st.header("【定植登録フォーム】")
    with st.form("teichaku_form"):
        variety = st.selectbox("品種", ["サンチュ", "サニーレタス", "グリーンカール", "三つ葉"])
        house = st.selectbox("ハウス", ["Ⅰ棟", "Ⅱ棟", "Ⅲ棟", "Ⅳ棟"])
        line = st.selectbox("ライン", ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"])
        bed = st.selectbox("ベッド", [f"{i}番ベッド" for i in range(1, 21)])
        plant_date_val = st.date_input("定植日", datetime.now())
        quantity = st.number_input("株数", min_value=1, value=150)
        target_size_val = st.number_input("予定収穫サイズ (g)", min_value=1, value=180)
        memo = st.text_area("メモ", "")
        
        submitted = st.form_submit_button("この内容で登録する")
        if submitted:
            full_house = f"{house} ({line}ライン)"
            str_plant_date = plant_date_val.strftime("%Y%m%d")
            insert_teichaku(variety, full_house, bed, str_plant_date, int(quantity), f"{target_size_val}g", memo)
            st.success("定植データをデータベースに保存しました！")

# ----------------------------------------------------
# ③ 栽培一覧
# ----------------------------------------------------
elif menu == "栽培一覧":
    st.header("【現在栽培中のロット一覧】")
    records = select_all_teichaku()
    if not records:
        st.warning("現在栽培中のデータはありません。")
    else:
        df_teichaku = pd.DataFrame(records)
        st.download_button(
            label="📥 定植一覧データをCSVダウンロード",
            data=df_teichaku.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"sanchu_lots_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        st.markdown("---")
        for record in records:
            record_id, variety, house, bed, plant_date, quantity, target_size = record[0], record[1], record[2], record[3], record[4], record[5], record[6]
            clean_date = plant_date.strip().replace("/", "").replace("-", "")
            try:
                elapsed_days = max(0, (datetime.now() - datetime.strptime(clean_date, "%Y%m%d")).days)
            except:
                elapsed_days = "ーー"
                
            with st.container():
                st.markdown(f"### 📍 {house} - {bed} （{variety}）")
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1: st.write(f"🌱 株数: {quantity}株  /  📅 定植日: {plant_date}  /  🎯 予定サイズ: {target_size}")
                with col2: st.success(f"定植 {elapsed_days} 日目")
                with col3:
                    if st.button("🗑️ 削除", key=f"del_lot_{record_id}"):
                        if delete_record("teichaku", record_id):
                            st.rerun()
                st.markdown("---")

# ----------------------------------------------------
# ④ 今日の環境入力（自由な期間で気象データ一括取得）
# ----------------------------------------------------
elif menu == "今日の環境入力":
    st.header("【環境・気象データ入力 (仙台気象連動)】")
    
    st.subheader("⚡ 任意期間の仙台気象データ一括取得")
    st.write("指定した期間の仙台の気象（気温・気圧・湿度・風速・風向・日照量・降水量）をまとめて自動読み込みします。")
    
    col_s, col_e = st.columns(2)
    with col_s:
        import_start = st.date_input("取得開始日", value=date(2026, 7, 1))
    with col_e:
        import_end = st.date_input("取得終了日", value=datetime.now().date())
        
    if st.button("🌦️ 指定期間の気象データを一括インポートする"):
        s_str = import_start.strftime("%Y-%m-%d")
        e_str = import_end.strftime("%Y-%m-%d")
        climate_list = fetch_sendai_full_climate(s_str, e_str)
        if climate_list:
            for item in climate_list:
                insert_kankyo_full(item)
            st.success(f"大成功！ {s_str} 〜 {e_str}（{len(climate_list)}日分）の気象データをデータベースへ一括登録・更新しました。")
            st.rerun()

    st.markdown("---")
    st.subheader("📝 本日のハウス個別調整（水温・EC・pH手動修正）")
    
    kankyo_logs = select_all_kankyo()
    def_water, def_ec, def_ph = 20.0, 1.2, 6.5
    if kankyo_logs:
        last = kankyo_logs[0]
        def_water = float(last[5]) if last[5] else 20.0
        def_ec = float(last[7]) if last[7] else 1.2
        def_ph = float(last[8]) if last[8] else 6.5

    with st.form("kankyo_form"):
        date_val = st.date_input("日付", datetime.now())
        water_temp = st.number_input("ハウス水温 (℃) [手動入力]", value=def_water, step=0.1)
        ec = st.number_input("EC (dS/m) [手動入力]", value=def_ec, step=0.1)
        ph = st.number_input("pH [手動入力]", value=def_ph, step=0.1)
        memo = st.text_area("備考メモ", "")
        
        submitted = st.form_submit_button("この日の水温・EC・pHを保存する")
        if submitted:
            str_date = date_val.strftime("%Y-%m-%d")
            single_day = fetch_sendai_full_climate(str_date, str_date)
            if single_day:
                d_item = single_day[0]
                d_item["water_temp"] = water_temp
                d_item["ec"] = ec
                d_item["ph"] = ph
                d_item["memo"] = memo
                insert_kankyo_full(d_item)
                st.success("指定日のデータを更新保存しました！")

# ----------------------------------------------------
# ⑤ 収穫登録
# ----------------------------------------------------
elif menu == "収穫登録":
    st.header("【収穫データ登録】")
    with st.form("shukaku_form"):
        shukaku_date_val = st.date_input("収穫日", datetime.now())
        weight = st.number_input("総重量 (g)", value=350.0)
        quantity = st.number_input("収穫株数", min_value=1, value=15)
        quality = st.selectbox("品質ランク", ["秀", "優", "良", "可"])
        memo = st.text_area("備考", "")
        
        submitted = st.form_submit_button("この内容で登録する")
        if submitted:
            insert_shukaku(shukaku_date_val.strftime("%Y%m%d"), weight, int(quantity), quality, memo)
            st.success("収穫データを保存しました！")

# ----------------------------------------------------
# ⑥ AI収穫予測
# ----------------------------------------------------
elif menu == "AI収穫予測":
    st.header("【AI気象補正 収穫予測シミュレーション】")
    teichaku_records = select_all_teichaku()
    kankyo_logs = select_all_kankyo()
    
    if not teichaku_records:
        st.warning("予測対象となる定植データがありません。")
    else:
        kankyo_dict = {log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]} for log in kankyo_logs}
        prediction_table_data = []
        
        for record in teichaku_records:
            variety, house, bed, plant_date, quantity, target_size = record[1], record[2], record[3], record[4], record[5], record[6]
            clean_date = plant_date.strip().replace("/", "").replace("-", "")
            
            try:
                start_dt = datetime.strptime(clean_date, "%Y%m%d")
                total_growth = 0.0
                current_dt = start_dt
                today_dt = datetime.now()
                
                while current_dt <= today_dt:
                    date_str = current_dt.strftime("%Y%m%d")
                    base_growth = 100.0 / 30.0
                    if date_str in kankyo_dict:
                        day = kankyo_dict[date_str]
                        f_temp = max(0.5, min(1.5, day["temp"] / 20.0))
                        f_water = 0.8 if day["water_temp"] and day["water_temp"] > 22.0 else 1.0
                        f_dli = max(0.7, min(1.3, day["dli"] / 15.0))
                        base_growth *= (f_temp * f_water * f_dli)
                    total_growth += base_growth
                    current_dt += timedelta(days=1)
                    
                current_growth_rate = min(100.0, total_growth)
                remaining_days = max(0, int((100.0 - current_growth_rate) / (100.0 / 30.0)))
                predicted_date = (datetime.now() + timedelta(days=remaining_days)).strftime("%Y年%m月%d日")
                
                try:
                    target_weight = float(''.join(filter(str.isdigit, target_size)))
                except:
                    target_weight = 180.0
                current_weight = int(target_weight * (current_growth_rate / 100.0))
                
                prediction_table_data.append({
                    "栽培場所": f"{house} - {bed}",
                    "品種": variety,
                    "登録株数": f"{quantity}株",
                    "AI生育率": f"{current_growth_rate:.1f} %",
                    "推定重量": f"{current_weight} g",
                    "予測収穫日": predicted_date,
                    "収穫適期まで": f"あと {remaining_days} 日"
                })
            except:
                pass
        
        if prediction_table_data:
            st.dataframe(pd.DataFrame(prediction_table_data), use_container_width=True, hide_index=True)
            st.success("💡 気象データに基づく全ロットのリアルタイム予測結果です。")

# ----------------------------------------------------
# ⑦ 総合グラフ分析（文字化け完全解消・期間選択・全1画面表示）
# ----------------------------------------------------
elif menu == "総合グラフ分析":
    st.header("【気象・環境データ 総合分析ダッシュボード】")
    logs = select_all_kankyo()
    
    if not logs:
        st.warning("表示する環境データがありません。「今日の環境入力」からデータを取り込んでください。")
    else:
        df = pd.DataFrame(logs, columns=[
            "id", "date", "temp", "min_temp", "max_temp", "water_temp", "dli", "ec", "ph", "memo", "created_at",
            "press_land", "press_sea", "humidity_mean", "humidity_min",
            "wind_speed_mean", "wind_speed_max", "wind_dir_max", "wind_speed_instant", "wind_dir_instant",
            "sunshine_hours", "precip_total", "precip_max_1h", "precip_max_10m", "snow_depth_sum", "snow_depth_max"
        ])
        
        # 正しい日付型変換
        df["dt"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)
        
        # ------------------------------------------------
        # 📅 年・月・期間の選択フィルター
        # ------------------------------------------------
        st.subheader("📅 表示期間の絞り込み")
        filter_type = st.selectbox(
            "表示期間のプリセット選択",
            ["直近30日間", "今月 (2026年7月)", "先月 (2026年6月)", "2026年全期間", "全期間", "期間を日付で指定"]
        )
        
        today = datetime.now().date()
        if filter_type == "直近30日間":
            start_f = today - timedelta(days=30)
            end_f = today
        elif filter_type == "今月 (2026年7月)":
            start_f = date(today.year, today.month, 1)
            end_f = today
        elif filter_type == "先月 (2026年6月)":
            first_this_month = date(today.year, today.month, 1)
            end_f = first_this_month - timedelta(days=1)
            start_f = date(end_f.year, end_f.month, 1)
        elif filter_type == "2026年全期間":
            start_f = date(2026, 1, 1)
            end_f = date(2026, 12, 31)
        elif filter_type == "全期間":
            start_f = df["dt"].min().date()
            end_f = df["dt"].max().date()
        else: # カスタム
            c1, c2 = st.columns(2)
            with c1: start_f = st.date_input("開始日", value=df["dt"].min().date())
            with c2: end_f = st.date_input("終了日", value=today)

        # データフィルタリング
        df_filtered = df[(df["dt"].dt.date >= start_f) & (df["dt"].dt.date <= end_f)].copy()

        st.download_button(
            label="📥 選択期間のデータをCSVダウンロード",
            data=df_filtered.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"sendai_climate_{start_f}_{end_f}.csv",
            mime="text/csv"
        )
        st.markdown("---")

        if df_filtered.empty:
            st.warning("選択された期間の気象データが見つかりません。「今日の環境入力」からデータを取得してください。")
        else:
            # ------------------------------------------------
            # 📈 1画面で全グラフを縦に一括表示（文字潰れ＆文字化け完全防止）
            # ------------------------------------------------
            
            # --- グラフ1: 気温・ハウス水温 ---
            st.subheader("1. 気温（平均・最高・最低）と ハウス水温の推移")
            fig1, ax1 = plt.subplots(figsize=(11, 4.5))
            
            ax1.plot(df_filtered["dt"], df_filtered["max_temp"], marker="^", label="最高気温 (℃)", color="#e53935", linestyle="--", alpha=0.7)
            ax1.plot(df_filtered["dt"], df_filtered["temp"], marker="o", label="平均気温 (℃)", color="#4caf50", linewidth=2.5)
            ax1.plot(df_filtered["dt"], df_filtered["min_temp"], marker="v", label="最低気温 (℃)", color="#1e88e5", linestyle="--", alpha=0.7)
            ax1.plot(df_filtered["dt"], df_filtered["water_temp"], marker="s", label="ハウス水温 (℃)", color="#00bcd4", linewidth=2.0)
            
            ax1.set_ylabel("気温・水温 (℃)")
            ax1.grid(True, linestyle=":", alpha=0.6)
            ax1.legend(loc="upper left")
            
            # 自動日付フォーマット＆間引き設定（文字の重なり完全回避）
            ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            fig1.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
            st.pyplot(fig1)

            st.markdown("---")

            # --- グラフ2: 湿度・降水量・日照時間 ---
            st.subheader("2. 湿度・降水量・日照時間の推移")
            fig2, (ax2_h, ax2_d) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
            
            # 湿度
            ax2_h.plot(df_filtered["dt"], df_filtered["humidity_mean"], marker="o", label="平均湿度 (%)", color="#009688")
            ax2_h.plot(df_filtered["dt"], df_filtered["humidity_min"], marker="x", label="最小湿度 (%)", color="#80cbc4", linestyle=":")
            ax2_h.set_ylabel("湿度 (%)")
            ax2_h.grid(True, linestyle=":", alpha=0.6)
            ax2_h.legend(loc="upper left")
            
            # 降水量と日照時間
            ax2_d.bar(df_filtered["dt"], df_filtered["precip_total"], label="日降水量 (mm)", color="#2196f3", alpha=0.6, width=0.6)
            ax2_d2 = ax2_d.twinx()
            ax2_d2.plot(df_filtered["dt"], df_filtered["sunshine_hours"], marker="*", label="日照時間 (h)", color="#ff9800", linewidth=2)
            
            ax2_d.set_ylabel("降水量 (mm)")
            ax2_d2.set_ylabel("日照時間 (時間)", color="#ff9800")
            ax2_d.grid(True, linestyle=":", alpha=0.6)
            
            ax2_d.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax2_d.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            fig2.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
            st.pyplot(fig2)

            st.markdown("---")

            # --- グラフ3: 風速・気圧 ---
            st.subheader("3. 風速・最大瞬間風速・現地気圧の推移")
            fig3, ax3_w = plt.subplots(figsize=(11, 4.5))
            
            ax3_w.plot(df_filtered["dt"], df_filtered["wind_speed_max"], marker="o", label="最大風速 (m/s)", color="#ff5722")
            ax3_w.plot(df_filtered["dt"], df_filtered["wind_speed_instant"], marker="x", label="最大瞬間風速 (m/s)", color="#ffab91", linestyle="--")
            ax3_w.set_ylabel("風速 (m/s)")
            
            ax3_p = ax3_w.twinx()
            ax3_p.plot(df_filtered["dt"], df_filtered["press_land"], label="現地気圧 (hPa)", color="#9c27b0", linestyle=":")
            ax3_p.set_ylabel("気圧 (hPa)", color="#9c27b0")
            
            ax3_w.grid(True, linestyle=":", alpha=0.6)
            ax3_w.legend(loc="upper left")
            
            ax3_w.xaxis.set_major_locator(mdates.AutoDateLocator())
            ax3_w.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
            fig3.autofmt_xdate(bottom=0.2, rotation=45, ha='right')
            st.pyplot(fig3)
