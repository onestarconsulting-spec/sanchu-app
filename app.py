import re
import threading
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from database.db_manager import (
    authenticate_user,
    delete_user,
    get_connection,
    init_db,
    insert_shukaku_and_clear_teichaku,
    insert_teichaku,
    insert_user,
    select_all_kankyo,
    select_all_shukaku,
    select_all_teichaku,
    select_all_users,
    sync_auto_climate_data,
    update_house_manual_kankyo,
)
from plotly.subplots import make_subplots

# データベースの初期化
init_db()

# 仙台の観測座標
SENDAI_LAT = 38.2688
SENDAI_LON = 140.8721


# ----------------------------------------------------
# ⚡ 爆速化：バックグラウンド非同期＆スマート差分同期
# ----------------------------------------------------
def bg_smart_climate_sync():
  today_str = datetime.now().strftime("%Y%m%d")
  try:
    kankyo_logs = select_all_kankyo()
    latest_date_in_db = kankyo_logs[0][1] if kankyo_logs else None

    if latest_date_in_db == today_str:
      return

    start_date_str = f"{datetime.now().year - 1}-01-01"
    end_date_str = datetime.now().strftime("%Y-%m-%d")

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

    response = requests.get(url, timeout=10)
    data = response.json().get("daily", {})
    dates = data.get("time", [])

    def deg_to_compass(num):
      val = int((num / 22.5) + 0.5)
      arr = [
          "北",
          "北北東",
          "北東",
          "東北東",
          "東",
          "東南東",
          "南東",
          "南南東",
          "南",
          "南南西",
          "南西",
          "西南西",
          "西",
          "西北西",
          "北西",
          "北北西",
      ]
      return arr[(val % 16)]

    for i in range(len(dates)):
      d_str = dates[i].replace("-", "")
      t_mean = (
          round(data["temperature_2m_mean"][i], 1)
          if data["temperature_2m_mean"][i] is not None
          else 25.0
      )
      t_max = (
          round(data["temperature_2m_max"][i], 1)
          if data["temperature_2m_max"][i] is not None
          else 30.0
      )
      t_min = (
          round(data["temperature_2m_min"][i], 1)
          if data["temperature_2m_min"][i] is not None
          else 20.0
      )

      h_mean = (
          round(data["relative_humidity_2m_mean"][i], 1)
          if data["relative_humidity_2m_mean"][i] is not None
          else 75.0
      )
      h_min = (
          round(data["relative_humidity_2m_min"][i], 1)
          if data["relative_humidity_2m_min"][i] is not None
          else 50.0
      )

      press = (
          round(data["surface_pressure_mean"][i], 1)
          if data["surface_pressure_mean"][i] is not None
          else 1013.2
      )
      w_max = (
          round(data["wind_speed_10m_max"][i] / 3.6, 1)
          if data["wind_speed_10m_max"][i] is not None
          else 3.0
      )
      w_gust = (
          round(data["wind_gusts_10m_max"][i] / 3.6, 1)
          if data["wind_gusts_10m_max"][i] is not None
          else 5.0
      )
      w_dir = (
          deg_to_compass(data["wind_direction_10m_dominant"][i])
          if data["wind_direction_10m_dominant"][i] is not None
          else "東"
      )

      sun_hours = (
          round(data["sunshine_duration"][i] / 3600.0, 1)
          if data["sunshine_duration"][i] is not None
          else 6.0
      )
      precip = (
          round(data["precipitation_sum"][i], 1)
          if data["precipitation_sum"][i] is not None
          else 0.0
      )
      rad = (
          data["shortwave_radiation_sum"][i]
          if data["shortwave_radiation_sum"][i] is not None
          else 12.0
      )
      dli = round(rad * 2.05, 1)

      item = {
          "date": d_str,
          "temp": t_mean,
          "min_temp": t_min,
          "max_temp": t_max,
          "dli": dli,
          "press_land": press,
          "press_sea": press + 5.0,
          "humidity_mean": h_mean,
          "humidity_min": h_min,
          "wind_speed_mean": round(w_max * 0.6, 1),
          "wind_speed_max": w_max,
          "wind_dir_max": w_dir,
          "wind_speed_instant": w_gust,
          "wind_dir_instant": w_dir,
          "sunshine_hours": sun_hours,
          "precip_total": precip,
          "precip_max_1h": round(precip * 0.4, 1),
          "precip_max_10m": round(precip * 0.1, 1),
          "snow_depth_sum": 0.0,
          "snow_depth_max": 0.0,
      }
      sync_auto_climate_data(item)
  except:
    pass


threading.Thread(target=bg_smart_climate_sync, daemon=True).start()

# ----------------------------------------------------
# ログイン状態のセッション管理
# ----------------------------------------------------
if "logged_in" not in st.session_state:
  st.session_state["logged_in"] = False
if "user_info" not in st.session_state:
  st.session_state["user_info"] = None

st.set_page_config(
    page_title="水耕栽培管理・収穫予測システム", page_icon="🌱", layout="wide"
)

# ----------------------------------------------------
# 📱 スマホ全画面化（アドレスバー消去）メタタグの動的挿入
# ----------------------------------------------------
components.html(
    """
    <script>
        const head = window.parent.document.head;

        // iOS (Safari) 用全画面化タグ
        if (!head.querySelector('meta[name="apple-mobile-web-app-capable"]')) {
            const metaApple = window.parent.document.createElement('meta');
            metaApple.name = 'apple-mobile-web-app-capable';
            metaApple.content = 'yes';
            head.appendChild(metaApple);
        }
        
        // iOS ステータスバーのデザイン指定
        if (!head.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')) {
            const metaStatus = window.parent.document.createElement('meta');
            metaStatus.name = 'apple-mobile-web-app-status-bar-style';
            metaStatus.content = 'default';
            head.appendChild(metaStatus);
        }

        // Android (Chrome) 用全画面化タグ
        if (!head.querySelector('meta[name="mobile-web-app-capable"]')) {
            const metaAndroid = window.parent.document.createElement('meta');
            metaAndroid.name = 'mobile-web-app-capable';
            metaAndroid.content = 'yes';
            head.appendChild(metaAndroid);
        }
    </script>
    """,
    height=0,
)

