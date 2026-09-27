import os
import json
from datetime import datetime, timedelta
import requests
import yfinance as yf

# ==========================================
# 1. 포트폴리오 자산 구성 및 수량 설정
# ==========================================
PORTFOLIO = {
    # [기술 성장주 / 반도체]
    'TSM': {'name': 'TSMC', 'shares': 31, 'buy_price': 106.00, 'currency': 'USD', 'category': 'Tech'},
    'RDDT': {'name': '레딧', 'shares': 32, 'buy_price': 140.10, 'currency': 'USD', 'category': 'Tech'},
    
    # [원유 탱커 / 시클리컬]
    'ECO': {'name': '오케아니스', 'shares': 350, 'buy_price': 32.00, 'currency': 'USD', 'category': 'Tanker'},
    'FRO': {'name': '프론트라인', 'shares': 546, 'buy_price': 16.98, 'currency': 'USD', 'category': 'Tanker'},
    'DHT': {'name': 'DHT홀딩스', 'shares': 200, 'buy_price': 10.50, 'currency': 'USD', 'category': 'Tanker'},
    
    # [해상 시추 / 오프쇼어]
    'NE': {'name': '노블', 'shares': 200, 'buy_price': 29.00, 'currency': 'USD', 'category': 'Drilling'},
    'NORAM.OL': {'name': '노람드릴링', 'shares': 1387, 'buy_price': 38.50, 'currency': 'NOK', 'category': 'Drilling'},
    'DOFG.OL': {'name': 'DOF그룹', 'shares': 200, 'buy_price': 95.00, 'currency': 'NOK', 'category': 'Drilling'},
    
    # [고배당 인컴 / 리츠 / 배당성장]
    'O': {'name': '리얼티인컴', 'shares': 600, 'buy_price': 52.80, 'currency': 'USD', 'category': 'Income'},
    'JEPI': {'name': 'JP모건고배당', 'shares': 200, 'buy_price': 56.90, 'currency': 'USD', 'category': 'Income'},
    'QYLD': {'name': '나스닥커버드콜', 'shares': 1664, 'buy_price': 17.80, 'currency': 'USD', 'category': 'Income'},
    'DGRO': {'name': '배당성장ETF', 'shares': 51, 'buy_price': 35.60, 'currency': 'USD', 'category': 'Income'},
    
    # [원자재 완충 자산]
    'HCC': {'name': '워리어멧콜', 'shares': 50, 'buy_price': 97.20, 'currency': 'USD', 'category': 'Commodity'},
    'AMR': {'name': '알파메탈', 'shares': 15, 'buy_price': 227.40, 'currency': 'USD', 'category': 'Commodity'}
}

# 배당세율 (15% 원천징수)
TAX_RATE = 0.15

# ==========================================
# 2. 환율 데이터 수집
# ==========================================
def get_exchange_rates():
    usd_krw = 1381.50
    nok_krw = 130.80

    try:
        usd_data = yf.Ticker("USDKRW=X").history(period="1d")
        if not usd_data.empty:
            usd_krw = float(usd_data['Close'].iloc[-1])
    except Exception as e:
        print(f"USD 환율 조회 실패(기본값 사용): {e}")

    try:
        nok_data = yf.Ticker("NOKKRW=X").history(period="1d")
        if not nok_data.empty:
            nok_krw = float(nok_data['Close'].iloc[-1])
    except Exception as e:
        print(f"NOK 환율 조회 실패(기본값 사용): {e}")

    return usd_krw, nok_krw

