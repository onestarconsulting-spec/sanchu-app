import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from database.db_manager import init_db, insert_teichaku, select_all_teichaku, insert_kankyo, select_all_kankyo, insert_shukaku, select_all_shukaku

# データベースの初期化
init_db()

# 画面全体の基本設定（スマホ対応）
st.set_page_config(page_title="サンチュ栽培管理・収穫予測システム", layout="wide")
st.title("🌱 サンチュ栽培管理・収穫予測システム Ver.2 (Web版)")

# 左側のサイドメニュー（画面切り替えナビゲーション）
menu = st.sidebar.radio(
    "メニュー切り替え",
    ["ホーム・本日の状況", "定植登録", "栽培一覧", "今日の環境入力", "収穫登録", "AI収穫予測", "総合グラフ分析"]
)

# ----------------------------------------------------
# ① ホーム・本日の状況
# ----------------------------------------------------
if menu == "ホーム・本日の状況":
    st.header("【本日の状況】")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="栽培中ロット", value="18 ロット")
    with col2:
        st.metric(label="本日収穫予定", value="3 ロット")
    with col3:
        st.metric(label="要注意ロット", value="2 ロット")
        
    st.info("左側のメニューから、各種データの登録やAI予測の確認を行ってください。")

# ----------------------------------------------------
# ② 定植登録
# ----------------------------------------------------
elif menu == "定植登録":
    st.header("【定植登録フォーム】")
    with st.form("teichaku_form"):
        variety = st.text_input("品種", "サンチュ")
        house = st.text_input("ハウス", "A棟")
        bed = st.text_input("ベッド", "ベッド1")
        plant_date = st.text_input("定植日 (YYYYMMDD)", datetime.now().strftime("%Y%m%d"))
        quantity = st.number_input("株数", min_value=1, value=150)
        target_size = st.text_input("予定収穫サイズ", "180g")
        memo = st.text_area("メモ", "")
        
        submitted = st.form_submit_button("この内容で登録する")
        if submitted:
            insert_teichaku(variety, house, bed, plant_date, int(quantity), target_size, memo)
            st.success("定植データをデータベースに安全に保存しました！")

# ----------------------------------------------------
# ③ 栽培一覧
# ----------------------------------------------------
elif menu == "栽培一覧":
    st.header("【現在栽培中のロット一覧】")
    records = select_all_teichaku()
    
    if not records:
        st.warning("現在栽培中のデータはありません。")
    else:
        for record in records:
            _, variety, house, bed, plant_date, quantity, target_size, _, _ = record
            
            # 日数計算ロジック
            elapsed_days = "ーー"
            clean_date = plant_date.strip().replace("/", "").replace("-", "")
            try:
                d1 = datetime.strptime(clean_date, "%Y%m%d")
                elapsed_days = max(0, (datetime.now() - d1).days)
            except:
                pass
                
            with st.container():
                st.markdown(f"### 📍 {house} - {bed} （{variety}）")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"🌱 株数: {quantity}株  /  📅 定植日: {plant_date}")
                with col2:
                    st.success(f"定植 {elapsed_days} 日目 / 生育率 63%")
                st.markdown("---")

# ----------------------------------------------------
# ④ 今日の環境入力
# ----------------------------------------------------
elif menu == "今日の環境入力":
    st.header("【今日の環境データ入力】")
    with st.form("kankyo_form"):
        date = st.text_input("日付 (YYYYMMDD)", datetime.now().strftime("%Y%m%d"))
        temp = st.number_input("気温 (℃)", value=25.0)
        min_temp = st.number_input("最低気温 (℃)", value=20.0)
        max_temp = st.number_input("最高気温 (℃)", value=30.0)
        water_temp = st.number_input("水温 (℃)", value=20.0)
        dli = st.number_input("日射量 (DLI)", value=15.0)
        ec = st.number_input("EC (dS/m)", value=1.2)
        ph = st.number_input("pH", value=6.5)
        memo = st.text_area("備考", "")
        
        submitted = st.form_submit_button("この内容で保存する")
        if submitted:
            insert_kankyo(date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo)
            st.success("環境データをデータベースに記録しました！")

# ----------------------------------------------------
# ⑤ 収穫登録
# ----------------------------------------------------
elif menu == "収穫登録":
    st.header("【収穫データ登録】")
    with st.form("shukaku_form"):
        shukaku_date = st.text_input("収穫日 (YYYYMMDD)", datetime.now().strftime("%Y%m%d"))
        weight = st.number_input("総重量 (g)", value=350.0)
        quantity = st.number_input("収穫株数", min_value=1, value=15)
        quality = st.selectbox("品質ランク", ["秀", "優", "良", "可"])
        memo = st.text_area("備考", "")
        
        submitted = st.form_submit_button("この内容で登録する")
        if submitted:
            insert_shukaku(shukaku_date, weight, int(quantity), quality, memo)
            st.success("収穫データをデータベースに登録しました！")

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
        _, variety, house, bed, plant_date, quantity, target_size, _, _ = teichaku_records[0]
        
        # 簡易AI気象補正計算
        kankyo_dict = {log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]} for log in kankyo_logs}
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
            predicted_date = (datetime.now() + timedelta(days=remaining_days)).strftime("%Y年%m月%d日")
            
            st.subheader(f"分析対象: {house} - {bed} ({variety})")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("AI判定 生育率", f"{current_growth_rate:.1f} %")
                st.metric("現在の推定重量", f"約 {int(180 * (current_growth_rate/100))} g")
            with col2:
                st.metric("AI予測 収穫適期日", predicted_date)
                st.metric("収穫適期まで", f"あと {remaining_days} 日")
                
            if water_stress_days >= 2:
                st.error(f"⚠️ 水温が22℃を超える日が{water_stress_days}日ありました。生育が通常より遅れ気味です。")
            else:
                st.success("🌱 現在、サンチュは極めて順調なペースで育っています。")
        except Exception as e:
            st.error(f"日付の計算でエラーが発生しました。入力形式を確認してください。({e})")

# ----------------------------------------------------
# ⑦ 総合グラフ分析
# ----------------------------------------------------
elif menu == "総合グラフ分析":
    st.header("【環境データ 総合分析ダッシュボード】")
    logs = select_all_kankyo()
    
    if not logs:
        st.warning("表示する環境データがまだありません。")
    else:
        logs.reverse()
        df = pd.DataFrame(logs, columns=["id", "date", "temp", "min_temp", "max_temp", "water_temp", "dli", "ec", "ph", "memo", "created_at"])
        
        # 横軸用の綺麗な日付を作成
        df["display_date"] = df["date"].apply(lambda x: x[4:6] + "/" + x[6:8] if len(x)==8 else x)
        
        # 気温・水温グラフ
        st.subheader("1. 気温・水温の推移")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df["display_date"], df["temp"], marker="o", label="Air Temp", color="#4caf50")
        ax.plot(df["display_date"], df["water_temp"], marker="s", label="Water Temp", color="#2196f3")
        ax.set_ylabel("Temperature (°C)")
        ax.legend()
        st.pyplot(fig)
        
        # DLIグラフ
        st.subheader("2. 日射量(DLI)の推移")
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.bar(df["display_date"], df["dli"], color="#ff9800", alpha=0.7)
        ax2.set_ylabel("DLI (mol/m²/d)")
        st.pyplot(fig2)