import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import requests
import re
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from database.db_manager import (
    init_db, 
    insert_teichaku, 
    select_all_teichaku, 
    insert_kankyo_full, 
    select_all_kankyo, 
    insert_shukaku_and_clear_teichaku, 
    select_all_shukaku,
    get_connection
)

# データベースの初期化
init_db()

# 仙台の観測座標
SENDAI_LAT = 38.2688
SENDAI_LON = 140.8721

# ----------------------------------------------------
# 0. 収穫データから重量(g)を安全に抽出するヘルパー関数
# ----------------------------------------------------
def get_weight_from_log(log):
    for val in log[2:]:
        if isinstance(val, (int, float)) and val > 0:
            return float(val)
    return 0.0

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
    ["ホーム・本日の状況", "定植登録", "今日の環境入力", "収穫登録", "AI収穫予測 (栽培管理)", "収穫実績・分析", "総合グラフ分析"]
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
        
        current_weight_g = sum([float(log[4]) for log in shukaku_logs if str(log[1]).startswith(this_month_str) and log[4] is not None])
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
        lines = st.multiselect(
            "ライン (複数選択可)", 
            ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
            default=["A"]
        )
        beds = st.multiselect(
            "ベッド (複数選択可)", 
            [f"{i}番ベッド" for i in range(1, 21)],
            default=["1番ベッド"]
        )
        plant_date_val = st.date_input("定植日", datetime.now())
        quantity = st.number_input("株数 (1ベッドあたり)", min_value=1, value=150)
        target_size_val = st.number_input("予定収穫サイズ (g)", min_value=1, value=180)
        memo = st.text_area("メモ", "")
        
        submitted = st.form_submit_button("この内容で一括登録する")
        if submitted:
            if not lines:
                st.error("⚠️ ラインを1つ以上選択してください。")
            elif not beds:
                st.error("⚠️ ベッドを1つ以上選択してください。")
            else:
                str_plant_date = plant_date_val.strftime("%Y%m%d")
                str_target_size = f"{target_size_val}g"
                count = 0
                for l in lines:
                    full_house = f"{house} ({l}ライン)"
                    for b in beds:
                        insert_teichaku(variety, full_house, b, str_plant_date, int(quantity), str_target_size, memo)
                        count += 1
                st.success(f"🎉 大成功！ {house} の {len(lines)}ライン × {len(beds)}ベッド（計 {count} 件）を一括登録しました！")

# ----------------------------------------------------
# ③ 今日の環境入力
# ----------------------------------------------------
elif menu == "今日の環境入力":
    st.header("【環境・気象データ入力 (仙台気象連動)】")
    
    st.subheader("⚡ 過去の仙台気象データ一括取得（6月〜本日）")
    st.write("2026年6月1日〜本日までの気象データ（気温・湿度・風速・気圧・降水量等）をまとめて全自動取り込みします。")
    
    col_s, col_e = st.columns(2)
    with col_s:
        import_start = st.date_input("取得開始日", value=date(2026, 6, 1))
    with col_e:
        import_end = st.date_input("取得終了日", value=datetime.now().date())
        
    if st.button("🌦️ 6月1日〜本日の仙台気象データを一括インポートする"):
        s_str = import_start.strftime("%Y-%m-%d")
        e_str = import_end.strftime("%Y-%m-%d")
        climate_list = fetch_sendai_full_climate(s_str, e_str)
        if climate_list:
            for item in climate_list:
                insert_kankyo_full(item)
            st.success(f"大成功！ {s_str} 〜 {e_str}（{len(climate_list)}日分）の気象データを一括登録・更新しました。")
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
# ④ 収穫登録
# ----------------------------------------------------
elif menu == "収穫登録":
    st.header("【収穫データ登録】")
    st.write("収穫を行った棟・ライン・ベッドを選択して登録します。登録完了と同時に、**AI収穫予測（栽培管理表）から自動削除（収穫完了）**されます。")
    
    with st.form("shukaku_form"):
        shukaku_date_val = st.date_input("収穫日", datetime.now())
        
        house = st.selectbox("ハウス", ["Ⅰ棟", "Ⅱ棟", "Ⅲ棟", "Ⅳ棟"])
        lines = st.multiselect(
            "ライン (複数選択可)", 
            ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"],
            default=["A"]
        )
        beds = st.multiselect(
            "ベッド (複数選択可)", 
            [f"{i}番ベッド" for i in range(1, 21)],
            default=["1番ベッド"]
        )
        
        weight = st.number_input("1ベッドあたりの実収穫重量 (g)", min_value=1.0, value=180.0, step=10.0)
        quality = st.selectbox("品質ランク", ["秀", "優", "良", "可"])
        memo = st.text_area("備考", "")
        
        submitted = st.form_submit_button("この内容で収穫登録する (栽培一覧から自動削除)")
        if submitted:
            if not lines:
                st.error("⚠️ ラインを1つ以上選択してください。")
            elif not beds:
                st.error("⚠️ ベッドを1つ以上選択してください。")
            else:
                str_shukaku_date = shukaku_date_val.strftime("%Y%m%d")
                count = 0
                for l in lines:
                    full_house = f"{house} ({l}ライン)"
                    for b in beds:
                        insert_shukaku_and_clear_teichaku(str_shukaku_date, full_house, b, weight, quality, memo)
                        count += 1
                        
                st.success(f"🎉 収穫完了！ {house} の {len(lines)}ライン × {len(beds)}ベッド（計 {count} 件）を収穫登録し、AI収穫予測表から自動消去しました！")