# ==========================================
# 3. 주가 및 평가손익 정산
# ==========================================
def get_price_summary(usd_rate, nok_rate):
    total_eval_krw = 0
    total_cost_krw = 0
    price_lines = []

    for ticker, info in PORTFOLIO.items():
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty:
                continue

            curr_price = float(hist['Close'].iloc[-1])
            prev_price = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else curr_price
            day_change_pct = ((curr_price - prev_price) / prev_price) * 100

            shares = info['shares']
            buy_price = info['buy_price']
            rate = usd_rate if info['currency'] == 'USD' else nok_rate
            symbol = "$" if info['currency'] == 'USD' else "kr"

            eval_krw = curr_price * shares * rate
            cost_krw = buy_price * shares * rate
            gain_pct = ((curr_price - buy_price) / buy_price) * 100

            total_eval_krw += eval_krw
            total_cost_krw += cost_krw

            if ticker in ['TSM', 'ECO', 'FRO', 'NE', 'O', 'JEPI', 'NORAM.OL']:
                sign = "+" if day_change_pct >= 0 else ""
                price_lines.append(f"• {ticker}: {symbol}{curr_price:,.2f} ({sign}{day_change_pct:.2f}%) | 누적 {gain_pct:+.1f}%")

        except Exception as e:
            print(f"[{ticker}] 시세 파싱 오류: {e}")

    total_gain_krw = total_eval_krw - total_cost_krw
    total_gain_pct = (total_gain_krw / total_cost_krw * 100) if total_cost_krw > 0 else 0

    return {
        'eval_krw': total_eval_krw,
        'gain_krw': total_gain_krw,
        'gain_pct': total_gain_pct,
        'lines': price_lines
    }

# ==========================================
# 4. 배당 캘린더 (오늘 기준 +30일 이내 필터링)
# ==========================================
def get_dividend_calendar(usd_rate, nok_rate):
    today = datetime.now().date()
    target_end = today + timedelta(days=30)
    events = []

    for ticker, info in PORTFOLIO.items():
        try:
            t = yf.Ticker(ticker)
            cal = t.calendar

            ex_date = None
            pay_date = None
            dividend_rate = 0.0

            if cal is not None and not (isinstance(cal, dict) and len(cal) == 0):
                cal_dict = cal.to_dict() if hasattr(cal, 'to_dict') else (cal if isinstance(cal, dict) else {})
                for k, v in cal_dict.items():
                    k_str = str(k).lower()
                    if 'ex-dividend' in k_str or 'ex dividend' in k_str:
                        ex_date = v[0] if isinstance(v, list) and v else (list(v.values())[0] if isinstance(v, dict) else v)
                    elif 'dividend date' in k_str or 'pay' in k_str:
                        pay_date = v[0] if isinstance(v, list) and v else (list(v.values())[0] if isinstance(v, dict) else v)

            divs = t.dividends
            if not divs.empty:
                dividend_rate = float(divs.iloc[-1])
                if ex_date is None:
                    last_ex = divs.index[-1].date()
                    if (today - timedelta(days=3)) <= last_ex <= target_end:
                        ex_date = last_ex

            if ex_date and hasattr(ex_date, 'date'):
                ex_date = ex_date.date()
            elif isinstance(ex_date, str):
                ex_date = datetime.strptime(ex_date[:10], '%Y-%m-%d').date()

            if pay_date and hasattr(pay_date, 'date'):
                pay_date = pay_date.date()
            elif isinstance(pay_date, str):
                pay_date = datetime.strptime(pay_date[:10], '%Y-%m-%d').date()

            is_valid_ex = ex_date and (today <= ex_date <= target_end)
            is_valid_pay = pay_date and (today <= pay_date <= target_end)

            if dividend_rate > 0 and (is_valid_ex or is_valid_pay):
                shares = info['shares']
                curr = info['currency']
                rate = usd_rate if curr == 'USD' else nok_rate

                pre_tax_native = dividend_rate * shares
                post_tax_native = pre_tax_native * (1 - TAX_RATE)
                pre_tax_krw = pre_tax_native * rate
                post_tax_krw = post_tax_native * rate

                events.append({
                    'ticker': ticker,
                    'name': info['name'],
                    'shares': shares,
                    'currency': curr,
                    'rate_per_share': dividend_rate,
                    'ex_date': ex_date if is_valid_ex else None,
                    'pay_date': pay_date if is_valid_pay else None,
                    'pre_tax_native': pre_tax_native,
                    'post_tax_native': post_tax_native,
                    'pre_tax_krw': pre_tax_krw,
                    'post_tax_krw': post_tax_krw,
                })
        except Exception as e:
            print(f"[{ticker}] 배당 파싱 스킵: {e}")

    return events

