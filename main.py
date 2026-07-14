import customtkinter as ctk
from screens.teichaku import TeichakuWindow
from screens.saibai_ichiran import SaibaiIchiranWindow
from screens.kankyo_input import KankyoInputWindow
from screens.shukaku_input import ShukakuInputWindow
from screens.yosoku import YosokuWindow
from screens.data_kanri import DataKanriWindow
# ★ いま作ったグラフ分析画面を読み込む
from screens.graph_analysis import GraphAnalysisWindow
from database.db_manager import init_db

ctk.set_appearance_mode("System")  
ctk.set_default_color_theme("green")  

class SanchuApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("サンチュ栽培管理・収穫予測システム Ver.1")
        self.geometry("600x640") 

        # タイトル
        self.title_label = ctk.CTkLabel(
            self, 
            text="サンチュ栽培管理・収穫予測システム", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=24, weight="bold")
        )
        self.title_label.pack(pady=20)

        # 本日の状況
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(pady=20, fill="x", padx=40)

        self.status_title = ctk.CTkLabel(self.info_frame, text="【本日の状況】", font=ctk.CTkFont(size=16, weight="bold"))
        self.status_title.pack(pady=5)

        self.status_detail = ctk.CTkLabel(
            self.info_frame, 
            text="栽培中：18ロット  |  本日収穫予定：3ロット  |  要注意：2ロット", 
            font=ctk.CTkFont(size=14)
        )
        self.status_detail.pack(pady=10)

        # メニューボタンの配置
        self.menu_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.menu_frame.pack(pady=15)

        # 【1段目】
        self.btn_teichaku = ctk.CTkButton(self.menu_frame, text="定植登録", width=160, height=40, command=self.open_teichaku)
        self.btn_teichaku.grid(row=0, column=0, padx=15, pady=10)

        self.btn_ichiran = ctk.CTkButton(self.menu_frame, text="栽培一覧", width=160, height=40, command=self.open_ichiran)
        self.btn_ichiran.grid(row=0, column=1, padx=15, pady=10)

        # 【2段目】
        self.btn_input = ctk.CTkButton(self.menu_frame, text="今日の入力", width=160, height=40, command=self.open_kankyo)
        self.btn_input.grid(row=1, column=0, padx=15, pady=10)

        self.btn_shukaku = ctk.CTkButton(self.menu_frame, text="収穫登録", width=160, height=40, command=self.open_shukaku)
        self.btn_shukaku.grid(row=1, column=1, padx=15, pady=10)

        # 【3段目】
        self.btn_yosoku = ctk.CTkButton(self.menu_frame, text="収穫予測", width=160, height=40, command=self.open_yosoku)
        self.btn_yosoku.grid(row=2, column=0, padx=15, pady=10)

        # ★ 「グラフ分析」ボタンに、画面起動コマンドを割り当てました！
        self.btn_analysis = ctk.CTkButton(self.menu_frame, text="グラフ分析", width=160, height=40, command=self.open_analysis)
        self.btn_analysis.grid(row=2, column=1, padx=15, pady=10)

        # 【4段目】
        self.btn_data = ctk.CTkButton(self.menu_frame, text="データ管理", width=160, height=40, command=self.open_data_kanri)
        self.btn_data.grid(row=3, column=0, padx=15, pady=10)

        self.btn_setting = ctk.CTkButton(self.menu_frame, text="設定", width=160, height=40)
        self.btn_setting.grid(row=3, column=1, padx=15, pady=10)

    def open_teichaku(self):
        teichaku_win = TeichakuWindow(self)
        teichaku_win.focus()

    def open_ichiran(self):
        ichiran_win = SaibaiIchiranWindow(self)
        ichiran_win.focus()

    def open_kankyo(self):
        kankyo_win = KankyoInputWindow(self)
        kankyo_win.focus()

    def open_shukaku(self):
        shukaku_win = ShukakuInputWindow(self)
        shukaku_win.focus()

    def open_yosoku(self):
        yosoku_win = YosokuWindow(self)
        yosoku_win.focus()

    def open_data_kanri(self):
        data_win = DataKanriWindow(self)
        data_win.focus()

    # ★ グラフ分析画面を開く
    def open_analysis(self):
        analysis_win = GraphAnalysisWindow(self)
        analysis_win.focus()

if __name__ == "__main__":
    init_db()
    app = SanchuApp()
    app.mainloop()