# ----------------------------------------------------
# 🔐 ログイン画面
# ----------------------------------------------------
if not st.session_state["logged_in"]:
  st.title("🔑 水耕栽培管理・収穫予測システム ログイン")
  st.write("システムを利用するには、IDとパスワードを入力してログインしてください。")

  with st.form("login_form"):
    username_input = st.text_input("ユーザーID")
    password_input = st.text_input("パスワード", type="password")
    submit_login = st.form_submit_button("ログイン")

    if submit_login:
      user = authenticate_user(username_input, password_input)
      if user:
        st.session_state["logged_in"] = True
        st.session_state["user_info"] = user
        st.rerun()
      else:
        st.error("⚠️ ユーザーIDまたはパスワードが正しくありません。")

  st.stop()

# ----------------------------------------------------
# 🔓 ログイン後のメインアプリケーション
# ----------------------------------------------------
current_user = st.session_state["user_info"]
user_disp_name = current_user.get("display_name", current_user["username"])
is_admin = current_user["role"] == "admin"


def get_today_weather():
  url = f"https://api.open-meteo.com/v1/forecast?latitude={SENDAI_LAT}&longitude={SENDAI_LON}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=Asia%2FTokyo"
  try:
    response = requests.get(url, timeout=5)
    data = response.json()
    weather_code = data["daily"]["weathercode"][0]
    max_temp = data["daily"]["temperature_2m_max"][0]
    min_temp = data["daily"]["temperature_2m_min"][0]
    weather_map = {
        0: "☀️ 晴天",
        1: "🌤️ おおむね晴れ",
        2: "⛅ 時々曇り",
        3: "☁️ 曇り",
        45: "🌫️ 霧",
        48: "🌫️ 霧",
        51: "🌧️ 霧雨",
        61: "☔ 雨",
        80: "🌦️ にわか雨",
        95: "⚡ 雷雨",
    }
    return (
        weather_map.get(weather_code, "☁️ 晴/曇"),
        f"{max_temp} ℃",
        f"{min_temp} ℃",
    )
  except:
    return "⚠️ 取得失敗", "--", "--"


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


def update_user_info(user_id, username, password, role, display_name):
  """ユーザー情報を更新（パスワードは入力がある場合のみ変更）"""
  try:
    conn = get_connection()
    cursor = conn.cursor()
    if password and password.strip() != "":
      cursor.execute(
          "UPDATE users SET username = %s, password = %s, role = %s,"
          " display_name = %s WHERE id = %s",
          (username, password, role, display_name, user_id),
      )
    else:
      cursor.execute(
          "UPDATE users SET username = %s, role = %s, display_name = %s WHERE"
          " id = %s",
          (username, role, display_name, user_id),
      )
    conn.commit()
    cursor.close()
    conn.close()
    return True
  except Exception as e:
    st.error(f"ユーザー更新エラー: {e}")
    return False


# サイドバー表示
st.sidebar.markdown(
    f"👤 **ログイン中**: `{user_disp_name}`"
    f" （{'👑管理者' if is_admin else '🌱一般'}）"
)
if st.sidebar.button("🚪 ログアウト"):
  st.session_state["logged_in"] = False
  st.session_state["user_info"] = None
  st.rerun()

st.sidebar.markdown("---")

menu_options = [
    "ホーム・本日の状況",
    "定植登録",
    "今日の環境入力",
    "収穫登録",
    "AI収穫予測 (栽培管理)",
    "収穫実績・分析",
    "総合グラフ分析",
]
if is_admin:
  menu_options.append("👥 ユーザー・権限管理")

menu = st.sidebar.radio("メニュー切り替え", menu_options)

st.title("🌱 水耕栽培管理・収穫予測システム")

