import customtkinter as ctk
# ★ 削除用の関数（delete_kankyo_by_date）を新しく読み込みます
from database.db_manager import export_all_to_excel, delete_kankyo_by_date
import os

class DataKanriWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. 画面の基本設定（削除機能が増えたので、高さを500に広げました）
        self.title("データ管理 - サンチュシステム")
        self.geometry("400x500")
        self.attributes("-topmost", True)

        # 2. タイトル
        self.label = ctk.CTkLabel(
            self, 
            text="【データ管理・外部連携】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=20, weight="bold")
        )
        self.label.pack(pady=20)

        # === 【エリアA：Excel出力】 ===
        self.excel_frame = ctk.CTkFrame(self)
        self.excel_frame.pack(pady=10, padx=20, fill="x")

        self.info_lbl = ctk.CTkLabel(
            self.excel_frame, 
            text="データベースの全データをExcelへ出力します。",
            font=ctk.CTkFont(size=13)
        )
        self.info_lbl.pack(pady=10)

        self.btn_excel = ctk.CTkButton(
            self.excel_frame, 
            text="Excelへ出力する", 
            width=200, 
            fg_color="#2e7d32", 
            hover_color="#1b5e20",
            command=self.trigger_excel_export
        )
        self.btn_excel.pack(pady=10)

        # === 【エリアB：データ削除（新設！）】 ===
        self.delete_frame = ctk.CTkFrame(self)
        self.delete_frame.pack(pady=15, padx=20, fill="x")

        self.delete_lbl = ctk.CTkLabel(
            self.delete_frame, 
            text="【環境データの削除】\n間違えて入力した日付（例: 20260714）を入力してください。",
            font=ctk.CTkFont(size=12)
        )
        self.delete_lbl.pack(pady=10)

        # 日付を入力するボックス
        self.entry_delete_date = ctk.CTkEntry(self.delete_frame, placeholder_text="例：20260714", width=180)
        self.entry_delete_date.pack(pady=5)

        # 削除ボタン（危険な操作なので「赤色」にして警告します！）
        self.btn_delete = ctk.CTkButton(
            self.delete_frame, 
            text="この日のデータを削除する", 
            width=200, 
            fg_color="#d32f2f", # 警告の赤色
            hover_color="#c2185b",
            command=self.trigger_data_delete
        )
        self.btn_delete.pack(pady=10)

        # 完了メッセージ用ラベル
        self.status_lbl = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13))
        self.status_lbl.pack(pady=10)

    def trigger_excel_export(self):
        filename = "サンチュ栽培データ.xlsx"
        export_all_to_excel(filename)
        self.status_lbl.configure(text=f"成功！「{filename}」を作成しました。", text_color="#81c784")

    # ★ 新設：削除ボタンが押されたときの処理
    def trigger_data_delete(self):
        target_date = self.entry_delete_date.get().strip()
        
        if not target_date:
            self.status_lbl.configure(text="エラー：日付を入力してください。", text_color="#ff8a80")
            return

        # データベースから削除を実行！
        delete_kankyo_by_date(target_date)
        
        # 画面に成功メッセージを出す
        self.status_lbl.configure(text=f"日付 {target_date} の環境データを削除しました。", text_color="#ff8a80")
        
        # 入力欄をきれいにする
        self.entry_delete_date.delete(0, "end")