# ==========================================
# 5. 브리핑 메시지 조합
# ==========================================
def build_combined_message(price_data, div_events, usd_rate, nok_rate):
    now_str = datetime.now().strftime('%Y-%m-%d')
    lines = [
        f"📊 [모닝 포트폴리오 & 배당 브리핑]",
        f"일자: {now_str} (오전 05:00 KST)",
        f"환율: USD {usd_rate:,.1f}원 | NOK {nok_rate:,.1f}원",
        "------------------------------------",
        f"💰 총 자산: 약 {price_data['eval_krw'] / 100000000:.2f}억 원",
        f"📈 총 손익: {price_data['gain_krw'] / 100000000:+.2f}억 원 ({price_data['gain_pct']:+.1f}%)",
        "------------------------------------",
        "📌 [주요 종목 시세 마감]"
    ]
    lines.extend(price_data['lines'])
    lines.append("------------------------------------")
    lines.append("📅 [향후 30일 이내 배당 캘린더]")

    # 배당락일 기준
    ex_events = [e for e in div_events if e['ex_date']]
    ex_events.sort(key=lambda x: x['ex_date'])

    if ex_events:
        for e in ex_events:
            sym = "$" if e['currency'] == 'USD' else "NOK "
            lines.append(
                f"• {e['ex_date'].strftime('%m/%d')} [배당락] {e['ticker']} ({e['name']})\n"
                f"  - 주당 {sym}{e['rate_per_share']:.2f} × {e['shares']:,}주\n"
                f"  - 세전: {sym}{e['pre_tax_native']:,.2f} ({e['pre_tax_krw']:,.0f}원)\n"
                f"  - 세후: {sym}{e['post_tax_native']:,.2f} ({e['post_tax_krw']:,.0f}원)"
            )
    else:
        lines.append("• 향후 30일 이내 예정된 배당락일이 없습니다.")

    # 배당지급일 기준
    pay_events = [e for e in div_events if e['pay_date']]
    pay_events.sort(key=lambda x: x['pay_date'])

    lines.append("\n💵 [향후 30일 이내 지급 예정액]")
    total_post_krw = 0
    if pay_events:
        for e in pay_events:
            sym = "$" if e['currency'] == 'USD' else "NOK "
            lines.append(f"• {e['pay_date'].strftime('%m/%d')} {e['ticker']}: {sym}{e['post_tax_native']:,.2f} (세후 {e['post_tax_krw']:,.0f}원)")
            total_post_krw += e['post_tax_krw']
    else:
        total_post_krw = sum(e['post_tax_krw'] for e in ex_events)
        lines.append("• 공식 지급일 발표 대기 중 (배당락 기준 추적)")

    lines.append("------------------------------------")
    lines.append(f"🎯 30일 내 세후 예상 배당합: 약 {total_post_krw:,.0f}원")

    return "\n".join(lines)

