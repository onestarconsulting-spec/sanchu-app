import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from database.db_manager import (
    init_db, 
    insert_teichaku, 
    select_all_teichaku, 
    insert_kankyo, 
    select_all_kankyo, 
    insert_shukaku, 
    select_all_shukaku,
    get_connection
)

# データベースの初期化
init_db()

# データの削除を処理する裏方の命令
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
        st.error(f"削除中にエラーが発生しました: {e}")
        return False

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
# ② 定植登録（ドロップダウン＆選択式へ大改造）
# ----------------------------------------------------
elif menu == "定植登録":
    st.header("【定植登録フォーム】")
    with st.form("teichaku_form"):
        # 品種・ハウス・ライン・ベッドをすべて選択式に変更
        variety = st.selectbox("品種", ["サンチュ", "サニーレタス", "グリーンカール", "三つ葉"])
        house = st.selectbox("ハウス", ["Ⅰ棟", "Ⅱ棟", "Ⅲ棟", "Ⅳ棟"])
        line = st.selectbox("ライン", ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T"])
        bed = st.selectbox("ベッド", [f"{i}番ベッド" for i in range(1, 21)])
        
        # 日付を入力ではなくカレンダー選択式に変更
        plant_date_val = st.date_input("定植日", datetime.now())
        quantity = st.number_input("株数", min_value=1, value=150)
        
        # 予定収穫サイズを数字入力（単位グラム）に変更
        target_size_val = st.number_input("予定収穫サイズ (g)", min_value=1, value=180)
        memo = st.text_area("メモ", "")
        
        submitted = st.form_submit_button("この内容で登録する")
        if submitted:
            # データベースを壊さないよう、ハウスとラインを自動で合体して保存します
            full_house = f"{house} ({line}ライン)"
            str_plant_date = plant_date_val.strftime("%Y%m%d")
            str_target_size = f"{target_size_val}g"
            
            insert_teichaku(variety, full_house, bed, str_plant_date, int(quantity), str_target_size, memo)
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
        df_teichaku = pd.DataFrame(records)
        csv_teichaku = df_teichaku.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 定植一覧データをCSVダウンロード",
            data=csv_teichaku,
            file_name=f"sanchu_lots_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        st.markdown("---")

        for record in records:
            record_id = record[0]
            variety = record[1]
            house = record[2]
            bed = record[3]
            plant_date = record[4]
            quantity = record[5]
            target_size = record[6]
            
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
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.write(f"🌱 株数: {quantity}株  /  📅 定植日: {plant_date}  /  🎯 予定サイズ: {target_size}")
                with col2:
                    st.success(f"定植 {elapsed_days} 日目 / 生育率 63%")
                with col3:
                    if st.button("🗑️ このロットを削除", key=f"del_lot_{record_id}"):
                        if delete_record("teichaku", record_id):
                            st.success("データを削除しました！")
                            st.rerun()
                st.markdown("---")

# ----------------------------------------------------
# ④ 今日の環境入力（前日の値を自動引き継ぎ＆選択式）
# ----------------------------------------------------
elif menu == "今日の環境入力":
    st.header("【今日の環境データ入力】")
    
    # データベースから最新の（前回の）データを自動で読み込んで初期値にします
    kankyo_logs = select_all_kankyo()
    if kankyo_logs:
        last = kankyo_logs[0] # 一番新しい1件
        def_temp = float(last[2])
        def_min = float(last[3])
        def_max = float(last[4])
        def_water = float(last[5])
        def_dli = float(last[6])
        def_ec = float(last[7])
        def_ph = float(last[8])
    else:
        # まだデータが1件もない場合の標準の初期値
        def_temp, def_min, def_max, def_water, def_dli, def_ec, def_ph = 25.0, 20.0, 30.0, 20.0, 15.0, 1.2, 6.5

    with st.form("kankyo_form"):
        # 日付を選択式に変更
        date_val = st.date_input("日付", datetime.now())
        
        # すべてに前日の数値をセット。右側に自動で「＋」「ー」の上下ボタンがつきます
        temp = st.number_input("気温 (℃)", value=def_temp, step=0.1)
        min_temp = st.number_input("最低気温 (℃)", value=def_min, step=0.1)
        max_temp = st.number_input("最高気温 (℃)", value=def_max, step=0.1)
        water_temp = st.number_input("水温 (℃)", value=def_water, step=0.1)
        dli = st.number_input("日射量 (DLI)", value=def_dli, step=0.1)
        ec = st.number_input("EC (dS/m)", value=def_ec, step=0.1)
        ph = st.number_input("pH", value=def_ph, step=0.1)
        memo = st.text_area("備考", "")
        
        submitted = st.form_submit_button("この内容で保存する")
        if submitted:
            str_date = date_val.strftime("%Y%m%d")
            insert_kankyo(str_date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo)
            st.success("環境データをデータベースに記録しました！")

# ----------------------------------------------------
# ⑤ 収穫登録（選択式へ変更）
# ----------------------------------------------------
elif menu == "収穫登録":
    st.header("【収穫データ登録】")
    with st.form("shukaku_form"):
        # 収穫日を選択式に変更
        shukaku_date_val = st.date_input("収穫日", datetime.now())
        weight = st.number_input("総重量 (g)", value=350.0)
        quantity = st.number_input("収穫株数", min_value=1, value=15)
        quality = st.selectbox("品質ランク", ["秀", "優", "良", "可"])
        memo = st.text_area("備考", "")
        
        submitted = st.form_submit_button("この内容で登録する")
        if submitted:
            str_shukaku_date = shukaku_date_val.strftime("%Y%m%d")
            insert_shukaku(str_shukaku_date, weight, int(quantity), quality, memo)
            st.success("収穫データをデータベースに登録しました！")

# ----------------------------------------------------
# ⑥ AI収穫予測（データが溜まっても見やすい表形式へ大改造！）
# ----------------------------------------------------
elif menu == "AI収穫予測":
    st.header("【AI気象補正 収穫予測シミュレーション（一覧表）】")
    teichaku_records = select_all_teichaku()
    kankyo_logs = select_all_kankyo()
    
    if not teichaku_records:
        st.warning("予測対象となる定植データがありません。")
    else:
        kankyo_dict = {log[1]: {"temp": log[2], "water_temp": log[5], "dli": log[6]} for log in kankyo_logs}
        
        # 表にまとめるためのデータを溜める空のリスト
        prediction_table_data = []
        
        for record in teichaku_records:
            _, variety, house, bed, plant_date, quantity, target_size = record[0], record[1], record[2], record[3], record[4], record[5], record[6]
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
                        f_water = 0.8 if day["water_temp"] > 22.0 else 1.0
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
                
                # 1つずつのロットデータを綺麗に整理してリストに追加
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
            # 溜まったデータを一発で綺麗な「Excel風の表」に変換して表示します
            df_prediction = pd.DataFrame(prediction_table_data)
            st.dataframe(df_prediction, use_container_width=True, hide_index=True)
            st.success("💡 全ロットの予測結果を1つの表にまとめました。データが増えても自動でスクロールバーがつき、スッキリ確認できます。")
        else:
            st.error("予測データの解析に失敗しました。定植日の形式を確認してください。")

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
        
        csv_kankyo = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 環境データをCSVとしてダウンロード",
            data=csv_kankyo,
            file_name=f"sanchu_kankyo_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
        st.markdown("---")

        df["display_date"] = df["date"].apply(lambda x: x[4:6] + "/" + x[6:8] if len(x)==8 else x)
        
        st.subheader("1. 気温・水温の推移")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df["display_date"], df["temp"], marker="o", label="Air Temp", color="#4caf50")
        ax.plot(df["display_date"], df["water_temp"], marker="s", label="Water Temp", color="#2196f3")
        ax.set_ylabel("Temperature (°C)")
        ax.legend()
        st.pyplot(fig)
        
        st.subheader("2. 日射量(DLI)の推移")
        fig2, ax2 = plt.subplots(figsize=(10, 3))
        ax2.bar(df["display_date"], df["dli"], color="#ff9800", alpha=0.7)
        ax2.set_ylabel("DLI (mol/m²/d)")
        st.pyplot(fig2)
