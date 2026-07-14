import customtkinter as ctk
from database.db_manager import insert_shukaku
from datetime import datetime

class ShukakuInputWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. 画面の基本設定
        self.title("収穫登録 - サンチュシステム")
        self.geometry("450x500")
        self.attributes("-topmost", True)

        # 2. タイトル
        self.label = ctk.CTkLabel(
            self, 
            text="【今日の収穫データ登録】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=20, weight="bold")
        )
        self.label.pack(pady=15)

        # 3. 入力フォームの外枠
        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.pack(pady=10, padx=20, fill="both", expand=True)

        # 今日の日付
        today_str = datetime.now().strftime("%Y%m%d")

        # 収穫日
        self.lbl_date = ctk.CTkLabel(self.form_frame, text="収穫日", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_date.grid(row=0, column=0, padx=20, pady=12, sticky="w")
        self.entry_date = ctk.CTkEntry(self.form_frame, width=220)
        self.entry_date.grid(row=0, column=1, padx=20, pady=12, sticky="e")
        self.entry_date.insert(0, today_str)

        # 重量(g)
        self.lbl_weight = ctk.CTkLabel(self.form_frame, text="総重量 (g)", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_weight.grid(row=1, column=0, padx=20, pady=12, sticky="w")
        self.entry_weight = ctk.CTkEntry(self.form_frame, width=220)
        self.entry_weight.grid(row=1, column=1, padx=20, pady=12, sticky="e")

        # 株数
        self.lbl_qty = ctk.CTkLabel(self.form_frame, text="収穫株数", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_qty.grid(row=2, column=0, padx=20, pady=12, sticky="w")
        self.entry_qty = ctk.CTkEntry(self.form_frame, width=220)
        self.entry_qty.grid(row=2, column=1, padx=20, pady=12, sticky="e")

        # 品質 (秀・優・良・可) - ドロップダウンで選べる親切設計！
        self.lbl_quality = ctk.CTkLabel(self.form_frame, text="品質ランク", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_quality.grid(row=3, column=0, padx=20, pady=12, sticky="w")
        self.menu_quality = ctk.CTkOptionMenu(self.form_frame, values=["秀", "優", "良", "可"], width=220)
        self.menu_quality.grid(row=3, column=1, padx=20, pady=12, sticky="e")

        # 備考
        self.lbl_memo = ctk.CTkLabel(self.form_frame, text="備考", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_memo.grid(row=4, column=0, padx=20, pady=12, sticky="w")
        self.entry_memo = ctk.CTkEntry(self.form_frame, width=220)
        self.entry_memo.grid(row=4, column=1, padx=20, pady=12, sticky="e")

        # 4. 保存ボタン
        self.btn_save = ctk.CTkButton(
            self, 
            text="この内容で登録する", 
            width=200, 
            height=40, 
            command=self.save_data
        )
        self.btn_save.pack(pady=20)

    # データを保存する動き
    def save_data(self):
        shukaku_date = self.entry_date.get()
        quality = self.menu_quality.get()
        memo = self.entry_memo.get()

        # 数値の安全な変換
        try:
            weight = float(self.entry_weight.get())
        except ValueError:
            weight = 0.0

        try:
            quantity = int(self.entry_qty.get())
        except ValueError:
            quantity = 0

        # データベースへ登録
        insert_shukaku(shukaku_date, weight, quantity, quality, memo)

        print("\n===== 収穫データをデータベースに登録しました =====")
        print(f"収穫日: {shukaku_date} | 重量: {weight}g | 株数: {quantity} | 品質: {quality}")
        print("==================================================")

        self.destroy()