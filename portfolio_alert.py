import requests
import json
import os
import time
from datetime import datetime
import pytz

# ─────────────────────────────────────────────
# 포트폴리오 (원화 매수원금 book_krw 기준)
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
# 환율 하이브리드 수집 (USD=야후 실시간, NOK=네이버 매매기준율)
# ─────────────────────────────────────────────
def get_fx_rates():
    rates = {"USDKRW": 1450.0, "NOKKRW": 141.8}
    
    # 1. USD: 야후 파이낸스 실시간 시장 환율 (증권사 야간 실시간 평가용)
    try:
        url_usd = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1d&range=1d"
        r_usd = requests.get(url_usd, headers=HEADERS, timeout=5).json()
        meta_usd = r_usd["chart"]["result"][0]["meta"]
        rates["USDKRW"] = float(meta_usd.get("regularMarketPrice") or meta_usd.get("previousClose"))
    except Exception as e:
        print(f"USD 야후 환율 실패 ({e}), 네이버로 대체 시도")
        try:
            url_nv = "https://m.stock.naver.com/front-api/v1/marketIndex/prices?category=exchange&reutersCode=FX_USDKRW&page=1"
            res = requests.get(url_nv, headers=HEADERS, timeout=5).json()
            rates["USDKRW"] = float(res["result"][0]["closePrice"].replace(",", ""))
        except:
            pass

    # 2. NOK: 네이버 금융 고시환율 (오차 없이 정확한 값)
    try:
        url_nok = "https://m.stock.naver.com/front-api/v1/marketIndex/prices?category=exchange&reutersCode=FX_NOKKRW&page=1"
        res = requests.get(url_nok, headers=HEADERS, timeout=5).json()
        rates["NOKKRW"] = float(res["result"][0]["closePrice"].replace(",", ""))
    except Exception as e:
        print(f"NOK 네이버 환율 실패 ({e}), fallback 유지")

    return rates

# ─────────────────────────────────────────────
# 주가 조회 (이전 정확했던 5일 윈도우 로직 복원)
# ─────────────────────────────────────────────
def get_price(symbol: str):
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

        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0.0
        return {"current": float(current), "change_pct": float(change_pct)}
    except Exception as e:
        print(f"  [{symbol}] 시세 조회 실패: {e}")
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

def build_message(us_data, no_data, fx):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%m/%d %H:%M")
    
    # [메시지 ①] 미국 주식
    msg1_lines = [
        f"📊 포트폴리오 현황 ① ({now})",
        f"💱 USD {fx['USDKRW']:,.1f}원 | NOK {fx['NOKKRW']:,.2f}원",
        "\n🇺🇸 미국주식 ──────────────"
    ]
    
    us_eval = us_cost = 0
    for d in us_data:
        ticker, h, p = d["ticker"], d["holding"], d["price"]
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
    
    # [메시지 ②] 노르웨이 주식 및 합산
    msg2_lines = [
        f"📊 포트폴리오 현황 ② ({now})",
        "\n🇳🇴 노르웨이주식 ──────────"
    ]
    
    no_eval = no_cost = 0
    for d in no_data:
        ticker, h, p = d["ticker"], d["holding"], d["price"]
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
    
    return "\n".join(msg1_lines), "\n".join(msg2_lines)

def send_kakao(message: str, token: str):
    template = {"object_type": "text", "text": message, "link": {"web_url": "", "mobile_web_url": ""}}
    requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"template_object": json.dumps(template, ensure_ascii=False)}, 
        timeout=10
    )

def main():
    fx = get_fx_rates()
    print(f"적용 환율: USD={fx['USDKRW']:,.2f}원, NOK={fx['NOKKRW']:,.2f}원")
    
    us_data = []
    for ticker, info in PORTFOLIO["US"].items():
        time.sleep(0.15)
        p = get_price(ticker)
        if p:
            us_data.append({"ticker": ticker, "holding": info, "price": p})
            
    no_data = []
    for ticker, info in PORTFOLIO["NO"].items():
        time.sleep(0.15)
        p = get_price(ticker)
        if p:
            no_data.append({"ticker": ticker, "holding": info, "price": p})
            
    msg1, msg2 = build_message(us_data, no_data, fx)
    token = refresh_kakao_token()
    
    if token: 
        send_kakao(msg1, token)
        time.sleep(1)
        send_kakao(msg2, token)
        print("카카오톡 전송 완료")

if __name__ == "__main__":
    main()