# ----------------------------------------------------
# ① ホーム・本日の状況
# ----------------------------------------------------
if menu == "ホーム・本日の状況":
  st.header("【本日の状況サマリー - 仙台観測自動連動中】")

  teichaku_records = select_all_teichaku()
  kankyo_logs = select_all_kankyo()
  shukaku_logs = select_all_shukaku()

  active_lots = len(teichaku_records)
  today_harvest_lots = 0
  caution_lots = 0

  if teichaku_records:
    kankyo_dict = {
        log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]}
        for log in kankyo_logs
    }
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
            f_water = (
                0.8
                if day["water_temp"] and day["water_temp"] > 22.0
                else 1.0
            )
            if day["water_temp"] and day["water_temp"] > 22.0:
              water_stress_days += 1
            f_dli = max(0.7, min(1.3, day["dli"] / 15.0))
            base_growth *= f_temp * f_water * f_dli
          total_growth += base_growth
          current_dt += timedelta(days=1)

        current_growth_rate = min(100.0, total_growth)
        remaining_days = max(
            0, int((100.0 - current_growth_rate) / (100.0 / 30.0))
        )

        if remaining_days == 0:
          today_harvest_lots += 1
        if water_stress_days >= 2:
          caution_lots += 1
      except:
        pass

  w_text, w_max, w_min = get_today_weather()

  st.markdown("### ☁️ 仙台本日の天気予報（気象庁/自動更新中）")
  w_col1, w_col2, w_col3 = st.columns(3)
  with w_col1:
    st.metric(label="本日の天気 (仙台)", value=w_text)
  with w_col2:
    st.metric(label="予想最高気温", value=w_max)
  with w_col3:
    st.metric(label="予想最低気温", value=w_min)
  st.markdown("---")

  if kankyo_logs:
    latest_env = kankyo_logs[0]
    l_date, l_wtemp, l_ph = latest_env[1], latest_env[5], latest_env[8]
    if l_wtemp and l_wtemp > 22.0:
      st.error(f"⚠️ **【ハウス水温アラート】** 水温が **{l_wtemp}℃** と高めです！")
      st.markdown("---")

  st.markdown("### 📊 ハウス内ロット状況")
  col1, col2, col3 = st.columns(3)
  with col1:
    st.metric(label="栽培中ロット", value=f"{active_lots} ロット")
  with col2:
    st.metric(label="本日収穫適期", value=f"{today_harvest_lots} ロット")
  with col3:
    st.metric(label="水温ストレス（要注意）", value=f"{caution_lots} ロット")
  st.markdown("---")

  left_col, right_col = st.columns(2)
  with left_col:
    st.subheader("📊 今月の目標収穫量と進捗")
    target_kg = st.number_input(
        "今月の目標収穫量 (kg)", min_value=1, value=50
    )
    this_month_str = datetime.now().strftime("%Y%m")

    current_weight_g = sum([
        float(log[4])
        for log in shukaku_logs
        if str(log[1]).startswith(this_month_str) and log[4] is not None
    ])
    current_weight_kg = current_weight_g / 1000.0
    progress_percent = (
        min(100, int((current_weight_kg / target_kg) * 100))
        if target_kg > 0
        else 0
    )

    st.metric(
        label="現在の収穫実績",
        value=f"{current_weight_kg:.2f} kg",
        delta=f"目標まで あと {max(0.0, target_kg - current_weight_kg):.2f} kg",
    )
    st.progress(progress_percent / 100)

  with right_col:
    st.subheader("📋 本日の作業タスク")
    st.checkbox("気象データを自動取り込み・確認する", key="task1", value=True)
    st.checkbox(
        "ハウス気温・水温・EC・pHを手動測定して更新する", key="task2"
    )
    st.checkbox("収穫適期ロットの巡回見回りを行う", key="task3")

# ----------------------------------------------------
# ② 定植登録
# ----------------------------------------------------
elif menu == "定植登録":
  st.header("【定植登録フォーム】")
  with st.form("teichaku_form"):
    variety = st.selectbox(
        "品種", ["サンチュ", "サニーレタス", "グリーンカール", "三つ葉"]
    )
    house = st.selectbox("ハウス", ["Ⅰ棟", "Ⅱ棟", "Ⅲ棟", "Ⅳ棟"])
    lines = st.multiselect(
        "ライン (複数選択可)",
        [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "S",
            "T",
        ],
        default=["A"],
    )
    beds = st.multiselect(
        "ベッド (複数選択可)",
        [f"{i}番ベッド" for i in range(1, 21)],
        default=["1番ベッド"],
    )
    plant_date_val = st.date_input("定植日", datetime.now())
    quantity = st.number_input(
        "株数 (1ベッドあたり)", min_value=1, value=150
    )
    target_size_val = st.number_input(
        "予定収穫サイズ (g)", min_value=1, value=180
    )
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
            insert_teichaku(
                variety,
                full_house,
                b,
                str_plant_date,
                int(quantity),
                str_target_size,
                memo,
                created_by=user_disp_name,
            )
            count += 1
        st.success(
            f"🎉 担当者: `{user_disp_name}` として {house} の {len(lines)}ライン ×"
            f" {len(beds)}ベッド（計 {count} 件）を一括登録しました！"
        )

# ----------------------------------------------------
# ③ 今日の環境入力
# ----------------------------------------------------
elif menu == "今日の環境入力":
  st.header("【ハウス内環境データ入力】")
  st.info(
      "💡 仙台の外気象データ（気温・湿度・風速・気圧等）は**ログイン時に全自動で更新**されています。\n"
      "ここでは実際に測定した**ハウス内気温・ハウス水温・EC・pH**を入力してください。"
  )

  kankyo_logs = select_all_kankyo()
  def_htemp, def_water, def_ec, def_ph = 25.0, 20.0, 1.2, 6.5

  if kankyo_logs:
    for log in kankyo_logs:
      if len(log) > 24 and log[24] is not None:
        def_htemp = float(log[24])
        break
    for log in kankyo_logs:
      if log[5] is not None:
        def_water = float(log[5])
        break
    for log in kankyo_logs:
      if log[7] is not None:
        def_ec = float(log[7])
        break
    for log in kankyo_logs:
      if log[8] is not None:
        def_ph = float(log[8])
        break

  with st.form("kankyo_form"):
    date_val = st.date_input("測定日付", datetime.now())
    house_temp = st.number_input(
        "ハウス内気温 (℃) [手動測定]", value=def_htemp, step=0.1
    )
    water_temp = st.number_input(
        "ハウス水温 (℃) [手動測定]", value=def_water, step=0.1
    )
    ec = st.number_input("EC (dS/m) [手動測定]", value=def_ec, step=0.1)
    ph = st.number_input("pH [手動測定]", value=def_ph, step=0.1)
    memo = st.text_area("備考メモ", "")

    submitted = st.form_submit_button(
        "この日のハウス内環境データを保存する"
    )
    if submitted:
      str_date = date_val.strftime("%Y%m%d")
      update_house_manual_kankyo(
          str_date,
          house_temp,
          water_temp,
          ec,
          ph,
          memo,
          created_by=user_disp_name,
      )
      st.success(
          f"担当者: `{user_disp_name}`"
          " として指定日のデータ（内気温・水温・EC・pH）を更新・保存しました！"
      )
      st.rerun()

