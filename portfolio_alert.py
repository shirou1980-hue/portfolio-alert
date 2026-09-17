import requests
import json
import os
import time
from datetime import datetime, timezone
import pytz

# ─────────────────────────────────────────────
# 포트폴리오 정의
# ─────────────────────────────────────────────
PORTFOLIO = {
    "US": {
        "RIG": {"name": "트랜스오션", "shares": 1010},
        "FRO": {"name": "프론트라인", "shares": 557},
        "NE": {"name": "노블", "shares": 194},
        "DHT": {"name": "DHT 홀딩스", "shares": 392},
        "ECO": {"name": "오케아니스 에코 탱커스", "shares": 301},
        "AMR": {"name": "알파 메탈러지컬 리소시스", "shares": 23},
        "FLNC": {"name": "플루언스 에너지", "shares": 150},
        "QYLD": {"name": "글로벌엑스 커버드콜 ETF", "shares": 1664},
        "JEPI": {"name": "JP모건 에쿼티 프리미엄", "shares": 200},
        "NVTS": {"name": "나비타스 세미컨덕터", "shares": 193},
        "NOK": {"name": "노키아 ADR", "shares": 22},
        "O": {"name": "리얼티 인컴", "shares": 600},
        "SKHY": {"name": "SK하이닉스 ADR", "shares": 50},
        "TSM": {"name": "TSMC", "shares": 31},
        "HCC": {"name": "워리어 멧 콜", "shares": 51},
    },
    "NO": {
        "PLSV.OL": {"name": "파라투스 에너지 서비시스", "shares": 2231},
        "SEA1.OL": {"name": "시1 오프쇼어", "shares": 7054},
        "NORAM.OL": {"name": "Noram Drilling AS", "shares": 6514},
        "WAWI.OL": {"name": "WALLENIUS WILHELMSEN", "shares": 125},
        "VAR.OL": {"name": "VR ENERGY AS", "shares": 612},
        "DOFG.OL": {"name": "DOF Group ASA", "shares": 754},
    }
}