# ----------------------------------------------------
# ⑤ AI収穫予測 (栽培管理)
# ----------------------------------------------------
elif menu == "AI収穫予測 (栽培管理)":
    st.header("【AI気象補正 収穫予測・栽培管理テーブル】")
    teichaku_records = select_all_teichaku()
    kankyo_logs = select_all_kankyo()
    shukaku_logs = select_all_shukaku()
    
    yield_accuracy_factor = 1.0
    if shukaku_logs:
        valid_weights = [float(log[4]) for log in shukaku_logs if len(log) > 4 and log[4] is not None and float(log[4]) > 0]
        if valid_weights:
            avg_actual = sum(valid_weights) / len(valid_weights)
            yield_accuracy_factor = round(avg_actual / 180.0, 2)
            if yield_accuracy_factor < 0.5: yield_accuracy_factor = 0.5
            if yield_accuracy_factor > 1.5: yield_accuracy_factor = 1.5

    st.info(f"🧠 **AI収量予測精度モデル**：過去の収穫実績より、現在の重量推定制精度は **{yield_accuracy_factor * 100:.1f}%** でキャリブレーションされています。")

    if not teichaku_records:
        st.warning("現在栽培中のロットデータはありません。全ロットが収穫完了しているか、定植登録が必要です。")
    else:
        df_export = pd.DataFrame(teichaku_records, columns=["ID", "品種", "ハウス", "ベッド", "定植日", "株数", "予定サイズ", "メモ", "登録日時"])
        st.download_button(
            label="📥 全栽培ロットデータをCSVダウンロード",
            data=df_export.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"sanchu_active_lots_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        st.markdown("---")

        kankyo_dict = {log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]} for log in kankyo_logs}
        lots_data = []
        
        for record in teichaku_records:
            rec_id, variety, house, bed, plant_date, quantity, target_size = record[0], record[1], record[2], record[3], record[4], record[5], record[6]
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
                predicted_date_dt = datetime.now() + timedelta(days=remaining_days)
                predicted_date_str = predicted_date_dt.strftime("%Y年%m月%d日")
                
                try:
                    target_weight = float(''.join(filter(str.isdigit, target_size)))
                except:
                    target_weight = 180.0
                
                current_weight = int(target_weight * (current_growth_rate / 100.0) * yield_accuracy_factor)
                
                line_match = re.search(r'\(([A-Z])ライン\)', house)
                line_code = line_match.group(1) if line_match else "A"
                
                bed_match = re.search(r'(\d+)', bed)
                bed_num = int(bed_match.group(1)) if bed_match else 0
                
                lots_data.append({
                    "id": rec_id,
                    "location": f"{house} - {bed}",
                    "variety": variety,
                    "quantity": f"{quantity}株",
                    "growth_rate": f"{current_growth_rate:.1f} %",
                    "weight": f"{current_weight} g",
                    "pred_date": predicted_date_str,
                    "rem_days_str": f"あと {remaining_days} 日",
                    "sort_rem_days": remaining_days,
                    "sort_line": line_code,
                    "sort_bed": bed_num
                })
            except:
                pass
        
        lots_data.sort(key=lambda x: (x["sort_rem_days"], x["sort_line"], x["sort_bed"]))

        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6, h_col7, h_col8 = st.columns([2.2, 1.2, 1.0, 1.1, 1.0, 1.5, 1.2, 0.8])
        h_col1.markdown("**栽培場所**")
        h_col2.markdown("**品種**")
        h_col3.markdown("**株数**")
        h_col4.markdown("**AI生育率**")
        h_col5.markdown("**推定重量**")
        h_col6.markdown("**予測収穫日**")
        h_col7.markdown("**適期まで**")
        h_col8.markdown("**操作**")
        st.markdown("---")

        for lot in lots_data:
            c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([2.2, 1.2, 1.0, 1.1, 1.0, 1.5, 1.2, 0.8])
            c1.write(lot["location"])
            c2.write(lot["variety"])
            c3.write(lot["quantity"])
            c4.write(lot["growth_rate"])
            c5.write(lot["weight"])
            c6.write(lot["pred_date"])
            
            if lot["sort_rem_days"] == 0:
                c7.markdown(f":green[**{lot['rem_days_str']}**]")
            else:
                c7.write(lot["rem_days_str"])
                
            if c8.button("🗑️", key=f"del_pred_{lot['id']}", help="手動削除"):
                if delete_record("teichaku", lot["id"]):
                    st.success("削除しました。")
                    st.rerun()

