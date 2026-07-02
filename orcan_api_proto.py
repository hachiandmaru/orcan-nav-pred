# coding: cp932
import yfinance as yf
import json
from datetime import datetime

# ==========================================
# 設定パラメーター
# ==========================================
# 2. 前営業日の確定基準価額（★ここを当日の朝、前日の値に書き換えてください）
NAV_BASE = 38376  

W_GLOBAL = 0.945
W_JAPAN = 0.055

def get_yfinance_change(symbol):
    """yfinanceを使って過去5日分のデータを取得し、直近2日間の終値から前日比を計算する"""
    try:
        ticker = yf.Ticker(symbol)
        # 祝日などを考慮して直近数日分を取得
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
    
    # データの取得 (APIキー不要、スリープ不要)
    # yfinanceでのティッカーシンボル: ドル円=USDJPY=X
    # オルカンと同じ指数に連動するETF(ACWI)を直接取得する
    val_global = get_yfinance_change("ACWI") 
    val_japan = 0.0 # ACWIの中に日本も含まれているので、個別取得は不要
    val_fx = get_yfinance_change("USDJPY=X")
    
    # エラーハンドリングと可視化
    delta_global = val_global if val_global is not None else 0.0
    delta_japan = val_japan if val_japan is not None else 0.0
    delta_fx = val_fx if val_fx is not None else 0.0
    
    if val_global is None or val_japan is None or val_fx is None:
        print("[INFO] 一部データの取得に失敗しました。")
        print("       データが取れなかった項目は暫定的に 0.00% として計算します。")

    # 【数式モデルの実行】
    r_pred = (1 + delta_global) * (1 + delta_fx) - 1
    nav_pred = NAV_BASE * (1 + r_pred)
    
    diff_nav = nav_pred - NAV_BASE
    diff_sign = "+" if diff_nav >= 0 else "-"

    # 保存するデータを辞書（Dictionary）にまとめる
    export_data = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nav_base": NAV_BASE,
        "nav_pred": nav_pred,
        "r_pred_percent": r_pred * 100,
        "diff_nav": diff_nav,
        "acwi_percent": delta_global * 100,
        "fx_percent": delta_fx * 100
    }

    # result.json という名前でファイルを書き出し（上書き）
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=4, ensure_ascii=False)
    
    print("結果を result.json に保存しました。")

if __name__ == "__main__":
    main()
