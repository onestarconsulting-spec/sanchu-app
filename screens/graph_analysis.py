import customtkinter as ctk
from database.db_manager import select_all_kankyo
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime, timedelta

# グラフ全体の文字サイズやフォントの設定
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

class GraphAnalysisWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. 画面の基本設定（全グラフを並べるため、画面サイズを大きく広げました）
        self.title("総合分析ダッシュボード - サンチュシステム")
        self.geometry("850x850")
        self.attributes("-topmost", True)

        # 2. タイトル文字
        self.label = ctk.CTkLabel(
            self, 
            text="【環境データ 総合分析ダッシュボード】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=20, weight="bold")
        )
        self.label.pack(pady=15)

        # 3. 期間指定エリア（新設！）
        self.filter_frame = ctk.CTkFrame(self)
        self.filter_frame.pack(pady=10, padx=20, fill="x")

        # デフォルト表示期間として「2週間前 ～ 今日」を自動セットする親切設計
        today_str = datetime.now().strftime("%Y%m%d")
        two_weeks_ago_str = (datetime.now() - timedelta(days=14)).strftime("%Y%m%d")

        self.lbl_start = ctk.CTkLabel(self.filter_frame, text="開始日:", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_start.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_start = ctk.CTkEntry(self.filter_frame, width=120, placeholder_text="YYYYMMDD")
        self.entry_start.grid(row=0, column=1, padx=5, pady=10)
        self.entry_start.insert(0, two_weeks_ago_str) # 初期値セット

        self.lbl_end = ctk.CTkLabel(self.filter_frame, text=" ～  終了日:", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_end.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        
        self.entry_end = ctk.CTkEntry(self.filter_frame, width=120, placeholder_text="YYYYMMDD")
        self.entry_end.grid(row=0, column=3, padx=5, pady=10)
        self.entry_end.insert(0, today_str) # 初期値セット

        # 期間適用ボタン
        self.btn_apply = ctk.CTkButton(
            self.filter_frame, 
            text="期間を適用", 
            width=120, 
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self.refresh_all_graphs
        )
        self.btn_apply.grid(row=0, column=4, padx=20, pady=10)

        # 4. 全グラフを縦に並べてスクロールできるエリア
        self.scroll_frame = ctk.CTkScrollableFrame(self, width=800, height=700)
        self.scroll_frame.pack(pady=10, padx=20, fill="both", expand=True)

        self.canvases = []
        
        # 初回起動時にグラフを自動描画
        self.refresh_all_graphs()

    def refresh_all_graphs(self):
        """指定された期間のデータを抽出し、4つのグラフをすべて同時に再描画する関数"""
        # 1. すでに表示されている古いグラフがあれば画面から完全に削除する（メモリ解放）
        for c in self.canvases:
            c.get_tk_widget().destroy()
        self.canvases.clear()

        # スクロール枠の中を一度きれいに掃除する
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # 2. データベースから環境データを全件取得
        logs = select_all_kankyo()
        if not logs:
            lbl_nodata = ctk.CTkLabel(
                self.scroll_frame, 
                text="グラフに表示するデータがまだありません。\n「今日の入力」から環境データを登録してください。",
                font=ctk.CTkFont(size=14)
            )
            lbl_nodata.pack(pady=150)
            return

        # 3. 画面から入力された「開始日」「終了日」を読み取る
        start_date = self.entry_start.get().strip()
        end_date = self.entry_end.get().strip()

        # 4. 期間に合致するデータだけをフィルタリングする（文字の大小比較で簡単・高速に判定）
        filtered_logs = []
        for log in logs:
            log_date = log[1] # YYYYMMDD形式のテキスト
            if (not start_date or log_date >= start_date) and (not end_date or log_date <= end_date):
                filtered_logs.append(log)

        # 指定期間内にデータがない場合の安全処理
        if not filtered_logs:
            lbl_nodata = ctk.CTkLabel(
                self.scroll_frame, 
                text="指定された期間内に環境データが見つかりませんでした。\n日付を変更して再度お試しください。",
                font=ctk.CTkFont(size=14),
                text_color="#ff8a80"
            )
            lbl_nodata.pack(pady=150)
            return

        # グラフが左から右へ時系列順（古い順）に流れるようにデータを反転
        filtered_logs.reverse()

        # 5. 各種環境データをグラフ用の配列へ分解流し込み
        dates = [log[1] for log in filtered_logs]
        x_labels = []
        for d in dates:
            try:
                # 表記を「07/14」のように短くして横軸をスッキリさせる
                x_labels.append(datetime.strptime(d, "%Y%m%d").strftime("%m/%d"))
            except:
                x_labels.append(d)

        temps = [log[2] for log in filtered_logs]
        water_temps = [log[5] for log in filtered_logs]
        dlis = [log[6] for log in filtered_logs]
        ecs = [log[7] for log in filtered_logs]
        phs = [log[8] for log in filtered_logs]

        # 6. グラフをきれいに埋め込むための「カード生成用」の内部共通処理
        def draw_graph_card(title, ylabel, x_data, y_data, graph_type="plot", color="#4caf50", y_data2=None, ylabel2=None, color2=None):
            card = ctk.CTkFrame(self.scroll_frame)
            card.pack(pady=15, padx=10, fill="x")

            fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=100)
            fig.patch.set_facecolor('#2b2b2b')
            ax.set_facecolor('#2b2b2b')

            ax.tick_params(colors='white')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.title.set_color('white')
            for spine in ax.spines.values():
                spine.set_color('gray')

            ax.set_title(title, fontsize=14, weight="bold")
            ax.set_ylabel(ylabel)
            ax.grid(True, color='gray', linestyle='--', alpha=0.3)

            # グラフのタイプ別処理
            if graph_type == "plot":
                ax.plot(x_data, y_data, marker='o', color=color, linewidth=2)
            elif graph_type == "bar":
                ax.bar(x_data, y_data, color=color, alpha=0.7)
            elif graph_type == "double":
                # EC用の左軸
                ax.plot(x_data, y_data, marker='o', color=color, linewidth=2)
                ax.set_ylabel(ylabel, color=color)
                ax.tick_params(axis='y', labelcolor=color)
                # pH用の右軸（W軸）
                ax2 = ax.twinx()
                ax2.plot(x_data, y_data2, marker='s', color=color2, linewidth=2)
                ax2.set_ylabel(ylabel2, color=color2)
                ax2.tick_params(axis='y', labelcolor=color2)
                ax2.spines['right'].set_color('gray')

            fig.tight_layout()
            
            # 画面への埋め込み
            canvas = FigureCanvasTkAgg(fig, master=card)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
            self.canvases.append(canvas)
            plt.close(fig)

        # 7. 4つのグラフカードを一発でまとめて縦に並べる
        draw_graph_card("1. Air Temperature Trend", "Temp (°C)", x_labels, temps, "plot", "#4caf50")
        draw_graph_card("2. Water Temperature Trend", "Water Temp (°C)", x_labels, water_temps, "plot", "#2196f3")
        draw_graph_card("3. Daily Light Integral (DLI) Trend", "DLI (mol/m²/d)", x_labels, dlis, "bar", "#ff9800")
        draw_graph_card("4. Nutrient Solution (EC & pH) Trend", "EC (dS/m)", x_labels, ecs, "double", "#e91e63", phs, "pH", "#00bcd4")