# ----------------------------------------------------
# ④ 収穫登録
# ----------------------------------------------------
elif menu == "収穫登録":
  st.header("【収穫データ登録】")
  st.write(
      "収穫を行った棟・ライン・ベッドを選択して登録します。登録完了と同時に、**AI収穫予測（栽培管理表）から自動削除**されます。"
  )

  with st.form("shukaku_form"):
    shukaku_date_val = st.date_input("収穫日", datetime.now())
    house = st.selectbox("ハウス", ["Ⅰ棟", "Ⅱ棟", "Ⅲ棟", "Ⅳ棟"])
    lines = st.multiselect(
        "ライン (複数選択可)",
        [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
            "P",
            "Q",
            "R",
            "S",
            "T",
        ],
        default=["A"],
    )
    beds = st.multiselect(
        "ベッド (複数選択可)",
        [f"{i}番ベッド" for i in range(1, 21)],
        default=["1番ベッド"],
    )
    weight = st.number_input(
        "1ベッドあたりの実収穫重量 (g)",
        min_value=1.0,
        value=180.0,
        step=10.0,
    )
    quality = st.selectbox("品質ランク", ["秀", "優", "良", "可"])
    memo = st.text_area("備考", "")

    submitted = st.form_submit_button("この内容で収穫登録する")
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
            insert_shukaku_and_clear_teichaku(
                str_shukaku_date,
                full_house,
                b,
                weight,
                quality,
                memo,
                created_by=user_disp_name,
            )
            count += 1

        st.success(
            f"🎉 担当者: `{user_disp_name}` として {house} の {len(lines)}ライン ×"
            f" {len(beds)}ベッド（計 {count} 件）を収穫登録しました！"
        )

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
    valid_weights = [
        float(log[4])
        for log in shukaku_logs
        if len(log) > 4 and log[4] is not None and float(log[4]) > 0
    ]
    if valid_weights:
      avg_actual = sum(valid_weights) / len(valid_weights)
      yield_accuracy_factor = round(avg_actual / 180.0, 2)
      if yield_accuracy_factor < 0.5:
        yield_accuracy_factor = 0.5
      if yield_accuracy_factor > 1.5:
        yield_accuracy_factor = 1.5

  st.info(
      f"🧠 **AI収量予測精度モデル**：過去の収穫実績より、現在の重量推推定精度は"
      f" **{yield_accuracy_factor * 100:.1f}%** でキャリブレーションされています。"
  )

  if not teichaku_records:
    st.warning(
        "現在栽培中のロットデータはありません。全ロットが収穫完了しているか、定植登録が必要です。"
    )
  else:
    df_export = pd.DataFrame(
        teichaku_records,
        columns=[
            "ID",
            "品種",
            "ハウス",
            "ベッド",
            "定植日",
            "株数",
            "予定サイズ",
            "メモ",
            "登録日時",
            "登録者",
        ],
    )
    st.download_button(
        label="📥 全栽培ロットデータをCSVダウンロード",
        data=df_export.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"active_lots_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
    st.markdown("---")

    kankyo_dict = {
        log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]}
        for log in kankyo_logs
    }
    lots_data = []

    for record in teichaku_records:
      rec_id, variety, house, bed, plant_date, quantity, target_size = (
          record[0],
          record[1],
          record[2],
          record[3],
          record[4],
          record[5],
          record[6],
      )
      created_by_user = (
          record[9] if len(record) > 9 and record[9] else "システム"
      )
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
            f_water = (
                0.8
                if day["water_temp"] and day["water_temp"] > 22.0
                else 1.0
            )
            f_dli = max(0.7, min(1.3, day["dli"] / 15.0))
            base_growth *= f_temp * f_water * f_dli
          total_growth += base_growth
          current_dt += timedelta(days=1)

        current_growth_rate = min(100.0, total_growth)
        remaining_days = max(
            0, int((100.0 - current_growth_rate) / (100.0 / 30.0))
        )
        predicted_date_dt = datetime.now() + timedelta(days=remaining_days)
        predicted_date_str = predicted_date_dt.strftime("%Y年%m月%d日")

        try:
          target_weight = float("".join(filter(str.isdigit, target_size)))
        except:
          target_weight = 180.0

        current_weight = int(
            target_weight
            * (current_growth_rate / 100.0)
            * yield_accuracy_factor
        )

        line_match = re.search(r"\(([A-Z])ライン\)", house)
        line_code = line_match.group(1) if line_match else "A"

        bed_match = re.search(r"(\d+)", bed)
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
            "created_by": created_by_user,
            "sort_rem_days": remaining_days,
            "sort_line": line_code,
            "sort_bed": bed_num,
        })
      except:
        pass

    lots_data.sort(
        key=lambda x: (x["sort_rem_days"], x["sort_line"], x["sort_bed"])
    )

    col_widths = [2.0, 1.0, 0.8, 1.0, 0.9, 1.3, 1.0, 1.1]
    if is_admin:
      col_widths.append(0.6)

    h_cols = st.columns(col_widths)
    h_cols[0].markdown("**栽培場所**")
    h_cols[1].markdown("**品種**")
    h_cols[2].markdown("**株数**")
    h_cols[3].markdown("**AI生育率**")
    h_cols[4].markdown("**推定重量**")
    h_cols[5].markdown("**予測収穫日**")
    h_cols[6].markdown("**適期まで**")
    h_cols[7].markdown("**登録者**")
    if is_admin:
      h_cols[8].markdown("**操作**")
    st.markdown("---")

    for lot in lots_data:
      c_cols = st.columns(col_widths)
      c_cols[0].write(lot["location"])
      c_cols[1].write(lot["variety"])
      c_cols[2].write(lot["quantity"])
      c_cols[3].write(lot["growth_rate"])
      c_cols[4].write(lot["weight"])
      c_cols[5].write(lot["pred_date"])

      if lot["sort_rem_days"] == 0:
        c_cols[6].markdown(f":green[**{lot['rem_days_str']}**]")
      else:
        c_cols[6].write(lot["rem_days_str"])

      c_cols[7].write(lot["created_by"])

      if is_admin:
        if c_cols[8].button(
            "🗑️", key=f"del_pred_{lot['id']}", help="手動削除"
        ):
          if delete_record("teichaku", lot["id"]):
            st.success("削除しました。")
            st.rerun()

