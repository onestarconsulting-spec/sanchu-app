import customtkinter as ctk
from database.db_manager import insert_kankyo
from datetime import datetime

class KankyoInputWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. 画面の基本設定
        self.title("今日の入力 - サンチュシステム")
        self.geometry("450x650") # 項目が多いので高さを少し高めに
        self.attributes("-topmost", True)

        # 2. 画面のタイトル文字
        self.label = ctk.CTkLabel(
            self, 
            text="【今日の環境データ入力】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=20, weight="bold")
        )
        self.label.pack(pady=15)

        # 3. 入力項目を綺麗に並べるための外枠
        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.pack(pady=10, padx=20, fill="both", expand=True)

        # 設計された9つの入力項目
        items = ["日付", "気温", "最低気温", "最高気温", "水温", "日射量(DLI)", "EC", "pH", "備考"]
        self.entries = {}

        # 今日の日付を「YYYYMMDD」の形式で自動取得
        today_str = datetime.now().strftime("%Y%m%d")

        for i, item in enumerate(items):
            lbl = ctk.CTkLabel(self.form_frame, text=item, font=ctk.CTkFont(size=14, weight="bold"))
            lbl.grid(row=i, column=0, padx=20, pady=8, sticky="w")
            
            entry = ctk.CTkEntry(self.form_frame, width=220)
            entry.grid(row=i, column=1, padx=20, pady=8, sticky="e")
            
            # 日付の入力欄には、最初から「今日の日付」を自動で入力しておく親切設計！
            if item == "日付":
                entry.insert(0, today_str)
                
            self.entries[item] = entry

        # 4. 保存ボタン
        self.btn_save = ctk.CTkButton(
            self, 
            text="この内容で保存する", 
            width=200, 
            height=40, 
            command=self.save_data
        )
        self.btn_save.pack(pady=20)

    # 保存ボタンが押されたときの処理
    def save_data(self):
        # データの回収
        date = self.entries["日付"].get()
        memo = self.entries["備考"].get()
        
        # 数値データは計算に使うので、安全に小数（float）に変換します
        def to_float(val):
            try:
                return float(val)
            except ValueError:
                return 0.0 # 空欄や文字が入っていたら安全のために0.0にする

        temp = to_float(self.entries["気温"].get())
        min_temp = to_float(self.entries["最低気温"].get())
        max_temp = to_float(self.entries["最高気温"].get())
        water_temp = to_float(self.entries["水温"].get())
        dli = to_float(self.entries["日射量(DLI)"].get())
        ec = to_float(self.entries["EC"].get())
        ph = to_float(self.entries["pH"].get())

        # データベースへ保存！
        insert_kankyo(date, temp, min_temp, max_temp, water_temp, dli, ec, ph, memo)
        
        print("\n===== 環境データをデータベースに記録しました =====")
        print(f"日付: {date} | 気温: {temp}℃ | 水温: {water_temp}℃ | DLI: {dli}")
        print("================================================")
        
        self.destroy()