import requests
import json
import os
import time
from datetime import datetime, timezone
import pytz

# ─────────────────────────────────────────────
# 포트폴리오 정의 (원화 매수원금 book_krw 기준)
# ─────────────────────────────────────────────
PORTFOLIO = {
    "US": {
        "RIG": {"name": "트랜스오션", "shares": 1010, "book_krw": 5985238},
        "FRO": {"name": "프론트라인", "shares": 557, "book_krw": 12949963},
        "NE": {"name": "노블", "shares": 194, "book_krw": 7917634},
        "DHT": {"name": "DHT 홀딩스", "shares": 392, "book_krw": 6374446},
        "ECO": {"name": "오케아니스 에코 탱커스", "shares": 301, "book_krw": 13744964},
        "AMR": {"name": "알파 메탈러지컬 리소시스", "shares": 23, "book_krw": 6796637},
        "FLNC": {"name": "플루언스 에너지", "shares": 150, "book_krw": 4894012},
        "QYLD": {"name": "글로벌엑스 커버드콜 ETF", "shares": 1664, "book_krw": 39862339},
        "JEPI": {"name": "JP모건 에쿼티 프리미엄", "shares": 200, "book_krw": 15499533},
        "NVTS": {"name": "나비타스 세미컨덕터", "shares": 193, "book_krw": 9287727},
        "NOK": {"name": "노키아 ADR", "shares": 22, "book_krw": 551503},
        "O": {"name": "리얼티 인컴", "shares": 600, "book_krw": 45211927},
        "SKHY": {"name": "SK하이닉스 ADR", "shares": 50, "book_krw": 9766891},
        "TSM": {"name": "TSMC", "shares": 31, "book_krw": 4067434},
        "HCC": {"name": "워리어 멧 콜", "shares": 51, "book_krw": 6552941},
    },
    "NO": {
        "PLSV.OL": {"name": "파라투스 에너지 서비시스", "shares": 2231, "book_krw": 10913955},
        "SEA1.OL": {"name": "시1 오프쇼어", "shares": 7054, "book_krw": 21859180},
        "NORAM.OL": {"name": "Noram Drilling AS", "shares": 6514, "book_krw": 31673808},
        "WAWI.OL": {"name": "WALLENIUS WILHELMSEN", "shares": 125, "book_krw": 2435832},
        "VAR.OL": {"name": "VR ENERGY AS", "shares": 612, "book_krw": 4455915},
        "DOFG.OL": {"name": "DOF Group ASA", "shares": 754, "book_krw": 10871813},
    }
}