# ----------------------------------------------------
# ⑥ 収穫実績・分析
# ----------------------------------------------------
elif menu == "収穫実績・分析":
  st.header("【収穫実績・分析ダッシュボード】")
  shukaku_logs = select_all_shukaku()

  if not shukaku_logs:
    st.warning(
        "現在登録されている収穫データはありません。「収穫登録」メニューから登録を行ってください。"
    )
  else:
    df_s = pd.DataFrame(
        shukaku_logs,
        columns=[
            "ID",
            "収穫日",
            "ハウス",
            "ベッド",
            "重量(g)",
            "株数",
            "品質",
            "備考",
            "登録日時",
            "品種",
            "登録者",
        ],
    )

    df_s["重量(g)"] = (
        pd.to_numeric(df_s["重量(g)"], errors="coerce").fillna(0.0)
    )
    df_s["重量(kg)"] = df_s["重量(g)"] / 1000.0
    df_s["品種"] = df_s["品種"].fillna("サンチュ")
    df_s["登録者"] = df_s["登録者"].fillna("管理者")

    def format_date(d_val):
      s = str(d_val).strip()
      if len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
      return s

    df_s["date_fmt"] = df_s["収穫日"].apply(format_date)
    df_s["dt"] = pd.to_datetime(df_s["date_fmt"], errors="coerce")

    st.download_button(
        label="📥 全過去収穫実績データをCSVダウンロード",
        data=df_s[[
            "ID",
            "収穫日",
            "品種",
            "ハウス",
            "ベッド",
            "重量(g)",
            "品質",
            "備考",
            "登録日時",
            "登録者",
        ]]
        .to_csv(index=False)
        .encode("utf-8-sig"),
        file_name=f"all_harvest_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
    st.markdown("---")

    st.subheader("1. 品目別 収穫総重量の推移 (kg)")

    today_dt_obj = datetime.now().date()
    this_year_val = today_dt_obj.year
    last_year_val = this_year_val - 1

    this_month_lbl = f"今月 ({this_year_val}年{today_dt_obj.month}月)"
    first_day_curr = today_dt_obj.replace(day=1)
    last_day_prev = first_day_curr - timedelta(days=1)
    prev_month_lbl = f"先月 ({last_day_prev.year}年{last_day_prev.month}月)"

    this_year_lbl = f"今年 ({this_year_val}年全期間)"
    last_year_lbl = f"昨年 ({last_year_val}年全期間)"

    filter_type_h = st.selectbox(
        "グラフ表示期間の選択",
        [
            "直近30日間",
            this_month_lbl,
            prev_month_lbl,
            this_year_lbl,
            last_year_lbl,
            "全期間",
            "日付で直接指定",
        ],
    )

    today = datetime.now().date()
    if filter_type_h == "直近30日間":
      start_h, end_h = today - timedelta(days=30), today
    elif filter_type_h == this_month_lbl:
      start_h, end_h = date(today.year, today.month, 1), today
    elif filter_type_h == prev_month_lbl:
      start_h = date(last_day_prev.year, last_day_prev.month, 1)
      end_h = last_day_prev
    elif filter_type_h == this_year_lbl:
      start_h, end_h = date(this_year_val, 1, 1), date(this_year_val, 12, 31)
    elif filter_type_h == last_year_lbl:
      start_h, end_h = date(last_year_val, 1, 1), date(last_year_val, 12, 31)
    elif filter_type_h == "全期間":
      min_d = (
          df_s["dt"].min().date()
          if not df_s["dt"].isna().all()
          else date(this_year_val, 1, 1)
      )
      start_h, end_h = min_d, today
    else:
      c1, c2 = st.columns(2)
      with c1:
        start_h = st.date_input("開始日", value=today - timedelta(days=30))
      with c2:
        end_h = st.date_input("終了日", value=today)

    all_days = [
        start_h + timedelta(days=i) for i in range((end_h - start_h).days + 1)
    ]
    varieties = ["サンチュ", "サニーレタス", "グリーンカール", "三つ葉"]

    full_grid = (
        pd.MultiIndex.from_product(
            [[d.strftime("%Y-%m-%d") for d in all_days], varieties],
            names=["date_fmt", "品種"],
        )
        .to_frame()
        .reset_index(drop=True)
    )

    df_s_filtered = df_s[
        (df_s["dt"].dt.date >= start_h) & (df_s["dt"].dt.date <= end_h)
    ].copy()
    df_pv = (
        df_s_filtered.groupby(["date_fmt", "品種"])["重量(kg)"]
        .sum()
        .reset_index()
        if not df_s_filtered.empty
        else pd.DataFrame(columns=["date_fmt", "品種", "重量(kg)"])
    )

    df_merged = pd.merge(
        full_grid, df_pv, on=["date_fmt", "品種"], how="left"
    ).fillna({"重量(kg)": 0.0})
    df_merged["display_date"] = df_merged["date_fmt"].apply(
        lambda x: f"{x[5:7]}/{x[8:10]}" if len(x) == 10 else x
    )

    fig_variety = px.bar(
        df_merged,
        x="display_date",
        y="重量(kg)",
        color="品種",
        title="■ 日別・品目別収穫量 (kg)",
        labels={
            "display_date": "収穫日",
            "重量(kg)": "収穫重量 (kg)",
            "品種": "品目",
        },
        template="plotly_dark",
        color_discrete_map={
            "サンチュ": "#4caf50",
            "サニーレタス": "#e53935",
            "グリーンカール": "#00bcd4",
            "三つ葉": "#82c91e",
        },
    )
    fig_variety.update_layout(
        height=420, hovermode="x unified", xaxis=dict(type="category")
    )
    st.plotly_chart(fig_variety, use_container_width=True)

    st.markdown("---")

    st.subheader("2. 過去1週間（直近7日間）の収穫実績データ一覧表")
    one_week_ago = today - timedelta(days=7)
    df_1week = df_s[df_s["dt"].dt.date >= one_week_ago].copy()

    if df_1week.empty:
      st.info("過去1週間以内の収穫データはありません。")
    else:

      def extract_line(h_str):
        if not h_str:
          return "A"
        m = re.search(r"\(([A-Z])ライン\)", str(h_str))
        return m.group(1) if m else "A"

      def extract_bed(b_str):
        if not b_str:
          return 0
        m = re.search(r"(\d+)", str(b_str))
        return int(m.group(1)) if m else 0

      df_1week["sort_line"] = df_1week["ハウス"].apply(extract_line)
      df_1week["sort_bed"] = df_1week["ベッド"].apply(extract_bed)

      df_1week_sorted = df_1week.sort_values(
          by=["date_fmt", "品種", "sort_line", "sort_bed"],
          ascending=[False, True, True, True],
      ).reset_index(drop=True)

      s_col_widths = [1.2, 1.1, 1.8, 1.0, 0.8, 1.1, 1.1, 1.3]
      if is_admin:
        s_col_widths.append(0.6)

      sh_cols = st.columns(s_col_widths)
      sh_cols[0].markdown("**収穫日**")
      sh_cols[1].markdown("**品種**")
      sh_cols[2].markdown("**栽培場所**")
      sh_cols[3].markdown("**収穫重量**")
      sh_cols[4].markdown("**品質**")
      sh_cols[5].markdown("**備考**")
      sh_cols[6].markdown("**担当者**")
      sh_cols[7].markdown("**登録日時**")
      if is_admin:
        sh_cols[8].markdown("**操作**")
      st.markdown("---")

      for idx, row in df_1week_sorted.iterrows():
        sc_cols = st.columns(s_col_widths)
        d_str = str(row["収穫日"])
        date_fmt = (
            f"{d_str[:4]}/{d_str[4:6]}/{d_str[6:]}"
            if len(d_str) == 8
            else d_str
        )

        sc_cols[0].write(date_fmt)
        sc_cols[1].write(row["品種"])
        sc_cols[2].write(
            f"{row['ハウス']} - {row['ベッド']}" if row["ハウス"] else "全体"
        )
        sc_cols[3].write(f"{row['重量(g)']} g")
        sc_cols[4].write(row["品質"] if row["品質"] else "秀")
        sc_cols[5].write(row["備考"] if row["備考"] else "-")
        sc_cols[6].write(row["登録者"] if row["登録者"] else "管理者")
        sc_cols[7].write(
            str(row["登録日時"])[:16] if row["登録日時"] else "-"
        )

        if is_admin:
          if sc_cols[8].button(
              "🗑️",
              key=f"del_shukaku_{row['ID']}",
              help="この収穫記録を削除",
          ):
            if delete_record("shukaku", row["ID"]):
              st.success("削除しました。")
              st.rerun()

# ----------------------------------------------------
# ⑦ 総合グラフ分析
# ----------------------------------------------------
elif menu == "総合グラフ分析":
  st.header("【気象・ハウス環境データ 総合分析ダッシュボード】")
  logs = select_all_kankyo()

  if not logs:
    st.warning("表示する環境データがありません。")
  else:
    df = pd.DataFrame(
        logs,
        columns=[
            "id",
            "date",
            "temp",
            "min_temp",
            "max_temp",
            "water_temp",
            "dli",
            "ec",
            "ph",
            "memo",
            "created_at",
            "press_land",
            "press_sea",
            "humidity_mean",
            "humidity_min",
            "wind_speed_mean",
            "wind_speed_max",
            "wind_dir_max",
            "wind_speed_instant",
            "wind_dir_instant",
            "sunshine_hours",
            "precip_total",
            "precip_max_1h",
            "precip_max_10m",
            "snow_depth_sum",
            "snow_depth_max",
            "house_temp",
            "created_by",
        ],
    )

    df["dt"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["dt"]).sort_values("dt").reset_index(drop=True)

    st.subheader("📅 表示期間の選択")

    today_dt_obj = datetime.now().date()
    this_year_val = today_dt_obj.year
    last_year_val = this_year_val - 1

    this_month_lbl = f"今月 ({this_year_val}年{today_dt_obj.month}月)"
    first_day_curr = today_dt_obj.replace(day=1)
    last_day_prev = first_day_curr - timedelta(days=1)
    prev_month_lbl = f"先月 ({last_day_prev.year}年{last_day_prev.month}月)"

    this_year_lbl = f"今年 ({this_year_val}年全期間)"
    last_year_lbl = f"昨年 ({last_year_val}年全期間)"

    filter_type = st.selectbox(
        "期間プリセット",
        [
            "直近30日間",
            this_month_lbl,
            prev_month_lbl,
            this_year_lbl,
            last_year_lbl,
            "全期間",
            "日付で直接指定",
        ],
    )

    today = datetime.now().date()
    if filter_type == "直近30日間":
      start_f, end_f = today - timedelta(days=30), today
    elif filter_type == this_month_lbl:
      start_f, end_f = date(today.year, today.month, 1), today
    elif filter_type == prev_month_lbl:
      start_f = date(last_day_prev.year, last_day_prev.month, 1)
      end_f = last_day_prev
    elif filter_type == this_year_lbl:
      start_f, end_f = date(this_year_val, 1, 1), date(this_year_val, 12, 31)
    elif filter_type == last_year_lbl:
      start_f, end_f = date(last_year_val, 1, 1), date(last_year_val, 12, 31)
    elif filter_type == "全期間":
      start_f, end_f = df["dt"].min().date(), df["dt"].max().date()
    else:
      c1, c2 = st.columns(2)
      with c1:
        start_f = st.date_input("開始日", value=df["dt"].min().date())
      with c2:
        end_f = st.date_input("終了日", value=today)

    df_filtered = df[
        (df["dt"].dt.date >= start_f) & (df["dt"].dt.date <= end_f)
    ].copy()

    st.download_button(
        label="📥 選択期間のCSVデータをダウンロード",
        data=df_filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"climate_data_{start_f}_{end_f}.csv",
        mime="text/csv",
    )
    st.markdown("---")

    if df_filtered.empty:
      st.warning("⚠️ 選択された期間のデータが見つかりません。")
    else:
      # ----------------------------------------------------
      # 💡 表示期間の長さに応じた「軸の目盛り間隔」設定
      # ----------------------------------------------------
      period_days = (end_f - start_f).days

      if period_days <= 60:
        dtick_val = "D1"
        date_format = "%m/%d"
      elif period_days <= 180:
        dtick_val = 7 * 86400000
        date_format = "%m/%d"
      else:
        dtick_val = "M1"
        date_format = "%Y/%m"

      trace_mode = "lines+markers" if period_days < 60 else "lines"

      # --- グラフ1: 外気気温 ＆ ハウス内気温・水温 ---
      st.subheader("1. 気温 (外気最高/平均/最低) と ハウス内気温・水温の推移")
      fig1 = go.Figure()
      fig1.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["max_temp"],
              mode=trace_mode,
              name="外気・最高気温 (℃)",
              line=dict(color="#e53935", width=1.5),
          )
      )
      fig1.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["temp"],
              mode=trace_mode,
              name="外気・平均気温 (℃)",
              line=dict(color="#4caf50", width=2),
          )
      )
      fig1.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["min_temp"],
              mode=trace_mode,
              name="外気・最低気温 (℃)",
              line=dict(color="#1e88e5", width=1.5),
          )
      )

      df_ht = df_filtered.dropna(subset=["house_temp"])
      if not df_ht.empty:
        fig1.add_trace(
            go.Scatter(
                x=df_ht["dt"],
                y=df_ht["house_temp"],
                mode=trace_mode,
                name="🏠 ハウス内気温 (℃)",
                line=dict(color="#ff9800", width=3),
            )
        )

      df_wt = df_filtered.dropna(subset=["water_temp"])
      if not df_wt.empty:
        fig1.add_trace(
            go.Scatter(
                x=df_wt["dt"],
                y=df_wt["water_temp"],
                mode=trace_mode,
                name="💧 ハウス水温 (℃)",
                line=dict(color="#00bcd4", width=2),
            )
        )

      fig1.update_layout(
          xaxis_title="日付",
          yaxis_title="温度 (℃)",
          hovermode="x unified",
          template="plotly_dark",
          height=450,
          xaxis=dict(
              type="date",
              tickformat=date_format,
              dtick=dtick_val,
              range=[start_f, end_f],
          ),
      )
      st.plotly_chart(fig1, use_container_width=True)

      st.markdown("---")

      # --- グラフ2: 湿度・降水量・日照時間 ---
      st.subheader("2. 湿度 (%) / 降水量 (mm) / 日照時間 (時間) の推移")
      fig2 = make_subplots(
          rows=2,
          cols=1,
          shared_xaxes=True,
          vertical_spacing=0.12,
          subplot_titles=("■ 湿度推移", "■ 降水量 と 日照時間"),
          specs=[[{"secondary_y": False}], [{"secondary_y": True}]],
      )

      fig2.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["humidity_mean"],
              mode=trace_mode,
              name="平均湿度 (%)",
              line=dict(color="#009688", width=2),
          ),
          row=1,
          col=1,
      )
      fig2.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["humidity_min"],
              mode=trace_mode,
              name="最小湿度 (%)",
              line=dict(color="#80cbc4", width=1.5),
          ),
          row=1,
          col=1,
      )

      fig2.add_trace(
          go.Bar(
              x=df_filtered["dt"],
              y=df_filtered["precip_total"],
              name="日降水量 (mm)",
              marker_color="#2196f3",
              opacity=0.6,
          ),
          row=2,
          col=1,
          secondary_y=False,
      )
      fig2.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["sunshine_hours"],
              mode=trace_mode,
              name="日照時間 (時間)",
              line=dict(color="#ff9800", width=2),
          ),
          row=2,
          col=1,
          secondary_y=True,
      )

      fig2.update_yaxes(title_text="湿度 (%)", row=1, col=1)
      fig2.update_yaxes(
          title_text="降水量 (mm)", row=2, col=1, secondary_y=False
      )
      fig2.update_yaxes(
          title_text="日照時間 (時間)", row=2, col=1, secondary_y=True
      )
      fig2.update_xaxes(
          type="date",
          tickformat=date_format,
          dtick=dtick_val,
          range=[start_f, end_f],
          row=2,
          col=1,
      )
      fig2.update_layout(
          hovermode="x unified", template="plotly_dark", height=650
      )
      st.plotly_chart(fig2, use_container_width=True)

      st.markdown("---")

      # --- グラフ3: 風速・気圧 ---
      st.subheader("3. 風速 (m/s) と 現地気圧 (hPa) の推移")
      fig3 = make_subplots(specs=[[{"secondary_y": True}]])

      fig3.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["wind_speed_max"],
              mode=trace_mode,
              name="最大風速 (m/s)",
              line=dict(color="#ff5722", width=2),
          ),
          secondary_y=False,
      )
      fig3.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["wind_speed_instant"],
              mode=trace_mode,
              name="最大瞬間風速 (m/s)",
              line=dict(color="#ffab91", width=1.5),
          ),
          secondary_y=False,
      )
      fig3.add_trace(
          go.Scatter(
              x=df_filtered["dt"],
              y=df_filtered["press_land"],
              mode="lines",
              name="現地気圧 (hPa)",
              line=dict(color="#9c27b0", width=1.5),
          ),
          secondary_y=True,
      )

      fig3.update_yaxes(title_text="風速 (m/s)", secondary_y=False)
      fig3.update_yaxes(title_text="気圧 (hPa)", secondary_y=True)
      fig3.update_xaxes(
          type="date",
          tickformat=date_format,
          dtick=dtick_val,
          range=[start_f, end_f],
      )
      fig3.update_layout(
          hovermode="x unified", template="plotly_dark", height=420
      )
      st.plotly_chart(fig3, use_container_width=True)

      st.markdown("---")

      # --- グラフ4: 培養液 (EC / pH) の推移 [手動測定データのみ] ---
      st.subheader("4. ハウス培養液 (EC / pH) の推移 [手動測定データのみ]")

      df_ec_ph = df_filtered.dropna(subset=["ec", "ph"], how="all")

      fig4 = make_subplots(specs=[[{"secondary_y": True}]])

      if not df_ec_ph.empty:
        fig4.add_trace(
            go.Scatter(
                x=df_ec_ph["dt"],
                y=df_ec_ph["ec"],
                mode=trace_mode,
                name="EC (dS/m)",
                line=dict(color="#e91e63", width=2.5),
            ),
            secondary_y=False,
        )
        fig4.add_trace(
            go.Scatter(
                x=df_ec_ph["dt"],
                y=df_ec_ph["ph"],
                mode=trace_mode,
                name="pH",
                line=dict(color="#00bcd4", width=2.5),
            ),
            secondary_y=True,
        )

      fig4.update_yaxes(title_text="EC (dS/m)", secondary_y=False)
      fig4.update_yaxes(title_text="pH", secondary_y=True)

      fig4.update_xaxes(
          type="date",
          tickformat=date_format,
          dtick=dtick_val,
          range=[start_f, end_f],
      )

      fig4.update_layout(
          hovermode="x unified", template="plotly_dark", height=420
      )
      st.plotly_chart(fig4, use_container_width=True)

