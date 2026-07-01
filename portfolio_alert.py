"""
포트폴리오 일일 변동 & 수익률 카카오톡 알림
XLS 실제 데이터 기반 (2026-06-27 잔고 기준)
"""

import requests
import json
import os
import time
from datetime import datetime
import pytz

# ─────────────────────────────────────────────
# 포트폴리오 (XLS 실측값)
# avg_fx = 매입단가(외화), qty = 보유수량
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
        {"ticker": "PLSV",  "name": "파라투스에너지서비시스", "qty": 2231, "avg_fx": 35.53},
        {"ticker": "SEA1",  "name": "시엠오프쇼어",           "qty": 5595, "avg_fx": 21.99},
        {"ticker": "NORAM", "name": "Noram Drilling",          "qty": 6251, "avg_fx": 38.25},
        {"ticker": "WAWI",  "name": "Wallenius Wilhelmsen",    "qty": 125,  "avg_fx": 129.60},
        {"ticker": "VAR",   "name": "VR Energy",               "qty": 612,  "avg_fx": 45.89},
        {"ticker": "DOFG",  "name": "DOF Group",               "qty": 754,  "avg_fx": 101.90},
    ],
}

KAKAO_ACCESS_TOKEN  = os.environ.get("KAKAO_ACCESS_TOKEN", "")
KAKAO_REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
KAKAO_CLIENT_ID     = os.environ.get("KAKAO_CLIENT_ID", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ─────────────────────────────────────────────
# 환율 조회
# ─────────────────────────────────────────────
def get_fx_rates():
    rates = {"USDKRW": 1545.30, "NOKKRW": 156.68}
    for key, symbol in [("USDKRW", "USDKRW=X"), ("NOKKRW", "NOKKRW=X")]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            r = requests.get(url, headers=HEADERS, timeout=10)
            price = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
            rates[key] = price
            print(f"  {key}: {price:.2f}")
        except Exception as e:
            print(f"  [{key}] 기본값 사용: {e}")
    return rates


# ─────────────────────────────────────────────
# 주가 조회
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 주가 조회 (정확한 당일 변동률 수정한 버전)
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# 주가 조회 (장외 시간/시차 오류 완벽 방어 버전)
# ─────────────────────────────────────────────
def get_price(ticker: str, is_norway: bool):
    symbol = f"{ticker}.OL" if is_norway else ticker
    try:
        # 안전하게 5일간의 요약 데이터를 가져오되, 계산은 '직전 마감가'로 정확히 처리합니다.
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
        r = requests.get(url, headers=HEADERS, timeout=10)
        
        meta = r.json()["chart"]["result"][0]["meta"]
        
        # 현재가 (장중 실시간 가격 또는 최종 장마감 가격)
        current = meta.get("regularMarketPrice", 0)
        
        # 💡 핵심 수정: meta에 들어있는 '진짜 직전 거래일 마감 종가'를 정확히 지정합니다.
        prev_close = meta.get("previousClose")
        
        # 만약 previousClose가 없다면 차트 리스트의 직전 값을 역산합니다.
        if not prev_close:
            prev_close = meta.get("chartPreviousClose") or current
            
        # 정확한 당일 변동률 계산 (어제 종가 대비 오늘 가격)
        change_pct = (current - prev_close) / prev_close * 100 if prev_close else 0
        
        return {"current": current, "change_pct": change_pct}
    except Exception as e:
        print(f"  [{ticker}] 조회 실패: {e}")
        return None
# ─────────────────────────────────────────────
# 카카오 토큰 갱신
# ─────────────────────────────────────────────
def refresh_kakao_token():
    if not KAKAO_REFRESH_TOKEN or not KAKAO_CLIENT_ID:
        return KAKAO_ACCESS_TOKEN
    try:
        r = requests.post("https://kauth.kakao.com/oauth/token", data={
            "grant_type":    "refresh_token",
            "client_id":     KAKAO_CLIENT_ID,
            "refresh_token": KAKAO_REFRESH_TOKEN,
        }, timeout=10)
        result = r.json()
        if "access_token" in result:
            print(f"  토큰 갱신 성공")
            return result["access_token"]
        print(f"  토큰 갱신 실패: {result}")
    except Exception as e:
        print(f"  토큰 갱신 오류: {e}")
    return KAKAO_ACCESS_TOKEN


# ─────────────────────────────────────────────
# 메시지 포맷
# ─────────────────────────────────────────────
def arrow(v):  return "🔺" if v >= 0 else "🔻"
def pct(v):    return f"{arrow(v)}{abs(v):.2f}%"
def money(v):  return f"{'+' if v>=0 else '-'}{abs(v):,.0f}원"


def build_message(us_data, no_data, fx):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%m/%d %H:%M")

    lines = [
        f"📊 포트폴리오 현황 ({now} KST)",
        f"💱 USD {fx['USDKRW']:,.0f}원  NOK {fx['NOKKRW']:.2f}원",
        "",
        "🇺🇸 ── 미국주식 ──────────────",
    ]

    us_eval = us_cost = 0
    for d in us_data:
        h, p   = d["holding"], d["price"]
        fx_r   = fx["USDKRW"]
        cur_krw  = p["current"] * fx_r
        avg_krw  = h["avg_fx"] * fx_r
        eval_amt = cur_krw * h["qty"]
        cost_amt = avg_krw * h["qty"]
        profit   = eval_amt - cost_amt
        ret_pct  = (p["current"] - h["avg_fx"]) / h["avg_fx"] * 100
        us_eval += eval_amt;  us_cost += cost_amt
        lines.append(
            f"[{h['ticker']}] {h['name']}\n"
            f"  ${p['current']:.2f}  당일{pct(p['change_pct'])}  수익{pct(ret_pct)}\n"
            f"  평가 {eval_amt:,.0f}원  손익 {money(profit)}"
        )

    us_ret = (us_eval - us_cost) / us_cost * 100 if us_cost else 0
    lines += [f"  → 미국 소계 {us_eval:,.0f}원  {pct(us_ret)}", "",
              "🇳🇴 ── 노르웨이주식 ──────────"]

    no_eval = no_cost = 0
    for d in no_data:
        h, p   = d["holding"], d["price"]
        fx_r   = fx["NOKKRW"]
        cur_krw  = p["current"] * fx_r
        avg_krw  = h["avg_fx"] * fx_r
        eval_amt = cur_krw * h["qty"]
        cost_amt = avg_krw * h["qty"]
        profit   = eval_amt - cost_amt
        ret_pct  = (p["current"] - h["avg_fx"]) / h["avg_fx"] * 100
        no_eval += eval_amt;  no_cost += cost_amt
        lines.append(
            f"[{h['ticker']}] {h['name']}\n"
            f"  {p['current']:.2f}NOK  당일{pct(p['change_pct'])}  수익{pct(ret_pct)}\n"
            f"  평가 {eval_amt:,.0f}원  손익 {money(profit)}"
        )

    no_ret = (no_eval - no_cost) / no_cost * 100 if no_cost else 0
    lines += [f"  → 노르웨이 소계 {no_eval:,.0f}원  {pct(no_ret)}", "",
              "💼 ── 전체 합계 ──────────────"]

    total_eval   = us_eval + no_eval
    total_cost   = us_cost + no_cost
    total_profit = total_eval - total_cost
    total_ret    = total_profit / total_cost * 100 if total_cost else 0
    lines += [
        f"총 평가  {total_eval:,.0f}원",
        f"총 손익  {money(total_profit)}",
        f"수익률   {pct(total_ret)}",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# 카카오톡 전송
# ─────────────────────────────────────────────
def send_kakao(message: str, token: str):
    template = {"object_type": "text", "text": message,
                "link": {"web_url": "", "mobile_web_url": ""}}
    r = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"template_object": json.dumps(template, ensure_ascii=False)},
        timeout=10
    )
    ok = r.status_code == 200 and r.json().get("result_code") == 0
    print("✅ 카카오톡 전송 성공" if ok else f"❌ 실패: {r.status_code} {r.text}")


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    kst = pytz.timezone("Asia/Seoul")
    print(f"=== 시작 {datetime.now(kst).strftime('%Y-%m-%d %H:%M KST')} ===")

    print("\n[1] 환율")
    fx = get_fx_rates()

    print("\n[2] 미국주식")
    us_data = []
    for h in PORTFOLIO["US"]:
        time.sleep(0.3)
        p = get_price(h["ticker"], False)
        if p:
            print(f"  {h['ticker']}: ${p['current']:.2f} ({p['change_pct']:+.2f}%)")
            us_data.append({"holding": h, "price": p})

    print("\n[3] 노르웨이주식")
    no_data = []
    for h in PORTFOLIO["NO"]:
        time.sleep(0.3)
        p = get_price(h["ticker"], True)
        if p:
            print(f"  {h['ticker']}: {p['current']:.2f}NOK ({p['change_pct']:+.2f}%)")
            no_data.append({"holding": h, "price": p})

    print("\n[4] 메시지 생성")
    msg = build_message(us_data, no_data, fx)
    print("\n" + "─"*50)
    print(msg)
    print("─"*50)

    print("\n[5] 토큰 갱신")
    token = refresh_kakao_token()

    if token:
        print("\n[6] 카카오톡 전송")
        send_kakao(msg, token)
    else:
        print("\n[6] 토큰 없음 → 콘솔 출력만")

    print("\n=== 완료 ===")


if __name__ == "__main__":
    main()
