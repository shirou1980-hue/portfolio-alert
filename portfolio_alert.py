"""
포트폴리오 일일 변동 & 수익률 카카오톡 알림 시스템
- 매일 오전 5시 실행 (cron 또는 GitHub Actions)
- 미국주식: Yahoo Finance (USD)
- 노르웨이주식: Yahoo Finance (NOK, .OL suffix)
- 카카오톡: KakaoTalk REST API (나에게 보내기)
"""

import requests
import json
import os
from datetime import datetime, date
import pytz

# ──────────────────────────────────────────────
# 1. 포트폴리오 설정 (이미지 기반)
# ──────────────────────────────────────────────

PORTFOLIO = {
    "US": [
        # (티커, 보유수량, 평균단가_KRW)
        {"ticker": "RIG",   "qty": 0,     "avg_krw": 5161.10,  "name": "트랜스오션"},
        {"ticker": "PRO",   "qty": 557,   "avg_krw": 19784.64, "name": "프로코어테크"},
        {"ticker": "NE",    "qty": 194,   "avg_krw": 7436.02,  "name": "니코"},
        {"ticker": "DHT",   "qty": 392,   "avg_krw": 6918.80,  "name": "DHT 홀딩스"},
        {"ticker": "ECO",   "qty": 301,   "avg_krw": 15013.88, "name": "오션테크니스 에코탱커스"},
        {"ticker": "AMR",   "qty": 23,    "avg_krw": 87371.29, "name": "알파 세철리치 리소시스"},
        {"ticker": "FLNC",  "qty": 150,   "avg_krw": 4466.69,  "name": "플루언스 에너지"},
        {"ticker": "QYLD",  "qty": 1664,  "avg_krw": 29719.04, "name": "글로벌엑스 나스닥100 커버드콜 ETF"},
        {"ticker": "JEPI",  "qty": 200,   "avg_krw": 11232.00, "name": "JP모건 에퀴티 프리미엄 인컴 ETF"},
        {"ticker": "NVTS",  "qty": 193,   "avg_krw": 5159.60,  "name": "나비타스 세미컨덕터"},
        {"ticker": "NOK",   "qty": 22,    "avg_krw": 286.22,   "name": "노키아 ADR"},
        {"ticker": "CI",    "qty": 600,   "avg_krw": 3817.53,  "name": "시그나 연합"},
        {"ticker": "TSM",   "qty": 31,    "avg_krw": 58523.60, "name": "TSMC(디이반반도체조)"},
        {"ticker": "HCC",   "qty": 31,    "avg_krw": 6405.70,  "name": "워리어 멧 콜"},
        {"ticker": "PLSV",  "qty": 2231,  "avg_krw": 101845.13,"name": "파리쿠스 에너지 서비스"},
    ],
    "NO": [
        # 노르웨이 주식: Yahoo Finance ticker = TICKER.OL
        {"ticker": "SSAT",  "qty": 5595,  "avg_krw": 1413228,  "name": "시 오솔로"},
        {"ticker": "NORAM", "qty": 6251,  "avg_krw": 7465.13,  "name": "Noram Drilling AS"},
        {"ticker": "WAWV",  "qty": 125,   "avg_krw": 2606763,  "name": "WALLENIUS WILHELMSEN ASA"},
        {"ticker": "VAR",   "qty": 612,   "avg_krw": 3194.64,  "name": "VR ENERGY AS"},
        {"ticker": "DOPC",  "qty": 734,   "avg_krw": 2607386,  "name": "Dolphin Group ASA"},
    ]
}

# ──────────────────────────────────────────────
# 2. 환경 변수 (GitHub Actions Secrets 또는 .env)
# ──────────────────────────────────────────────

KAKAO_ACCESS_TOKEN = os.environ.get("KAKAO_ACCESS_TOKEN", "")  # 카카오 액세스 토큰
USDKRW_API_KEY     = os.environ.get("EXCHANGERATE_API_KEY", "") # 환율 API (선택)

# ──────────────────────────────────────────────
# 3. 환율 조회 (USD→KRW, NOK→KRW)
# ──────────────────────────────────────────────

