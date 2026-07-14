import customtkinter as ctk
from database.db_manager import select_all_teichaku
from datetime import datetime

class SaibaiIchiranWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.title("栽培一覧 - サンチュシステム")
        self.geometry("550x600")
        self.attributes("-topmost", True)

        self.label = ctk.CTkLabel(
            self, 
            text="【現在栽培中のロット一覧】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=20, weight="bold")
        )
        self.label.pack(pady=15)

        self.scroll_frame = ctk.CTkScrollableFrame(self, width=500, height=480)
        self.scroll_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.load_data()

    def load_data(self):
        records = select_all_teichaku()

        if not records:
            no_data_label = ctk.CTkLabel(
                self.scroll_frame, 
                text="現在栽培中のデータはありません。\n「定植登録」からデータを追加してください。", 
                font=ctk.CTkFont(size=14)
            )
            no_data_label.pack(pady=50)
            return

        for record in records:
            _, variety, house, bed, plant_date, quantity, target_size, _, _ = record

            # ★ どんな日付入力でも解釈しようとする「賢い判定処理」
            elapsed_days = None
            clean_date = plant_date.strip().replace("/", "-") # 余計な空白を消してスラッシュをハイフンに変換

            # 試したい日付のパターンリスト
            date_formats = ["%Y-%m-%d", "%Y%m%d"] 
            
            for fmt in date_formats:
                try:
                    d1 = datetime.strptime(clean_date, fmt)
                    d2 = datetime.now()
                    elapsed_days = (d2 - d1).days
                    break # うまく解釈できたらループを抜ける
                except ValueError:
                    continue # ダメなら次のパターンを試す

            # 計算結果のテキスト作成
            if elapsed_days is not None:
                day_text = f"定植 {max(0, elapsed_days)} 日目"
            else:
                day_text = "定植 -- 日目"

            # カード（見た目）の作成
            card = ctk.CTkFrame(self.scroll_frame, corner_radius=10)
            card.pack(pady=10, padx=5, fill="x")

            info_text = f"📍 {house} - {bed} \n🌱 品種: {variety} ({quantity} 株)\n📅 定植日: {plant_date}"
            lbl_info = ctk.CTkLabel(card, text=info_text, font=ctk.CTkFont(size=14), justify="left")
            lbl_info.pack(side="left", padx=20, pady=15)

            status_text = f"{day_text}\n生育率 63%\nあと 11 日"
            lbl_status = ctk.CTkLabel(
                card, 
                text=status_text, 
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#1b5e20",
                corner_radius=8,
                padx=12,
                pady=8
            )
            lbl_status.pack(side="right", padx=20, pady=15)