KAKAO_ACCESS_TOKEN  = os.environ.get("KAKAO_ACCESS_TOKEN", "")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
KAKAO_CLIENT_ID     = os.environ.get("KAKAO_CLIENT_ID", "")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ─────────────────────────────────────────────
# 환율 수집 (실시간 야후/네이버 하이브리드)
# ─────────────────────────────────────────────
def get_fx_rates():
    rates = {"USDKRW": 1450.0, "NOKKRW": 141.8}
    try:
        url_usd = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1d&range=1d"
        r_usd = requests.get(url_usd, headers=HEADERS, timeout=5).json()
        meta = r_usd["chart"]["result"][0]["meta"]
        rates["USDKRW"] = float(meta.get("regularMarketPrice") or meta.get("previousClose"))
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
# 종목별 배당 스케줄 및 주당 배당금 추출
# ─────────────────────────────────────────────
def get_dividend_info(symbol: str):
    """야후 v8 차트의 events 및 calendarEvents 필드에서 배당락일/지급일/단가 파싱"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1mo&events=div"
        r = requests.get(url, headers=HEADERS, timeout=10)
        res = r.json()["chart"]["result"][0]
        
        events = res.get("events", {}).get("dividends", {})
        meta = res.get("meta", {})
        
        # 기본 1주당 배당 단가 추정
        div_rate = 0.0
        ex_date_str = "-"
        pay_date_str = "-"
        
        # 최근 선언된 배당 이벤트가 있을 경우
        if events:
            # 타임스탬프 기준 최신순 정렬
            latest_ts = sorted(events.keys(), reverse=True)[0]
            div_data = events[latest_ts]
            div_rate = float(div_data.get("amount", 0.0))
            ex_dt = datetime.fromtimestamp(int(latest_ts), tz=timezone.utc)
            ex_date_str = ex_dt.strftime("%Y-%m-%d")
        
        # 메타데이터 내 배당락일 확인
        if meta.get("exDividendDate"):
            ex_dt = datetime.fromtimestamp(meta["exDividendDate"], tz=timezone.utc)
            ex_date_str = ex_dt.strftime("%Y-%m-%d")
            
        return {
            "dps": div_rate,             # 1주당 배당금 (현지통화)
            "ex_date": ex_date_str,      # 배당락일 (YYYY-MM-DD)
            "pay_date": pay_date_str     # 수령일 (공시 미확정 시 '-')
        }
    except Exception as e:
        return {"dps": 0.0, "ex_date": "-", "pay_date": "-"}

# ─────────────────────────────────────────────
# 카카오 인증 및 발송
# ─────────────────────────────────────────────
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
    except:
        return KAKAO_ACCESS_TOKEN

def send_kakao(message: str, token: str):
    template = {"object_type": "text", "text": message, "link": {"web_url": "", "mobile_web_url": ""}}
    requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"template_object": json.dumps(template, ensure_ascii=False)}, 
        timeout=10
    )

# ─────────────────────────────────────────────
# 메인 실행부
# ─────────────────────────────────────────────
def main():
    kst = pytz.timezone("Asia/Seoul")
    today_str = datetime.now(kst).strftime("%Y-%m-%d")
    fx = get_fx_rates()
    
    print(f"=== [{today_str}] 배당 스케줄 점검 ===")
    
    calendar_rows = []
    alerts = []
    
    # 1. 포트폴리오 전체 순회
    for market, stocks in PORTFOLIO.items():
        currency = "USD" if market == "US" else "NOK"
        fx_rate = fx["USDKRW"] if market == "US" else fx["NOKKRW"]
        
        for ticker, info in stocks.items():
            time.sleep(0.15)
            div_info = get_dividend_info(ticker)
            dps = div_info["dps"]
            shares = info["shares"]
            clean_ticker = ticker.replace(".OL", "")
            
            # 캘린더 목록 추가
            if div_info["ex_date"] != "-":
                calendar_rows.append({
                    "ticker": clean_ticker,
                    "name": info["name"],
                    "market": market,
                    "ex_date": div_info["ex_date"],
                    "dps": dps,
                    "currency": currency
                })
            
            # 2. 오늘이 배당락일 또는 수령일인지 판별
            is_today_ex = (div_info["ex_date"] == today_str)
            is_today_pay = (div_info["pay_date"] == today_str)
            
            if (is_today_ex or is_today_pay) and dps > 0:
                gross_foreign = dps * shares
                gross_krw = gross_foreign * fx_rate
                # 해외주식 배당소득세 원천징수 세율: 15% 적용
                tax_krw = gross_krw * 0.15
                net_krw = gross_krw - tax_krw
                
                event_type = "배당락일" if is_today_ex else "배당금 입금일"
                alert_text = (
                    f"📌 [{clean_ticker}] {info['name']} {event_type}\n"
                    f"• 보유수량: {shares:,}주\n"
                    f"• 주당 배당금: {dps:.3f} {currency}\n"
                    f"• 세전 배당금: {gross_krw:,.0f}원 ({gross_foreign:,.2f} {currency})\n"
                    f"• 세후 배당금: {net_krw:,.0f}원 (15% 원천징수 적용)"
                )
                alerts.append(alert_text)

    # 3. 콘솔 캘린더 형식 정렬 출력
    calendar_rows.sort(key=lambda x: x["ex_date"], reverse=True)
    print("\n📅 [포트폴리오 배당 캘린더]")
    print(f"{'종목':<10} {'종목명':<16} {'배당락일':<12} {'주당배당금':<12}")
    print("-" * 55)
    for r in calendar_rows:
        print(f"{r['ticker']:<10} {r['name']:<16} {r['ex_date']:<12} {r['dps']:.2f} {r['currency']}")
    print("-" * 55)

    # 4. 당일 배당 이벤트가 발생했을 경우 카카오톡 자동 발송
    token = refresh_kakao_token()
    if alerts and token:
        msg = f"🔔 [배당 알림] {today_str}\n\n" + "\n\n".join(alerts)
        send_kakao(msg, token)
        print("\n카카오톡 배당 알림 발송 완료!")
    else:
        print("\n오늘 도래한 배당락일/지급일 이벤트가 없습니다. (카카오톡 미발송)")

if __name__ == "__main__":
    main()