def get_fx_rates():
    """USD/KRW, NOK/KRW 환율 조회 (Yahoo Finance 이용)"""
    rates = {"USDKRW": 1370.0, "NOKKRW": 125.0}  # 기본값 fallback
    try:
        for pair, symbol in [("USDKRW", "USDKRW=X"), ("NOKKRW", "NOKKRW=X")]:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            data = r.json()
            price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
            rates[pair] = price
            print(f"  {pair}: {price:.2f}")
    except Exception as e:
        print(f"[FX] 환율 조회 실패, 기본값 사용: {e}")
    return rates


# ──────────────────────────────────────────────
# 4. 주가 조회 (Yahoo Finance v8)
# ──────────────────────────────────────────────

def get_stock_price(ticker: str, is_norway: bool = False):
    """
    현재가, 전일 종가, 52주 최고/최저 반환
    Returns: dict or None
    """
    symbol = f"{ticker}.OL" if is_norway else ticker
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        meta = data["chart"]["result"][0]["meta"]
        current   = meta.get("regularMarketPrice", 0)
        prev_close= meta.get("chartPreviousClose", meta.get("previousClose", current))
        day_high  = meta.get("regularMarketDayHigh", current)
        day_low   = meta.get("regularMarketDayLow", current)
        currency  = meta.get("currency", "USD")
        change_pct = ((current - prev_close) / prev_close * 100) if prev_close else 0
        return {
            "symbol":     symbol,
            "current":    current,
            "prev_close": prev_close,
            "day_high":   day_high,
            "day_low":    day_low,
            "change_pct": change_pct,
            "currency":   currency,
        }
    except Exception as e:
        print(f"  [{ticker}] 주가 조회 실패: {e}")
        return None


# ──────────────────────────────────────────────
# 5. 수익률 계산
# ──────────────────────────────────────────────

def calc_return(price_info: dict, holding: dict, fx: dict) -> dict:
    """보유 종목의 수익률 및 평가금액 계산 (KRW 기준)"""
    is_nok = price_info["currency"] == "NOK"
    fx_rate = fx["NOKKRW"] if is_nok else fx["USDKRW"]
    cur_krw  = price_info["current"] * fx_rate
    prev_krw = price_info["prev_close"] * fx_rate
    avg_krw  = holding["avg_krw"]
    qty      = holding["qty"]

    eval_amt  = cur_krw * qty
    cost_amt  = avg_krw * qty
    profit    = eval_amt - cost_amt
    ret_pct   = ((cur_krw - avg_krw) / avg_krw * 100) if avg_krw else 0
    day_chg   = price_info["change_pct"]

    return {
        "name":      holding["name"],
        "ticker":    holding["ticker"],
        "qty":       qty,
        "current":   price_info["current"],
        "currency":  price_info["currency"],
        "fx_rate":   fx_rate,
        "cur_krw":   cur_krw,
        "avg_krw":   avg_krw,
        "eval_amt":  eval_amt,
        "profit":    profit,
        "ret_pct":   ret_pct,
        "day_chg":   day_chg,
    }


# ──────────────────────────────────────────────
# 6. 메시지 포맷
# ──────────────────────────────────────────────

