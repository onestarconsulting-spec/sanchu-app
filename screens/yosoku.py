import customtkinter as ctk
from database.db_manager import select_all_teichaku, select_all_kankyo
from datetime import datetime, timedelta

class YosokuWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.title("AI収穫予測 - サンチュシステム")
        self.geometry("500x630")
        self.attributes("-topmost", True)

        self.label = ctk.CTkLabel(
            self, 
            text="【AI気象補正 収穫予測シミュレーション】", 
            font=ctk.CTkFont(family="Hiragino Kaku Gothic ProN", size=18, weight="bold")
        )
        self.label.pack(pady=15)

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=10, padx=20, fill="both", expand=True)

        self.calculate_ai_prediction()

    def calculate_ai_prediction(self):
        # 1. データベースから最新の定植ロットを取得
        teichaku_records = select_all_teichaku()
        if not teichaku_records:
            lbl_nodata = ctk.CTkLabel(
                self.main_frame, 
                text="予測対象となる定植データがありません。\n先に「定植登録」を行ってください。",
                font=ctk.CTkFont(size=14)
            )
            lbl_nodata.pack(pady=50)
            return

        _, variety, house, bed, plant_date, quantity, target_size, _, _ = teichaku_records[0]

        # 日付フォーマットのクレンジング (例: "2026/07/10" や "2026-07-10" を "20260710" に統一)
        plant_date_clean = plant_date.strip().replace("/", "").replace("-", "")
        
        try:
            start_dt = datetime.strptime(plant_date_clean, "%Y%m%d")
        except ValueError:
            lbl_error = ctk.CTkLabel(self.main_frame, text="定植日の日付形式が不正です。")
            lbl_error.pack(pady=50)
            return

        # 2. データベースから全環境データを取得
        kankyo_logs = select_all_kankyo()
        
        # ログを日付キーで検索しやすいように辞書型に変換
        # kankyo_dict["20260714"] = (temp, water_temp, dli) などの形式にする
        kankyo_dict = {}
        for log in kankyo_logs:
            # log[1]が日付、log[2]気温、log[5]水温、log[6]DLI
            kankyo_dict[log[1]] = {
                "temp": log[2],
                "water_temp": log[5],
                "dli": log[6]
            }

        # 3. 定植日から今日までの生育シミュレーションを1日ずつ実行
        total_growth = 0.0
        current_dt = start_dt
        today_dt = datetime.now()
        elapsed_days = (today_dt - start_dt).days

        # 分析用の状況メモ用変数
        water_stress_days = 0
        good_sunlight_days = 0
        total_simulated_days = 0
        
        # 直近5日間の成長スピードを記録するリスト（未来予測の傾きとして使用）
        recent_growth_rates = []

        while current_dt <= today_dt:
            date_str = current_dt.strftime("%Y%m%d")
            total_simulated_days += 1

            # 標準の1日あたり成長ペース (30日で100%に達すると仮定 = 3.33%)
            base_daily_growth = 100.0 / 30.0

            # その日の記録が環境データ(kankyo_dict)にあるか確認
            if date_str in kankyo_dict:
                day_data = kankyo_dict[date_str]
                
                # A. 気温補正因子 (基準を20℃とし、比例させる。最低0.5倍〜最大1.5倍に制限)
                f_temp = max(0.5, min(1.5, day_data["temp"] / 20.0))
                
                # B. 水温ストレス補正因子 (水温が22℃を超えると根にストレスがかかり成長が遅れる)
                if day_data["water_temp"] > 22.0:
                    f_water = 0.8  # 成長スピードが20%低下
                    water_stress_days += 1
                else:
                    f_water = 1.0

                # C. 日射量(DLI)補正因子 (基準を15とし、最大1.3倍、最低0.7倍に制限)
                f_dli = max(0.7, min(1.3, day_data["dli"] / 15.0))
                if day_data["dli"] > 16.0:
                    good_sunlight_days += 1
            else:
                # 環境データがない日は、通常ペース(補正なし)で進んだと仮定
                f_temp, f_water, f_dli = 1.0, 1.0, 1.0

            # 補正後の今日の成長率を算出
            daily_growth = base_daily_growth * f_temp * f_water * f_dli
            total_growth += daily_growth
            recent_growth_rates.append(daily_growth)

            # 次の日に進む
            current_dt += timedelta(days=1)

        # 現在の生育率（100%を超えないようにする）
        current_growth_rate = min(100.0, total_growth)

        # 4. 未来の収穫予測日を計算する
        # 直近5日間の平均成長スピードを採用（データが少ない場合は過去全日数の平均）
        sub_list = recent_growth_rates[-5:] if len(recent_growth_rates) >= 5 else recent_growth_rates
        avg_daily_growth = sum(sub_list) / len(sub_list) if sub_list else (100.0 / 30.0)
        
        # 安全対策（万が一平均が0以下になったら標準ペースを代入）
        if avg_daily_growth <= 0:
            avg_daily_growth = 100.0 / 30.0

        # あとどれくらい成長が必要か
        remaining_growth = 100.0 - current_growth_rate
        
        # 収穫適期までの必要日数
        remaining_days = int(remaining_growth / avg_daily_growth)
        
        # 予測収穫日
        predicted_date = (today_dt + timedelta(days=remaining_days)).strftime("%Y年%m月%d日")

        # 5. 現在の重量推定 (目標サイズに対する進捗)
        try:
            target_weight = float(''.join(filter(str.isdigit, target_size)))
        except:
            target_weight = 180.0
        current_weight = int(target_weight * (current_growth_rate / 100.0))

        # --- AIアドバイザーの診断メッセージを動的に生成！ ---
        ai_advice = "【AIアドバイザーの分析結果】\n"
        if water_stress_days >= 2:
            ai_advice += f"⚠️ 直近で水温が22℃を超える日が{water_stress_days}日ありました。根にストレスがかかり、生育が通常より遅れ気味です。水温の上昇に注意してください。\n"
        elif good_sunlight_days >= 2:
            ai_advice += f"☀️ 日射量(DLI)が十分に確保されています！光合成が活発に行われ、生育が通常よりスピーディに進んでいます。\n"
        else:
            ai_advice += "🌱 現在、サンチュは極めて順調かつ標準的なペースで育っています。この調子で環境をキープしてください。\n"
            
        ai_advice += f"※直近5日間の平均生育ペース: 1日あたり {avg_daily_growth:.1f}% でシミュレーション中。"

        # --- 画面への表示処理 ---
        lbl_target = ctk.CTkLabel(
            self.main_frame, 
            text=f"分析対象: {house} - {bed} ({variety})", 
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#81c784"
        )
        lbl_target.pack(pady=15)

        display_items = [
            ("AI判定 生育率", f"{current_growth_rate:.1f} %"),
            ("AI予測 収穫適期日", predicted_date),
            ("現在の推定重量", f"{current_weight} g"),
            ("収穫適期まで", f"あと {remaining_days} 日")
        ]

        for item, value in display_items:
            row_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=40, pady=10)

            lbl_item = ctk.CTkLabel(row_frame, text=item, font=ctk.CTkFont(size=14))
            lbl_item.pack(side="left")

            lbl_val = ctk.CTkLabel(
                row_frame, 
                text=value, 
                font=ctk.CTkFont(size=18, weight="bold"),
                text_color="#81c784" if item == "収穫適期まで" else "white"
            )
            lbl_val.pack(side="right")

        # 動的なAI分析アドバイス表示エリア（グリーン枠）
        ai_frame = ctk.CTkFrame(self.main_frame, fg_color="#1b5e20")
        ai_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        lbl_ai = ctk.CTkLabel(
            ai_frame, 
            text=ai_advice,
            font=ctk.CTkFont(size=12, family="Hiragino Kaku Gothic ProN"),
            justify="left",
            wraplength=400 # 長文でも自動改行される設定
        )
        lbl_ai.pack(pady=15, padx=15)