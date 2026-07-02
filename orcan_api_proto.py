# coding: utf-8
import yfinance as yf
import json
from datetime import datetime

# ==========================================
# 設定パラメーター
# ==========================================
NAV_BASE = 38017  

def get_yfinance_change(symbol):
    """yfinanceを使って過去5日分のデータを取得し、直近2日間の終値から前日比を計算する"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d")
        
        if len(hist) >= 2:
            today_close = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2])
            return (today_close - prev_close) / prev_close
    except Exception as e:
        print(f"[ERROR] {symbol} のデータ取得に失敗しました: {e}")
    return None

def main():
    print("--- Yahoo Financeから最新データを取得中... ---")
    
    val_global = get_yfinance_change("ACWI") 
    val_japan = 0.0
    val_fx = get_yfinance_change("USDJPY=X")
    
    delta_global = val_global if val_global is not None else 0.0
    delta_japan = val_japan if val_japan is not None else 0.0
    delta_fx = val_fx if val_fx is not None else 0.0
    
    if val_global is None or val_japan is None or val_fx is None:
        print("[INFO] 一部データの取得に失敗しました。")
        print("       データが取れなかった項目は暫定的に 0.00% として計算します。")

    r_pred = (1 + delta_global) * (1 + delta_fx) - 1
    nav_pred = NAV_BASE * (1 + r_pred)
    diff_nav = nav_pred - NAV_BASE

    # 保存するデータを辞書（Dictionary）にまとめる
    current_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "nav_base": NAV_BASE,
        "nav_pred": nav_pred,
        "r_pred_percent": r_pred * 100,
        "diff_nav": diff_nav,
        "acwi_percent": delta_global * 100,
        "fx_percent": delta_fx * 100
    }

    file_path = "result.json"
    history_data = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            history_data = json.load(f)
            if not isinstance(history_data, list):
                history_data = []
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # 今日のデータと同じ日付のデータが既にリストにあれば削除
    history_data = [item for item in history_data if item.get("date") != current_data["date"]]

    # 最新のデータをリストの先頭に追加
    history_data.insert(0, current_data)

    # 過去30日分だけ保持する
    history_data = history_data[:30]

    # result.json を上書き保存
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
    
    print("結果を result.json に保存しました。")

if __name__ == "__main__":
    main()