def format_message(us_results: list, no_results: list, fx: dict) -> str:
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M KST")

    lines = [
        f"📊 포트폴리오 알림 ({now})",
        f"💱 환율: USD {fx['USDKRW']:.0f}원 | NOK {fx['NOKKRW']:.2f}원",
        "",
        "━━━ 🇺🇸 미국주식 ━━━",
    ]

    def arrow(v):
        return "🔺" if v >= 0 else "🔻"

    total_us_eval = total_us_cost = total_us_profit = 0
    for r in us_results:
        if r["qty"] == 0:
            continue
        a = arrow(r["day_chg"])
        b = arrow(r["ret_pct"])
        lines.append(
            f"{r['name']}({r['ticker']})\n"
            f"  현재가 ${r['current']:.2f} {a}{r['day_chg']:+.2f}%  |  수익률 {b}{r['ret_pct']:+.2f}%\n"
            f"  평가 {r['eval_amt']:,.0f}원  손익 {r['profit']:+,.0f}원"
        )
        total_us_eval   += r["eval_amt"]
        total_us_cost   += r["avg_krw"] * r["qty"]
        total_us_profit += r["profit"]

    us_ret = (total_us_profit / total_us_cost * 100) if total_us_cost else 0
    a = arrow(us_ret)
    lines += [
        f"\n[미국 합계] 평가 {total_us_eval:,.0f}원  {a}{us_ret:+.2f}%",
        "",
        "━━━ 🇳🇴 노르웨이주식 ━━━",
    ]

    total_no_eval = total_no_cost = total_no_profit = 0
    for r in no_results:
        if r["qty"] == 0:
            continue
        a = arrow(r["day_chg"])
        b = arrow(r["ret_pct"])
        lines.append(
            f"{r['name']}({r['ticker']})\n"
            f"  현재가 {r['current']:.2f}NOK {a}{r['day_chg']:+.2f}%  |  수익률 {b}{r['ret_pct']:+.2f}%\n"
            f"  평가 {r['eval_amt']:,.0f}원  손익 {r['profit']:+,.0f}원"
        )
        total_no_eval   += r["eval_amt"]
        total_no_cost   += r["avg_krw"] * r["qty"]
        total_no_profit += r["profit"]

    no_ret = (total_no_profit / total_no_cost * 100) if total_no_cost else 0
    a = arrow(no_ret)
    lines += [
        f"\n[노르웨이 합계] 평가 {total_no_eval:,.0f}원  {a}{no_ret:+.2f}%",
        "",
    ]

    total_eval   = total_us_eval + total_no_eval
    total_cost   = total_us_cost + total_no_cost
    total_profit = total_us_profit + total_no_profit
    total_ret    = (total_profit / total_cost * 100) if total_cost else 0
    a = arrow(total_ret)
    lines += [
        "━━━ 💼 전체 합계 ━━━",
        f"총 평가금액  {total_eval:,.0f}원",
        f"총 손익      {total_profit:+,.0f}원",
        f"전체 수익률  {a}{total_ret:+.2f}%",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 7. 카카오톡 전송 (나에게 보내기)
# ──────────────────────────────────────────────

def send_kakao(message: str, token: str):
    """카카오톡 나에게 보내기 API"""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    template = {
        "object_type": "text",
        "text": message,
        "link": {"web_url": "", "mobile_web_url": ""},
    }
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    r = requests.post(url, headers=headers, data=data, timeout=10)
    if r.status_code == 200 and r.json().get("result_code") == 0:
        print("✅ 카카오톡 전송 성공")
    else:
        print(f"❌ 카카오톡 전송 실패: {r.status_code} {r.text}")


# ──────────────────────────────────────────────
# 8. 메인
# ──────────────────────────────────────────────

def main():
    print(f"=== 포트폴리오 알림 시작 {datetime.now()} ===")

    # 환율
    print("\n[1] 환율 조회")
    fx = get_fx_rates()

    # 미국 주식
    print("\n[2] 미국주식 조회")
    us_results = []
    for h in PORTFOLIO["US"]:
        print(f"  {h['ticker']}...", end=" ")
        info = get_stock_price(h["ticker"], is_norway=False)
        if info:
            r = calc_return(info, h, fx)
            us_results.append(r)
            print(f"${info['current']:.2f} ({info['change_pct']:+.2f}%)")
        else:
            print("실패")

    # 노르웨이 주식
    print("\n[3] 노르웨이주식 조회")
    no_results = []
    for h in PORTFOLIO["NO"]:
        print(f"  {h['ticker']}...", end=" ")
        info = get_stock_price(h["ticker"], is_norway=True)
        if info:
            r = calc_return(info, h, fx)
            no_results.append(r)
            print(f"{info['current']:.2f} NOK ({info['change_pct']:+.2f}%)")
        else:
            print("실패")

    # 메시지 생성
    print("\n[4] 메시지 생성")
    msg = format_message(us_results, no_results, fx)
    print("\n" + "="*50)
    print(msg)
    print("="*50)

    # 카카오톡 전송
    if KAKAO_ACCESS_TOKEN:
        print("\n[5] 카카오톡 전송")
        send_kakao(msg, KAKAO_ACCESS_TOKEN)
    else:
        print("\n[5] KAKAO_ACCESS_TOKEN 미설정 → 콘솔 출력만")

    print("\n=== 완료 ===")


if __name__ == "__main__":
    main()
