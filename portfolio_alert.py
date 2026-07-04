import requests
import json
import os
import time
from datetime import datetime
import pytz

# ─────────────────────────────────────────────
# 포트폴리오 (XLS 실측값)
# ─────────────────────────────────────────────
PORTFOLIO = {
    "US": [
        {"ticker": "RIG",   "name": "트랜스오션",          "qty": 1010, "avg_fx": 4.01},
        {"ticker": "FRO",   "name": "프론트라인",           "qty": 557,  "avg_fx": 16.38},
        {"ticker": "NE",    "name": "노블",                 "qty": 194,  "avg_fx": 28.67},
        {"ticker": "DHT",   "name": "DHT홀딩스",            "qty": 392,  "avg_fx": 11.67},
        {"ticker": "ECO",   "name": "오케아니스에코탱커스", "qty": 301,  "avg_fx": 31.19},
        {"ticker": "AMR",   "name": "알파메탈러지컬",       "qty": 23,   "avg_fx": 198.86},
        {"ticker": "FLNC",  "name": "플루언스에너지",       "qty": 150,  "avg_fx": 21.56},
        {"ticker": "QYLD",  "name": "나스닥100커버드콜ETF", "qty": 1664, "avg_fx": 18.57},
        {"ticker": "JEPI",  "name": "JP모건에쿼티ETF",      "qty": 200,  "avg_fx": 56.80},
        {"ticker": "NVTS",  "name": "나비타스세미컨덕터",   "qty": 193,  "avg_fx": 31.80},
        {"ticker": "NOK",   "name": "노키아ADR",            "qty": 22,   "avg_fx": 16.57},
        {"ticker": "O",     "name": "리얼티인컴",           "qty": 600,  "avg_fx": 56.72},
        {"ticker": "TSM",   "name": "TSMC",                 "qty": 31,   "avg_fx": 114.28},
        {"ticker": "HCC",   "name": "워리어멧콜",           "qty": 51,   "avg_fx": 88.87},
    ],
    "NO": [
        {"ticker": "PLSV",  "name": "파라투스에너지",     "qty": 2231, "avg_fx": 35.53},
        {"ticker": "SEA1",  "name": "시엠오프쇼어",       "qty": 5595, "avg_fx": 21.99},
        {"ticker": "NORAM", "name": "Noram Drilling",     "qty": 6514, "avg_fx": 38.2575},
        {"ticker": "WAWI",  "name": "Wallenius",          "qty": 125,  "avg_fx": 129.60},
        {"ticker": "VAR",   "name": "VR Energy",          "qty": 612,  "avg_fx": 45.89},
        {"ticker": "DOFG",  "name": "DOF Group",          "qty": 754,  "avg_fx": 101.90},
    ],
}