# ----------------------------------------------------
# ⑧ 👥 ユーザー・権限管理（管理者専用画面）
# ----------------------------------------------------
elif menu == "👥 ユーザー・権限管理" and is_admin:
  st.header("【👥 ユーザー・権限管理画面 (管理者専用)】")
  st.write(
      "現場スタッフや管理者のユーザーアカウント（ID・氏名・PW・権限）の登録・変更・削除ができます。"
  )

  col_u1, col_u2 = st.columns([1, 1])

  with col_u1:
    st.subheader("➕ 新規アカウントの発行")
    with st.form("new_user_form"):
      new_disp = st.text_input("氏名 (例: 山田 花子)")
      new_u = st.text_input("新規ユーザーID (半角英数字)")
      new_p = st.text_input("新規パスワード", type="password")
      new_r = st.selectbox(
          "付与する権限", ["user (一般スタッフ)", "admin (管理者)"]
      )

      role_code = "admin" if "admin" in new_r else "user"
      submit_u = st.form_submit_button("アカウントを作成する")

      if submit_u:
        if not new_u or not new_p:
          st.error("⚠️ ユーザーIDとパスワードの両方を入力してください。")
        else:
          if insert_user(new_u, new_p, role_code, new_disp):
            st.success(
                f"🎉 ユーザー `{new_u}` （氏名: {new_disp or new_u}）"
                " を作成しました！"
            )
            st.rerun()
          else:
            st.error(
                "⚠️"
                " このユーザーIDは既に存在します。別のIDを指定してください。"
            )

  with col_u2:
    st.subheader("📋 登録済みユーザー一覧・編集")
    all_u = select_all_users()
    if all_u:
      for u in all_u:
        u_id, u_name, u_role, u_disp, u_created = (
            u[0],
            u[1],
            u[2],
            u[3],
            u[4],
        )
        r_label = "👑 管理者" if u_role == "admin" else "🌱 一般"

        st.write(f"👤 **{u_disp}** (`{u_name}`) - {r_label}")

        with st.expander("✏️ アカウント情報を変更・管理する"):
          with st.form(key=f"edit_user_form_{u_id}"):
            edit_disp = st.text_input("氏名", value=u_disp or "")
            edit_u = st.text_input("ユーザーID (半角英数字)", value=u_name)
            edit_p = st.text_input(
                "新しいパスワード (変更しない場合は空欄)",
                type="password",
            )
            edit_r_idx = 1 if u_role == "admin" else 0
            edit_r = st.selectbox(
                "権限",
                ["user (一般スタッフ)", "admin (管理者)"],
                index=edit_r_idx,
            )

            e_role_code = "admin" if "admin" in edit_r else "user"
            submit_edit = st.form_submit_button("変更内容を保存する")

            if submit_edit:
              if not edit_u:
                st.error("⚠️ ユーザーIDを入力してください。")
              else:
                if update_user_info(
                    u_id, edit_u, edit_p, e_role_code, edit_disp
                ):
                  st.success(
                      f"🎉 ユーザー `{edit_disp}` の情報を更新しました！"
                  )
                  st.rerun()

          if u_name != "admin":
            if st.button(
                "🗑️ このアカウントを削除する", key=f"del_u_{u_id}"
            ):
              delete_user(u_id)
              st.success(f"ユーザー `{u_disp}` を削除しました。")
              st.rerun()
        st.markdown("---")
