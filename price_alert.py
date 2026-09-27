from datetime import datetime
import json
import os
import time
import pytz
import requests

# ─────────────────────────────────────────────
# 포트폴리오 정의 (보유 종목 리스트)
# ─────────────────────────────────────────────
PORTFOLIO = {
    "US": {
        "RIG": {"name": "트랜스오션", "shares": 1010, "book_krw": 5985238},
        "FRO": {"name": "프론트라인", "shares": 557, "book_krw": 12949963},
        "NE": {"name": "노블", "shares": 194, "book_krw": 7917634},
        "DHT": {"name": "DHT 홀딩스", "shares": 392, "book_krw": 6374446},
        "ECO": {
            "name": "오케아니스 에코 탱커스",
            "shares": 301,
            "book_krw": 13744964,
        },
        "AMR": {
            "name": "알파 메탈러지컬 리소시스",
            "shares": 23,
            "book_krw": 6796637,
        },
        "FLNC": {"name": "플루언스 에너지", "shares": 150, "book_krw": 4894012},
        "QYLD": {
            "name": "글로벌엑스 커버드콜 ETF",
            "shares": 1664,
            "book_krw": 39862339,
        },
        "JEPI": {
            "name": "JP모건 에쿼티 프리미엄",
            "shares": 200,
            "book_krw": 15499533,
        },
        "NVTS": {"name": "나비타스 세미컨덕터", "shares": 193, "book_krw": 9287727},
        "NOK": {"name": "노키아 ADR", "shares": 22, "book_krw": 551503},
        "O": {"name": "리얼티 인컴", "shares": 600, "book_krw": 45211927},
        "SKHY": {"name": "SK하이닉스 ADR", "shares": 50, "book_krw": 9766891},
        "TSM": {"name": "TSMC", "shares": 31, "book_krw": 4067434},
        "HCC": {"name": "워리어 멧 콜", "shares": 51, "book_krw": 6552941},
    },
    "NO": {
        "PLSV.OL": {
            "name": "파라투스 에너지 서비시스",
            "shares": 2231,
            "book_krw": 10913955,
        },
        "SEA1.OL": {"name": "시1 오프쇼어", "shares": 7054, "book_krw": 21859180},
        "NORAM.OL": {
            "name": "Noram Drilling AS",
            "shares": 6514,
            "book_krw": 31673808,
        },
        "WAWI.OL": {
            "name": "WALLENIUS WILHELMSEN",
            "shares": 125,
            "book_krw": 2435832,
        },
        "VAR.OL": {"name": "VR ENERGY AS", "shares": 612, "book_krw": 4455915},
        "DOFG.OL": {"name": "DOF Group ASA", "shares": 754, "book_krw": 10871813},
    },
}

THRESHOLD = 5.0  # 알람 기준 변동률 (5%)
STATE_FILE = "alerted_today.json"

KAKAO_ACCESS_TOKEN = os.environ.get("KAKAO_ACCESS_TOKEN", "")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
KAKAO_CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def refresh_kakao_token():
  if not KAKAO_REFRESH_TOKEN or not KAKAO_CLIENT_ID:
    return KAKAO_ACCESS_TOKEN
  try:
    r = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": KAKAO_CLIENT_ID,
            "refresh_token": KAKAO_REFRESH_TOKEN,
        },
        timeout=10,
    )
    return r.json().get("access_token", KAKAO_ACCESS_TOKEN)
  except:
    return KAKAO_ACCESS_TOKEN


def get_stock_change(symbol: str):
  try:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    res = requests.get(url, headers=HEADERS, timeout=10).json()
    meta = res["chart"]["result"][0]["meta"]
    current = float(meta.get("regularMarketPrice", 0.0))
    prev_close = float(
        meta.get("previousClose") or meta.get("chartPreviousClose", current)
    )
    change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0.0
    return current, change_pct
  except Exception as e:
    print(f"[{symbol}] 조회 실패: {e}")
    return None, None


def load_alerted_state(today_str):
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if data.get("date") == today_str:
          return data.get("alerted", [])
    except:
      pass
  return []


def save_alerted_state(today_str, alerted_list):
  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump({"date": today_str, "alerted": alerted_list}, f)


def send_kakao(message: str, token: str):
  template = {"object_type": "text", "text": message}
  requests.post(
      "https://kapi.kakao.com/v2/api/talk/memo/default/send",
      headers={
          "Authorization": f"Bearer {token}",
          "Content-Type": "application/x-www-form-urlencoded",
      },
      data={"template_object": json.dumps(template, ensure_ascii=False)},
      timeout=10,
  )


def main():
  kst = pytz.timezone("Asia/Seoul")
  now_dt = datetime.now(kst)
  today_str = now_dt.strftime("%Y-%m-%d")
  now_time_str = now_dt.strftime("%m/%d %H:%M")

  alerted_list = load_alerted_state(today_str)
  new_alerts = []

  all_stocks = []
  for ticker, info in PORTFOLIO["US"].items():
    all_stocks.append((ticker, info, "US"))
  for ticker, info in PORTFOLIO["NO"].items():
    all_stocks.append((ticker, info, "NO"))

  for ticker, info, market in all_stocks:
    time.sleep(0.1)
    clean_ticker = ticker.replace(".OL", "")

    if clean_ticker in alerted_list:
      continue

    current, change_pct = get_stock_change(ticker)
    if current is not None and abs(change_pct) >= THRESHOLD:
      direction = "급등 🚀" if change_pct > 0 else "급락 📉"
      arrow_str = "🔺" if change_pct > 0 else "🔻"

      msg = (
          f"🚨 [주가 변동 경고] ({now_time_str})\n"
          f"────────────────\n"
          f"[{clean_ticker}] {info['name']}\n"
          f"• 변동률: {arrow_str}{change_pct:.2f}% ({direction})\n"
          f"• 현재가: {current:,.2f} ({market})\n"
          f"• 보유수량: {info['shares']:,}주"
      )

      token = refresh_kakao_token()
      if token:
        send_kakao(msg, token)
        print(f"알림 전송 완료: {clean_ticker} ({change_pct:.2f}%)")
        alerted_list.append(clean_ticker)
        new_alerts.append(clean_ticker)
        time.sleep(1)

  save_alerted_state(today_str, alerted_list)


if __name__ == "__main__":
  main()
