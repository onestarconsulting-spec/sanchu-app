import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime

# -----------------------------------------------------------------------------
# 1. ページ基本設定
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="水耕栽培管理・収穫予測システム",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 水耕栽培管理・収穫予測システム")

# -----------------------------------------------------------------------------
# 2. 日付・表示期間の動的計算（自動更新処理）
# -----------------------------------------------------------------------------
today = datetime.date.today()

# 今月の表記と開始・終了日
this_month_name = f"今月 ({today.year}年{today.month}月)"
this_month_start = today.replace(day=1)

# 先月の表記と開始・終了日
first_day_of_this_month = today.replace(day=1)
last_day_of_last_month = first_day_of_this_month - datetime.timedelta(days=1)
last_month_start = last_day_of_last_month.replace(day=1)
last_month_name = f"先月 ({last_month_start.year}年{last_month_start.month}月)"

# 今年全期間の表記
this_year_name = f"{today.year}年全期間"

# サイドバーで期間を選択
st.sidebar.header("📅 表示期間設定")
period_option = st.sidebar.selectbox(
    "期間を選択してください",
    [
        "直近30日間",
        this_month_name,
        last_month_name,
        this_year_name,
        "全期間",
        "日付で直接指定"
    ]
)

# 選択肢に応じて開始日・終了日を自動判定
if period_option == "直近30日間":
    start_date = today - datetime.timedelta(days=30)
    end_date = today
elif period_option == this_month_name:
    start_date = this_month_start
    end_date = today
elif period_option == last_month_name:
    start_date = last_month_start
    end_date = last_day_of_last_month
elif period_option == this_year_name:
    start_date = datetime.date(today.year, 1, 1)
    end_date = today
elif period_option == "全期間":
    start_date = datetime.date(2020, 1, 1)  # データ存在する最古の日付
    end_date = today
else:  # 日付で直接指定
    col_s, col_e = st.sidebar.columns(2)
    start_date = col_s.date_input("開始日", today - datetime.timedelta(days=30))
    end_date = col_e.date_input("終了日", today)

# -----------------------------------------------------------------------------
# 3. ダミーデータ生成 (※実際の運用ではDBやCSV読み込み処理に差し替えてください)
# -----------------------------------------------------------------------------
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

# メイン環境データ
df_sensor = pd.DataFrame({
    'date': date_range,
    'max_wind': [2.0 + (i % 3) for i in range(len(date_range))],
    'max_instant_wind': [6.0 + (i % 5) for i in range(len(date_range))],
    'pressure': [1000 + (i % 15) for i in range(len(date_range))]
})

# 手動測定データ (データ数が少ないケースのテスト用)
# ※選択期間内に1件程度しか存在しない状況を再現
manual_dates = [pd.Timestamp('2026-07-27')] if pd.Timestamp('2026-07-27') in date_range else [date_range[len(date_range)//2]]
df_manual = pd.DataFrame({
    'date': manual_dates,
    'EC': [1.2],
    'pH': [6.5]
})

# -----------------------------------------------------------------------------
# 4. グラフ描画
# -----------------------------------------------------------------------------

# --- グラフ3: 風速と現地気圧の推移 ---
st.subheader("3. 風速 (m/s) と 現地気圧 (hPa) の推移")

fig_wind = make_subplots(specs=[[{"secondary_y": True}]])
fig_wind.add_trace(
    go.Scatter(x=df_sensor['date'], y=df_sensor['max_wind'], name="最大風速 (m/s)", mode='lines+markers', line=dict(color='#ff5722')),
    secondary_y=False
)
fig_wind.add_trace(
    go.Scatter(x=df_sensor['date'], y=df_sensor['max_instant_wind'], name="最大瞬間風速 (m/s)", mode='lines+markers', line=dict(color='#ffab91', dash='dash')),
    secondary_y=False
)
fig_wind.add_trace(
    go.Scatter(x=df_sensor['date'], y=df_sensor['pressure'], name="現地気圧 (hPa)", mode='lines', line=dict(color='#a855f7', dot='dot')),
    secondary_y=True
)

fig_wind.update_xaxes(range=[start_date, end_date], tickformat="%m/%d")
fig_wind.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=30, b=20))
st.plotly_chart(fig_wind, use_container_width=True)


# --- グラフ4: ハウス培養液 (EC / pH) の推移 [手動測定データのみ] ---
st.subheader("4. ハウス培養液 (EC / pH) の推移 [手動測定データのみ]")

fig_ec_ph = make_subplots(specs=[[{"secondary_y": True}]])

# データのプロット
fig_ec_ph.add_trace(
    go.Scatter(
        x=df_manual['date'], 
        y=df_manual['EC'], 
        name="EC (dS/m)", 
        mode='lines+markers', 
        line=dict(color='#e91e63', width=3),
        marker=dict(size=8)
    ),
    secondary_y=False
)
fig_ec_ph.add_trace(
    go.Scatter(
        x=df_manual['date'], 
        y=df_manual['pH'], 
        name="pH", 
        mode='lines+markers', 
        line=dict(color='#00bcd4', width=3),
        marker=dict(size=8)
    ),
    secondary_y=True
)

# 【重要】データ件数に関わらず、X軸（表示範囲）をメイン期間（start_date 〜 end_date）に完全固定する
fig_ec_ph.update_xaxes(
    range=[start_date, end_date],
    tickformat="%m/%d",
    gridcolor='#333333'
)

fig_ec_ph.update_yaxes(title_text="EC (dS/m)", secondary_y=False, gridcolor='#333333')
fig_ec_ph.update_yaxes(title_text="pH", secondary_y=True, gridcolor='#333333')

fig_ec_ph.update_layout(
    template="plotly_dark",
    height=400,
    margin=dict(l=20, r=20, t=30, b=20)
)

st.plotly_chart(fig_ec_ph, use_container_width=True)