KAKAO_ACCESS_TOKEN  = os.environ.get("KAKAO_ACCESS_TOKEN", "")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
KAKAO_CLIENT_ID     = os.environ.get("KAKAO_CLIENT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ─────────────────────────────────────────────
# 환율 수집 (USD=야후 실시간, NOK=네이버 매매기준율)
# ─────────────────────────────────────────────
def get_fx_rates():
    rates = {"USDKRW": 1450.0, "NOKKRW": 141.8}
    try:
        url_usd = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1d&range=1d"
        r_usd = requests.get(url_usd, headers=HEADERS, timeout=5).json()
        meta_usd = r_usd["chart"]["result"][0]["meta"]
        rates["USDKRW"] = float(meta_usd.get("regularMarketPrice") or meta_usd.get("previousClose"))
    except:
        pass

    try:
        url_nok = "https://m.stock.naver.com/front-api/v1/marketIndex/prices?category=exchange&reutersCode=FX_NOKKRW&page=1"
        res = requests.get(url_nok, headers=HEADERS, timeout=5).json()
        rates["NOKKRW"] = float(res["result"][0]["closePrice"].replace(",", ""))
    except:
        pass

    return rates

# ─────────────────────────────────────────────
# 주가 및 배당 정보 조회
# ─────────────────────────────────────────────
def get_stock_data(symbol: str):
    """현재가, 등락률, 최신 배당락일 및 배당금을 한 번에 수집"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d&events=div"
        r = requests.get(url, headers=HEADERS, timeout=10)
        res = r.json()["chart"]["result"][0]
        meta = res["meta"]
        
        # 1. 시세 추출
        current = meta.get("regularMarketPrice", 0.0)
        close_prices = res.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        valid_closes = [c for c in close_prices if c is not None]
        
        if len(valid_closes) >= 2:
            prev_close = valid_closes[-2]
        else:
            prev_close = meta.get("previousClose") or current
            
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0.0
        
        # 2. 배당 정보 추출
        events = res.get("events", {}).get("dividends", {})
        dps = 0.0
        ex_date_str = "-"
        
        if events:
            latest_ts = sorted(events.keys(), reverse=True)[0]
            dps = float(events[latest_ts].get("amount", 0.0))
            ex_date_str = datetime.fromtimestamp(int(latest_ts), tz=timezone.utc).strftime("%Y-%m-%d")
        elif meta.get("exDividendDate"):
            ex_date_str = datetime.fromtimestamp(meta["exDividendDate"], tz=timezone.utc).strftime("%Y-%m-%d")

        return {
            "current": float(current),
            "change_pct": float(change_pct),
            "dps": dps,
            "ex_date": ex_date_str
        }
    except Exception as e:
        print(f"  [{symbol}] 조회 실패: {e}")
        return None

def refresh_kakao_token():
    if not KAKAO_REFRESH_TOKEN or not KAKAO_CLIENT_ID: 
        return KAKAO_ACCESS_TOKEN
    try:
        r = requests.post("https://kauth.kakao.com/oauth/token", data={
            "grant_type": "refresh_token", 
            "client_id": KAKAO_CLIENT_ID, 
            "refresh_token": KAKAO_REFRESH_TOKEN,
        }, timeout=10)
        return r.json().get("access_token", KAKAO_ACCESS_TOKEN)
    except Exception:
        return KAKAO_ACCESS_TOKEN

def arrow(v): return "🔺" if v >= 0 else "🔻"
def pct(v):   return f"{arrow(v)}{abs(v):.2f}%"
def money(v): return f"{'+' if v >= 0 else '-'}{abs(v):,.0f}원"

# ─────────────────────────────────────────────
# 메시지 빌드 (기존 종가 알림 + 배당 알림)
# ─────────────────────────────────────────────
def build_messages(us_data, no_data, fx, today_str):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%m/%d %H:%M")
    
    # ── [메시지 ①] 미국 주식 현황 ──
    msg1_lines = [
        f"📊 포트폴리오 현황 ① ({now})",
        f"💱 USD {fx['USDKRW']:,.1f}원 | NOK {fx['NOKKRW']:,.2f}원",
        "\n🇺🇸 미국주식 ──────────────"
    ]
    us_eval = us_cost = 0
    for d in us_data:
        ticker, h, p = d["ticker"], d["holding"], d["data"]
        eval_krw = round(p["current"] * fx["USDKRW"] * h["shares"])
        cost_krw = h["book_krw"]
        profit_krw = eval_krw - cost_krw
        ret_pct = (profit_krw / cost_krw * 100) if cost_krw else 0
        us_eval += eval_krw
        us_cost += cost_krw
        msg1_lines.append(
            f"[{ticker}] ${p['current']:.2f} ({pct(p['change_pct'])}) | {pct(ret_pct)}\n"
            f"  평가 {eval_krw/10000:,.0f}만 ({money(profit_krw)})"
        )
    us_ret = ((us_eval - us_cost) / us_cost * 100) if us_cost else 0
    msg1_lines.append(f"▶ 미국 소계: {us_eval/10000:,.0f}만 ({pct(us_ret)})")

    # ── [메시지 ②] 노르웨이 주식 및 합산 ──
    msg2_lines = [
        f"📊 포트폴리오 현황 ② ({now})",
        "\n🇳🇴 노르웨이주식 ──────────"
    ]
    no_eval = no_cost = 0
    for d in no_data:
        ticker, h, p = d["ticker"], d["holding"], d["data"]
        clean_ticker = ticker.replace(".OL", "")
        eval_krw = round(p["current"] * fx["NOKKRW"] * h["shares"])
        cost_krw = h["book_krw"]
        profit_krw = eval_krw - cost_krw
        ret_pct = (profit_krw / cost_krw * 100) if cost_krw else 0
        no_eval += eval_krw
        no_cost += cost_krw
        msg2_lines.append(
            f"[{clean_ticker}] {p['current']:.2f} NOK ({pct(p['change_pct'])}) | {pct(ret_pct)}\n"
            f"  평가 {eval_krw/10000:,.0f}만 ({money(profit_krw)})"
        )
    no_ret = ((no_eval - no_cost) / no_cost * 100) if no_cost else 0
    total_eval = us_eval + no_eval
    total_cost = us_cost + no_cost
    total_profit = total_eval - total_cost
    total_ret = (total_profit / total_cost * 100) if total_cost else 0
    msg2_lines += [
        f"▶ 노르웨이 소계: {no_eval/10000:,.0f}만 ({pct(no_ret)})",
        "\n💼 전체 계좌 합계 ──────────",
        f"총 매수원금: {total_cost:,.0f}원",
        f"총 평가금액: {total_eval:,.0f}원",
        f"총 누적손익: {money(total_profit)}",
        f"총 합산수익률: {pct(total_ret)}"
    ]

    # ── [메시지 ③] 배당 알림 ──
    all_stocks = us_data + no_data
    today_div_alerts = []
    upcoming_divs = []

    for item in all_stocks:
        ticker = item["ticker"].replace(".OL", "")
        name = item["holding"]["name"]
        shares = item["holding"]["shares"]
        d = item["data"]
        curr = "USD" if item["market"] == "US" else "NOK"
        fx_val = fx["USDKRW"] if item["market"] == "US" else fx["NOKKRW"]

        if d["ex_date"] != "-":
            upcoming_divs.append({
                "ticker": ticker, "ex_date": d["ex_date"],
                "dps": d["dps"], "shares": shares, "curr": curr, "fx": fx_val
            })

        # 오늘 당일 배당락 여부
        if d["ex_date"] == today_str and d["dps"] > 0:
            gross = d["dps"] * shares * fx_val
            net = gross * 0.85
            today_div_alerts.append(
                f"📌 [{ticker}] {name} 배당락일\n"
                f"• 보유: {shares:,}주 | 주당: {d['dps']:.2f}{curr}\n"
                f"• 예상 세후 배당금: {net:,.0f}원 (15% 원천징수)"
            )

    msg3_lines = []
    if today_div_alerts:
        msg3_lines = [f"🔔 [오늘 배당락 알림] ({today_str})", "──────────────"] + today_div_alerts
    else:
        # 오늘 이벤트가 없을 때 보여주는 최근/다가오는 배당 캘린더 요약 4종목
        upcoming_divs.sort(key=lambda x: x["ex_date"], reverse=True)
        msg3_lines = [f"📅 [최근 배당 스케줄 요약]", "──────────────"]
        for u in upcoming_divs[:4]:
            est_net = u["dps"] * u["shares"] * u["fx"] * 0.85
            msg3_lines.append(f"• {u['ticker']} ({u['ex_date']}): 주당 {u['dps']:.2f}{u['curr']} | 약 {est_net/10000:,.1f}만")

    return "\n".join(msg1_lines), "\n".join(msg2_lines), "\n".join(msg3_lines)

def send_kakao(message: str, token: str):
    template = {"object_type": "text", "text": message, "link": {"web_url": "", "mobile_web_url": ""}}
    requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"template_object": json.dumps(template, ensure_ascii=False)}, 
        timeout=10
    )

# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────
def main():
    kst = pytz.timezone("Asia/Seoul")
    today_str = datetime.now(kst).strftime("%Y-%m-%d")
    
    fx = get_fx_rates()
    print(f"[{today_str}] 환율: USD={fx['USDKRW']:,.1f}원 | NOK={fx['NOKKRW']:,.2f}원")
    
    us_data = []
    for ticker, info in PORTFOLIO["US"].items():
        time.sleep(0.15)
        d = get_stock_data(ticker)
        if d:
            us_data.append({"ticker": ticker, "holding": info, "data": d, "market": "US"})
            
    no_data = []
    for ticker, info in PORTFOLIO["NO"].items():
        time.sleep(0.15)
        d = get_stock_data(ticker)
        if d:
            no_data.append({"ticker": ticker, "holding": info, "data": d, "market": "NO"})
            
    msg1, msg2, msg3 = build_messages(us_data, no_data, fx, today_str)
    token = refresh_kakao_token()
    
    if token:
        # 1. 미국 주식 발송
        send_kakao(msg1, token)
        time.sleep(1)
        # 2. 노르웨이 및 전체 합산 발송
        send_kakao(msg2, token)
        time.sleep(1)
        # 3. 배당 정보 발송 (당일 배당락 상세 또는 최근 일정 요약)
        send_kakao(msg3, token)
        print("모든 카카오톡 포트폴리오/배당 메시지 전송 완료!")

if __name__ == "__main__":
    main()