KAKAO_ACCESS_TOKEN  = os.environ.get("KAKAO_ACCESS_TOKEN", "")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
KAKAO_CLIENT_ID     = os.environ.get("KAKAO_CLIENT_ID", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def get_fx_rates():
    rates = {"USDKRW": 1545.30, "NOKKRW": 156.68}
    for key, symbol in [("USDKRW", "USDKRW=X"), ("NOKKRW", "NOKKRW=X")]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            r = requests.get(url, headers=HEADERS, timeout=10)
            rates[key] = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
        except:
            pass
    return rates

def get_price(ticker: str, is_norway: bool):
    symbol = f"{ticker}.OL" if is_norway else ticker
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        r = requests.get(url, headers=HEADERS, timeout=10)
        result = r.json()["chart"]["result"][0]
        
        meta = result["meta"]
        current = meta.get("regularMarketPrice", 0)
        
        close_prices = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        valid_closes = [c for c in close_prices if c is not None]
        
        if len(valid_closes) >= 2:
            prev_close = valid_closes[-2]
        else:
            prev_close = meta.get("previousClose") or current

        change_pct = (current - prev_close) / prev_close * 100 if prev_close else 0
        return {"current": current, "change_pct": change_pct}
    except Exception as e:
        print(f"  [{ticker}] 조회 실패: {e}")
        return None

def refresh_kakao_token():
    if not KAKAO_REFRESH_TOKEN or not KAKAO_CLIENT_ID: return KAKAO_ACCESS_TOKEN
    try:
        r = requests.post("https://kauth.kakao.com/oauth/token", data={
            "grant_type": "refresh_token", "client_id": KAKAO_CLIENT_ID, "refresh_token": KAKAO_REFRESH_TOKEN,
        }, timeout=10)
        return r.json().get("access_token", KAKAO_ACCESS_TOKEN)
    except:
        return KAKAO_ACCESS_TOKEN

def arrow(v):  return "🔺" if v >= 0 else "🔻"
def pct(v):    return f"{arrow(v)}{abs(v):.2f}%"
def money(v):  return f"{'+' if v>=0 else '-'}{abs(v):,.0f}원"

def build_message(us_data, no_data, fx):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%m/%d %H:%M")
    
    # ── [메시지 ①] 미국 주식 전용 ──
    msg1_lines = [
        f"📊 포트폴리오 현황 ① ({now})",
        f"💱 USD {fx['USDKRW']:,.1f}원 | NOK {fx['NOKKRW']:,.2f}원",
        "\n🇺🇸 미국주식 ──────────────"
    ]
    
    us_eval = us_cost = 0
    for d in us_data:
        h, p = d["holding"], d["price"]
        cur_krw = p["current"] * fx["USDKRW"]
        eval_amt = cur_krw * h["qty"]
        cost_amt = (h["avg_fx"] * fx["USDKRW"]) * h["qty"]
        profit = eval_amt - cost_amt
        ret_pct = (p["current"] - h["avg_fx"]) / h["avg_fx"] * 100
        us_eval += eval_amt; us_cost += cost_amt
        msg1_lines.append(f"[{h['ticker']}] {p['current']:.2f} ({pct(p['change_pct'])}) | 수익{pct(ret_pct)}\n  평가 {eval_amt/10000:,.0f}만 ({money(profit)})")

    us_ret = (us_eval - us_cost) / us_cost * 100 if us_cost else 0
    msg1_lines.append(f"▶ 미국 소계: {us_eval/10000:,.0f}만 ({pct(us_ret)})")
    
    # ── [메시지 ②] 노르웨이 주식 및 합계 ──
    msg2_lines = [
        f"📊 포트폴리오 현황 ② ({now})",
        "\n🇳🇴 노르웨이주식 ──────────"
    ]
    
    no_eval = no_cost = 0
    for d in no_data:
        h, p = d["holding"], d["price"]
        cur_krw = p["current"] * fx["NOKKRW"]
        eval_amt = cur_krw * h["qty"]
        cost_amt = (h["avg_fx"] * fx["NOKKRW"]) * h["qty"]
        profit = eval_amt - cost_amt
        ret_pct = (p["current"] - h["avg_fx"]) / h["avg_fx"] * 100
        no_eval += eval_amt; no_cost += cost_amt
        msg2_lines.append(f"[{h['ticker']}] {p['current']:.1f}K ({pct(p['change_pct'])}) | 수익{pct(ret_pct)}\n  평가 {eval_amt/10000:,.0f}만 ({money(profit)})")

    no_ret = (no_eval - no_cost) / no_cost * 100 if no_cost else 0
    msg2_lines += [f"▶ 노르웨이 소계: {no_eval/10000:,.0f}만 ({pct(no_ret)})", "\n💼 전체 합계 ──────────────"]
    
    total_eval = us_eval + no_eval
    total_profit = total_eval - (us_cost + no_cost)
    total_ret = total_profit / (us_cost + no_cost) * 100 if (us_cost + no_cost) else 0
    
    msg2_lines += [
        f"총 평가금액: {total_eval:,.0f}원",
        f"총 누적손익: {money(total_profit)}",
        f"총 합산수익률: {pct(total_ret)}"
    ]
    
    return "\n".join(msg1_lines), "\n".join(msg2_lines)

def send_kakao(message: str, token: str):
    template = {"object_type": "text", "text": message, "link": {"web_url": "", "mobile_web_url": ""}}
    requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=10
    )

def main():
    fx = get_fx_rates()
    
    us_data = []
    for h in PORTFOLIO["US"]:
        time.sleep(0.2)
        p = get_price(h["ticker"], False)
        if p: us_data.append({"holding": h, "price": p})
            
    no_data = []
    for h in PORTFOLIO["NO"]:
        time.sleep(0.2)
        p = get_price(h["ticker"], True)
        if p: no_data.append({"holding": h, "price": p})
            
    msg1, msg2 = build_message(us_data, no_data, fx)
    token = refresh_kakao_token()
    
    if token: 
        send_kakao(msg1, token)
        time.sleep(1)  # 연속 전송 시 카카오 서버에서 씹히는 현상 방지
        send_kakao(msg2, token)

if __name__ == "__main__":
    main()
