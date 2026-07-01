def build_message(us_data, no_data, fx):
    kst = pytz.timezone("Asia/Seoul")
    now = datetime.now(kst).strftime("%m/%d %H:%M")
    
    lines = [
        f"📊 포트폴리오 현황 ({now})",
        f"💱 USD {fx['USDKRW']:,.1f} | NOK {fx['NOKKRW']:,.2f}",
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
        
        # 💡 1줄로 압축 (글자 수 최대 60% 절약)
        lines.append(f"[{h['ticker']}] {p['current']:.2f} ({pct(p['change_pct'])}) | 수익{pct(ret_pct)}\n  평가:{eval_amt/10000:,.0f}만 ({money(profit)})")

    us_ret = (us_eval - us_cost) / us_cost * 100 if us_cost else 0
    lines += [f"▶ 미국 소계: {us_eval/10000:,.0f}만원 ({pct(us_ret)})", "\n🇳🇴 노르웨이주식 ──────────"]
    
    no_eval = no_cost = 0
    for d in no_data:
        h, p = d["holding"], d["price"]
        cur_krw = p["current"] * fx["NOKKRW"]
        eval_amt = cur_krw * h["qty"]
        cost_amt = (h["avg_fx"] * fx["NOKKRW"]) * h["qty"]
        profit = eval_amt - cost_amt
        ret_pct = (p["current"] - h["avg_fx"]) / h["avg_fx"] * 100
        no_eval += eval_amt; no_cost += cost_amt
        
        # 💡 1줄로 압축
        lines.append(f"[{h['ticker']}] {p['current']:.1f}K ({pct(p['change_pct'])}) | 수익{pct(ret_pct)}\n  평가:{no_eval/10000:,.0f}만 ({money(profit)})")

    no_ret = (no_eval - no_cost) / no_cost * 100 if no_cost else 0
    lines += [f"▶ 노르웨이 소계: {no_eval/10000:,.0f}만원 ({pct(no_ret)})", "\n💼 전체 합계 ──────────────"]
    
    total_eval = us_eval + no_eval
    total_profit = total_eval - (us_cost + no_cost)
    total_ret = total_profit / (us_cost + no_cost) * 100 if (us_cost + no_cost) else 0
    
    lines += [
        f"총 평가금액: {total_eval:,.0f}원",
        f"총 누적손익: {money(total_profit)}",
        f"총 합산수익률: {pct(total_ret)}"
    ]
    return "\n".join(lines)
