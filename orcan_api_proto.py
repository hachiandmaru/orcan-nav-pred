# coding: utf-8
import yfinance as yf
import json
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

# ==========================================
# 基準価額の自動取得機能（スクレイピング）
# ==========================================
def get_actual_nav():
    """みんかぶから最新の基準価額を自動取得する"""
    url = "https://itf.minkabu.jp/fund/0331418A"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        # meta descriptionから取得（最も安定）
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            content = meta.get('content', '')
            match = re.search(r'基準価額(\d[\d,]+)円', content)
            if match:
                return int(match.group(1).replace(',', ''))
        if price_element:
            price_str = price_element.text
            # "38,009円" などの文字列から数字部分だけを抜き出す
            match = re.search(r'([0-9,]+)', price_str)
            if match:
                return int(match.group(1).replace(',', ''))
    except Exception as e:
        print(f"[ERROR] 基準価額の自動取得に失敗しました: {e}")
    return None

def get_fallback_nav():
    """スクレイピング失敗時や初回実行時に、前回のJSONから基準価額を引き継ぐ安全装置"""
    try:
        with open("result.json", "r", encoding="utf-8") as f:
            history_data = json.load(f)
            if isinstance(history_data, list) and len(history_data) > 0:
                return history_data[0].get("nav_base", 38017)
    except Exception:
        pass
    return 38017

# ==========================================
# メイン処理
# ==========================================
def get_yfinance_change(symbol):
    """yfinanceを使って直近2日間の終値から前日比を計算する"""
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
    # 1. 自動で今日の確定基準価額を取得
    NAV_BASE = get_actual_nav()
    if NAV_BASE is None:
        print("[INFO] 自動取得に失敗。前回保存された基準価額を使用します。")
        NAV_BASE = get_fallback_nav()
    else:
        print(f"[INFO] 最新の基準価額 {NAV_BASE}円 を自動取得しました。")

    print("--- Yahoo Financeから最新為替・株価データを取得中... ---")
    val_global = get_yfinance_change("ACWI") 
    val_japan = 0.0
    val_fx = get_yfinance_change("USDJPY=X")
    
    delta_global = val_global if val_global is not None else 0.0
    delta_japan = val_japan if val_japan is not None else 0.0
    delta_fx = val_fx if val_fx is not None else 0.0

    # 2. 予想価格の計算
    r_pred = (1 + delta_global) * (1 + delta_fx) - 1
    nav_pred = NAV_BASE * (1 + r_pred)
    diff_nav = nav_pred - NAV_BASE

    # 3. データの保存
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

    # 今日のデータと同じ日付のデータが既にリストにあれば削除して上書き
    history_data = [item for item in history_data if item.get("date") != current_data["date"]]
    history_data.insert(0, current_data)
    history_data = history_data[:30]

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
    
    print("結果を result.json に保存しました。")

if __name__ == "__main__":
    main()
