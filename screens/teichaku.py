import customtkinter as ctk
# ★ さっき作った database フォルダの db_manager から「保存する機能」を読み込む
from database.db_manager import insert_teichaku

class TeichakuWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.title("定植登録 - サンチュシステム")
        self.geometry("450x600")  
        self.attributes("-topmost", True)

        self.label = ctk.CTkLabel(
            self, 
            text="【定植登録フォーム】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=20, weight="bold")
        )
        self.label.pack(pady=15)

        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.pack(pady=10, padx=20, fill="both", expand=True)

        items = ["品種", "ハウス", "ベッド", "定植日", "株数", "予定収穫サイズ", "メモ"]
        self.entries = {}

        for i, item in enumerate(items):
            lbl = ctk.CTkLabel(self.form_frame, text=item, font=ctk.CTkFont(size=14, weight="bold"))
            lbl.grid(row=i, column=0, padx=20, pady=10, sticky="w")
            
            entry = ctk.CTkEntry(self.form_frame, width=220)
            entry.grid(row=i, column=1, padx=20, pady=10, sticky="e")
            
            self.entries[item] = entry

        self.btn_register = ctk.CTkButton(
            self, 
            text="この内容で登録する", 
            width=200, 
            height=40, 
            command=self.register_data
        )
        self.btn_register.pack(pady=20)

    # ★ 登録ボタンを押したときの動き
    def register_data(self):
        # 各ボックスから、入力された文字を回収する
        variety = self.entries["品種"].get()
        house = self.entries["ハウス"].get()
        bed = self.entries["ベッド"].get()
        plant_date = self.entries["定植日"].get()
        quantity_str = self.entries["株数"].get()
        target_size = self.entries["予定収穫サイズ"].get()
        memo = self.entries["メモ"].get()

        # 株数は「数字（整数）」としてデータベースに入れたいので、変換する
        try:
            quantity = int(quantity_str)
        except ValueError:
            quantity = 0  # もし数字以外が打たれていたら、安全のために 0 にしておく

        # ★ 【最重要】データベースにデータを保存する！
        insert_teichaku(variety, house, bed, plant_date, quantity, target_size, memo)
        
        print("\n===== データをデータベースに安全に保存しました！ =====")
        print(f"品種: {variety} / ハウス: {house} / 株数: {quantity}株")
        print("====================================================")
        
        self.destroy()