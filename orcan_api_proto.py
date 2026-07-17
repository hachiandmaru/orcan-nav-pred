# coding: utf-8
import yfinance as yf
import json
import requests
import re
import csv
import io
from datetime import datetime, timezone

# ==========================================
# 設定：eMAXIS Slim 全世界株式（オール・カントリー）
# ==========================================
ISIN_CD = "JP90C000H1T1"
ASSOC_FUND_CD = "0331418A"
RESULT_FILE = "result.json"

# ==========================================
# 実際の基準価額の取得
# 一次ソース: 投信総合検索ライブラリー（投資信託協会）の公式CSV
# 二次ソース: みんかぶ（正規表現を小数点対応に修正）
# ==========================================
def fetch_nav_history():
    """投信協会の公式CSVから基準価額の全履歴を {"YYYY-MM-DD": 価額} の辞書で返す"""
    url = ("https://toushin-lib.fwg.ne.jp/FdsWeb/FDST030000/csv-file-download"
           f"?isinCd={ISIN_CD}&associFundCd={ASSOC_FUND_CD}")
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        text = res.content.decode("cp932", errors="replace")  # Shift_JIS系
        navs = {}
        for row in csv.reader(io.StringIO(text)):
            if len(row) < 2:
                continue
            # 日付は「2026年07月16日」形式。ヘッダ行はここで弾かれる
            m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", row[0])
            if not m:
                continue
            date_str = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            try:
                navs[date_str] = int(float(row[1].replace(",", "")))
            except ValueError:
                continue
        if navs:
            latest = max(navs)
            print(f"[INFO] 投信協会CSV: {len(navs)}日分を取得（最新 {latest} = {navs[latest]}円）")
        return navs
    except Exception as e:
        print(f"[ERROR] 投信協会CSVの取得に失敗しました: {e}")
        return {}


def get_nav_from_minkabu():
    """予備: みんかぶから最新の基準価額を取得（「38,299円」も「38299.0円」も対応）"""
    url = "https://itf.minkabu.jp/fund/0331418A"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        m = re.search(r"基準価額\s*([0-9,]+(?:\.\d+)?)\s*円", res.text)
        if m:
            return int(float(m.group(1).replace(",", "")))
        print("[WARN] みんかぶのページ形式が変わった可能性があります。")
    except Exception as e:
        print(f"[ERROR] みんかぶからの取得に失敗しました: {e}")
    return None


def get_fallback_nav(history_data):
    """最終手段: 前回のJSONから引き継ぐ"""
    if isinstance(history_data, list) and len(history_data) > 0:
        return history_data[0].get("nav_base", 38017)
    return 38017

# ==========================================
# 市場データ（yfinance）
# ==========================================
def get_completed_daily_change(symbol):
    """形成中の当日足を除いた、直近2本の「確定した」日足終値から前日比を計算する。

    平日の昼(JST)に実行する想定：
      - ACWI     … 前夜に引けた米国市場の終値 ÷ その前営業日の終値
      - USDJPY=X … 日足の切替が日本の朝なので、およそ「昨日の朝 → 今朝」の変化
                   （基準価額の計算に使われる10時仲値どうしの変化の近似になる）
    """
    try:
        hist = yf.Ticker(symbol).history(period="10d", interval="1d")
        today_utc = datetime.now(timezone.utc).date()
        hist = hist[[ts.date() < today_utc for ts in hist.index]]
        if len(hist) >= 2:
            latest = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            return (latest - prev) / prev
    except Exception as e:
        print(f"[ERROR] {symbol} のデータ取得に失敗しました: {e}")
    return None

# ==========================================
# メイン処理
# ==========================================
def main():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # 既存の履歴を読み込み
    history_data = []
    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            history_data = json.load(f)
            if not isinstance(history_data, list):
                history_data = []
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # 1. 公式CSVから確定基準価額の履歴を取得
    nav_history = fetch_nav_history()

    # 2. 過去の予想行に「実際の基準価額」を日付で突き合わせて記入
    #    （前夜に確定した値が、翌営業日昼の実行でここに入る）
    for item in history_data:
        d = item.get("date")
        if d and d in nav_history:
            item["nav_actual"] = nav_history[d]

    # 3. 今日の予想ベース（＝前営業日の確定基準価額）を決定
    NAV_BASE = None
    past_dates = [d for d in nav_history if d < today]
    if past_dates:
        base_date = max(past_dates)
        NAV_BASE = nav_history[base_date]
        print(f"[INFO] 予想ベース: {NAV_BASE}円（{base_date}の確定値）")
    if NAV_BASE is None:
        NAV_BASE = get_nav_from_minkabu()
    if NAV_BASE is None:
        NAV_BASE = get_fallback_nav(history_data)
        print(f"[WARN] 全ての自動取得に失敗。前回値 {NAV_BASE}円 を使用します。")

    # 同じ日に複数回実行しても、その日の最初のベースを維持する
    for item in history_data:
        if item.get("date") == today and item.get("nav_base"):
            NAV_BASE = item["nav_base"]
            print(f"[INFO] 本日の初回ベース {NAV_BASE}円 を維持します。")
            break

    # 4. 予想の計算（土日は実測値の追記だけ行い、予想は作らない）
    if now.weekday() < 5:
        print("--- Yahoo Financeから最新為替・株価データを取得中... ---")
        val_global = get_completed_daily_change("ACWI")
        val_fx = get_completed_daily_change("USDJPY=X")
        delta_global = val_global if val_global is not None else 0.0
        delta_fx = val_fx if val_fx is not None else 0.0

        r_pred = (1 + delta_global) * (1 + delta_fx) - 1
        nav_pred = NAV_BASE * (1 + r_pred)

        current_data = {
            "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": today,
            "nav_base": NAV_BASE,
            "nav_pred": nav_pred,
            "r_pred_percent": r_pred * 100,
            "diff_nav": nav_pred - NAV_BASE,
            "acwi_percent": delta_global * 100,
            "fx_percent": delta_fx * 100,
        }
        # 夜に再実行した場合など、当日分が既に確定していれば記入
        if today in nav_history:
            current_data["nav_actual"] = nav_history[today]

        history_data = [item for item in history_data if item.get("date") != today]
        history_data.insert(0, current_data)
    else:
        print("[INFO] 土日のため予想は作成しません（実測値の追記のみ）。")

    # 5. 保存
    history_data = history_data[:30]
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)
    print(f"結果を {RESULT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