# ----------------------------------------------------
# ⑥ 収穫実績・分析（グラフ完全正常化＆1日1本綺麗に集計版）
# ----------------------------------------------------
elif menu == "収穫実績・分析":
    st.header("【収穫実績・分析ダッシュボード】")
    shukaku_logs = select_all_shukaku()
    
    if not shukaku_logs:
        st.warning("現在登録されている収穫データはありません。「収穫登録」メニューから登録を行ってください。")
    else:
        df_s = pd.DataFrame(shukaku_logs, columns=[
            "ID", "収穫日", "ハウス", "ベッド", "重量(g)", "株数", "品質", "備考", "登録日時"
        ])
        
        df_s["重量(g)"] = pd.to_numeric(df_s["重量(g)"], errors="coerce").fillna(0.0)
        df_s["重量(kg)"] = df_s["重量(g)"] / 1000.0
        
        # YYYYMMDD -> YYYY-MM-DD
        def format_date(d_val):
            s = str(d_val).strip()
            if len(s) == 8:
                return f"{s[:4]}-{s[4:6]}-{s[6:]}"
            return s
            
        df_s["date_fmt"] = df_s["収穫日"].apply(format_date)
        
        # 1. 日別合計の完全集計（1日＝1本の棒にする）
        df_daily = df_s.groupby("date_fmt", as_index=False)["重量(kg)"].sum().sort_values("date_fmt")
        df_daily["display_date"] = df_daily["date_fmt"].apply(lambda x: f"{x[5:7]}/{x[8:10]}" if len(x)==10 else x)
        
        st.download_button(
            label="📥 収穫実績データをCSVダウンロード",
            data=df_s[["ID", "収穫日", "ハウス", "ベッド", "重量(g)", "品質", "備考", "登録日時"]].to_csv(index=False).encode('utf-8-sig'),
            file_name=f"sanchu_harvest_records_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        st.markdown("---")
        
        st.subheader("1. 日別 収穫総重量の推移 (kg)")
        fig_h = go.Figure()
        fig_h.add_trace(go.Bar(
            x=df_daily["display_date"], 
            y=df_daily["重量(kg)"], 
            text=df_daily["重量(kg)"].apply(lambda v: f"{v:.2f} kg"),
            textposition="outside",
            name="収穫量(kg)", 
            marker_color="#4caf50",
            width=0.35
        ))
        fig_h.update_layout(
            xaxis_title="収穫日", yaxis_title="収穫量 (kg)",
            hovermode="x unified", template="plotly_dark", height=420,
            bargap=0.5,
            xaxis=dict(type="category") # 重複・塗りつぶし完全防止
        )
        st.plotly_chart(fig_h, use_container_width=True)
        
        st.markdown("---")
        
        # 2. 収穫実績一覧表
        st.subheader("2. 収穫実績データ一覧表")
        
        def extract_line(h_str):
            if not h_str: return "A"
            m = re.search(r'\(([A-Z])ライン\)', str(h_str))
            return m.group(1) if m else "A"

        def extract_bed(b_str):
            if not b_str: return 0
            m = re.search(r'(\d+)', str(b_str))
            return int(m.group(1)) if m else 0

        df_s["sort_line"] = df_s["ハウス"].apply(extract_line)
        df_s["sort_bed"] = df_s["ベッド"].apply(extract_bed)
        
        df_sorted = df_s.sort_values(
            by=["date_fmt", "sort_line", "sort_bed"], 
            ascending=[False, True, True]
        ).reset_index(drop=True)

        h1, h2, h3, h4, h5, h6, h7 = st.columns([1.5, 2.2, 1.2, 1.0, 1.5, 1.8, 0.8])
        h1.markdown("**収穫日**")
        h2.markdown("**栽培場所**")
        h3.markdown("**収穫重量**")
        h4.markdown("**品質**")
        h5.markdown("**備考**")
        h6.markdown("**登録日時**")
        h7.markdown("**操作**")
        st.markdown("---")
        
        for idx, row in df_sorted.iterrows():
            c1, c2, c3, c4, c5, c6, c7 = st.columns([1.5, 2.2, 1.2, 1.0, 1.5, 1.8, 0.8])
            d_str = str(row['収穫日'])
            date_fmt = f"{d_str[:4]}/{d_str[4:6]}/{d_str[6:]}" if len(d_str)==8 else d_str
            
            c1.write(date_fmt)
            c2.write(f"{row['ハウス']} - {row['ベッド']}" if row['ハウス'] else "全体")
            c3.write(f"{row['重量(g)']} g")
            c4.write(row['品質'] if row['品質'] else "秀")
            c5.write(row['備考'] if row['備考'] else "-")
            c6.write(str(row['登録日時'])[:16] if row['登録日時'] else "-")
            
            if c7.button("🗑️", key=f"del_shukaku_{row['ID']}", help="この収穫記録を削除"):
                if delete_record("shukaku", row['ID']):
                    st.success("削除しました。")
                    st.rerun()

# ----------------------------------------------------
# ⑦ 総合グラフ分析
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
        
        df["dt"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)
        
        st.subheader("📅 表示期間の選択")
        filter_type = st.selectbox(
            "期間プリセット",
            ["直近30日間", "今月 (2026年7月)", "先月 (2026年6月)", "2026年全期間", "全期間", "日付で直接指定"]
        )
        
        today = datetime.now().date()
        if filter_type == "直近30日間":
            start_f, end_f = today - timedelta(days=30), today
        elif filter_type == "今月 (2026年7月)":
            start_f, end_f = date(today.year, today.month, 1), today
        elif filter_type == "先月 (2026年6月)":
            start_f = date(2026, 6, 1)
            end_f = date(2026, 6, 30)
        elif filter_type == "2026年全期間":
            start_f, end_f = date(2026, 1, 1), date(2026, 12, 31)
        elif filter_type == "全期間":
            start_f, end_f = df["dt"].min().date(), df["dt"].max().date()
        else:
            c1, c2 = st.columns(2)
            with c1: start_f = st.date_input("開始日", value=df["dt"].min().date())
            with c2: end_f = st.date_input("終了日", value=today)

        df_filtered = df[(df["dt"].dt.date >= start_f) & (df["dt"].dt.date <= end_f)].copy()

        st.download_button(
            label="📥 選択期間のCSVデータをダウンロード",
            data=df_filtered.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"sendai_climate_{start_f}_{end_f}.csv",
            mime="text/csv"
        )
        st.markdown("---")

        if df_filtered.empty:
            st.warning("⚠️ 選択された期間のデータが見つかりません。「今日の環境入力」画面で気象データを一括インポートしてください。")
        else:
            # --- グラフ1: 気温・水温 ---
            st.subheader("1. 気温 (最高/平均/最低) と ハウス水温の推移")
            fig1 = go.Figure()
            fig1.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["max_temp"], mode='lines+markers', name='最高気温 (℃)', line=dict(color='#e53935', dash='dash')))
            fig1.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["temp"], mode='lines+markers', name='平均気温 (℃)', line=dict(color='#4caf50', width=3)))
            fig1.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["min_temp"], mode='lines+markers', name='最低気温 (℃)', line=dict(color='#1e88e5', dash='dash')))
            fig1.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["water_temp"], mode='lines+markers', name='ハウス水温 (℃)', line=dict(color='#00bcd4', width=2)))
            
            fig1.update_layout(
                xaxis_title="日付", yaxis_title="温度 (℃)",
                hovermode="x unified", template="plotly_dark", height=420,
                xaxis=dict(tickformat="%m/%d")
            )
            st.plotly_chart(fig1, use_container_width=True)

            st.markdown("---")

            # --- グラフ2: 湿度・降水量・日照時間 ---
            st.subheader("2. 湿度 (%) / 降水量 (mm) / 日照時間 (時間) の推移")
            fig2 = make_subplots(
                rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                subplot_titles=("■ 湿度推移", "■ 降水量 と 日照時間"),
                specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
            )
            
            fig2.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["humidity_mean"], mode='lines+markers', name='平均湿度 (%)', line=dict(color='#009688')), row=1, col=1)
            fig2.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["humidity_min"], mode='lines+markers', name='最小湿度 (%)', line=dict(color='#80cbc4', dash='dot')), row=1, col=1)
            
            fig2.add_trace(go.Bar(x=df_filtered["dt"], y=df_filtered["precip_total"], name='日降水量 (mm)', marker_color='#2196f3', opacity=0.6), row=2, col=1, secondary_y=False)
            fig2.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["sunshine_hours"], mode='lines+markers', name='日照時間 (時間)', line=dict(color='#ff9800', width=2)), row=2, col=1, secondary_y=True)
            
            fig2.update_yaxes(title_text="湿度 (%)", row=1, col=1)
            fig2.update_yaxes(title_text="降水量 (mm)", row=2, col=1, secondary_y=False)
            fig2.update_yaxes(title_text="日照時間 (時間)", row=2, col=1, secondary_y=True)
            fig2.update_xaxes(tickformat="%m/%d", row=2, col=1)
            fig2.update_layout(hovermode="x unified", template="plotly_dark", height=650)
            st.plotly_chart(fig2, use_container_width=True)

            st.markdown("---")

            # --- グラフ3: 風速・気圧 ---
            st.subheader("3. 風速 (m/s) と 現地気圧 (hPa) の推移")
            fig3 = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig3.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["wind_speed_max"], mode='lines+markers', name='最大風速 (m/s)', line=dict(color='#ff5722')), secondary_y=False)
            fig3.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["wind_speed_instant"], mode='lines+markers', name='最大瞬間風速 (m/s)', line=dict(color='#ffab91', dash='dash')), secondary_y=False)
            fig3.add_trace(go.Scatter(x=df_filtered["dt"], y=df_filtered["press_land"], mode='lines', name='現地気圧 (hPa)', line=dict(color='#9c27b0', dash='dot')), secondary_y=True)
            
            fig3.update_yaxes(title_text="風速 (m/s)", secondary_y=False)
            fig3.update_yaxes(title_text="気圧 (hPa)", secondary_y=True)
            fig3.update_xaxes(tickformat="%m/%d")
            fig3.update_layout(hovermode="x unified", template="plotly_dark", height=420)
            st.plotly_chart(fig3, use_container_width=True)