# ==========================================
# 6. 카카오톡 발송 모듈 (Secrets 명칭 호환)
# ==========================================
def send_kakao_message(text):
    # 등록된 KAKAO_CLIENT_ID 및 REFRESH_TOKEN 읽기
    client_id = (
        os.environ.get("KAKAO_CLIENT_ID") or 
        os.environ.get("KAKAO_REST_API_KEY")
    )
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
    access_token = os.environ.get("KAKAO_ACCESS_TOKEN")

    # 1. Refresh Token이 있으면 새 Access Token으로 갱신
    if client_id and refresh_token:
        token_url = "https://kauth.kakao.com/oauth/token"
        token_data = {
            "grant_type": "refresh_token",
            "client_id": client_id.strip(),
            "refresh_token": refresh_token.strip()
        }
        try:
            t_res = requests.post(token_url, data=token_data).json()
            new_access_token = t_res.get("access_token")
            if new_access_token:
                access_token = new_access_token
        except Exception as e:
            print(f"토큰 갱신 중 예외 발생: {e}")

    if not access_token:
        print("❌ 유효한 카카오 Access Token을 확보하지 못했습니다.")
        return

    # 2. 나에게 메시지 보내기 호출
    send_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": "https://finance.yahoo.com",
                "mobile_web_url": "https://finance.yahoo.com"
            },
            "button_title": "증시 확인"
        })
    }

    res = requests.post(send_url, headers=headers, data=payload)
    if res.status_code == 200 and res.json().get("result_code") == 0:
        print("✅ 카카오톡 모닝 브리핑 발송 성공!")
    else:
        print(f"❌ 카카오톡 발송 실패: {res.status_code}, {res.text}")

# ==========================================
# 메인 실행
# ==========================================
if __name__ == "__main__":
    usd_rate, nok_rate = get_exchange_rates()
    price_data = get_price_summary(usd_rate, nok_rate)
    div_events = get_dividend_calendar(usd_rate, nok_rate)
    final_message = build_combined_message(price_data, div_events, usd_rate, nok_rate)
    
    print(final_message)
   # ==========================================
# 6. 카카오톡 발송 모듈 (디버깅 및 폴백 강화)
# ==========================================
def send_kakao_message(text):
    client_id = os.environ.get("KAKAO_CLIENT_ID") or os.environ.get("KAKAO_REST_API_KEY")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
    access_token = os.environ.get("KAKAO_ACCESS_TOKEN")

    print("\n--- [카카오 인증 상태 점검] ---")
    print(f"CLIENT_ID 존재: {bool(client_id)}, REFRESH_TOKEN 존재: {bool(refresh_token)}, ACCESS_TOKEN 존재: {bool(access_token)}")

    # 1. Refresh Token으로 새 Access Token 갱신 시도
    if client_id and refresh_token:
        token_url = "https://kauth.kakao.com/oauth/token"
        token_data = {
            "grant_type": "refresh_token",
            "client_id": client_id.strip(),
            "refresh_token": refresh_token.strip()
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            res = requests.post(token_url, data=token_data, headers=headers)
            t_res = res.json()
            print(f"토큰 갱신 응답 결과: {t_res}")
            
            if "access_token" in t_res:
                access_token = t_res["access_token"]
                print(">> 새 Access Token 갱신 성공!")
            else:
                print(f">> 토큰 갱신 실패 사유: {t_res.get('error_description', t_res)}")
        except Exception as e:
            print(f"토큰 갱신 요청 중 예외 발생: {e}")

    # 2. 갱신 실패 시 Secrets에 있는 기본 ACCESS_TOKEN 사용
    if not access_token:
        print("❌ 유효한 카카오 Access Token을 확보하지 못했습니다.")
        return

    # 3. 나에게 메시지 보내기 요청
    send_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    send_headers = {
        "Authorization": f"Bearer {access_token.strip()}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 텍스트 메시지 템플릿
    template = {
        "object_type": "text",
        "text": text,
        "link": {
            "web_url": "https://finance.yahoo.com",
            "mobile_web_url": "https://finance.yahoo.com"
        },
        "button_title": "증시 확인"
    }
    
    payload = {"template_object": json.dumps(template, ensure_ascii=False)}
    
    res = requests.post(send_url, headers=send_headers, data=payload)
    try:
        res_json = res.json()
    except:
        res_json = res.text

    if res.status_code == 200 and isinstance(res_json, dict) and res_json.get("result_code") == 0:
        print("✅ 카카오톡 모닝 브리핑 발송 성공!")
    else:
        print(f"❌ 카카오톡 발송 실패: HTTP {res.status_code}, 응답: {res_json}")
