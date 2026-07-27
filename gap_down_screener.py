# -*- coding: utf-8 -*-
"""
진짜 '빈공간(window gap) 하락갭' 종목 스크리너
- 조건1: 당일 고가 < 전일 저가 (캔들 사이에 겹치는 구간이 전혀 없는 진짜 갭)
- 기간: 최근 N 거래일(기본 60봉 = 약 3개월) 이내에 1회 이상 발생
- 갭 크기(%): (전일저가 - 당일고가) / 전일저가 * 100 이 GAP_THRESHOLD 이상인 것만
- 조건2: 갭하락 발생 시점 기준으로, 종가가 224일 이동평균선 아래에서
         BELOW_MA_MONTHS(기본 4개월≈80거래일) 이상 "연속으로" 머물러 있었던 종목만

사용법:
    pip install pykrx pandas
    python gap_down_screener.py

주의:
- 전종목(약 2,700개)을 하나씩 조회하기 때문에 실행에 시간이 꽤 걸립니다 (수십 분).
- 224일 이평선 계산 + 4개월 연속조건까지 보려면 과거 데이터를 더 길게(약 1.5년)
  받아와야 해서, 이전 버전보다 종목당 조회 시간이 조금 더 걸립니다.
- KRX 서버 과부하 방지를 위해 종목마다 약간의 딜레이(SLEEP_SEC)를 둡니다.
  너무 줄이면 중간에 차단/에러가 날 수 있어요.
- 결과는 gap_down_result.csv 로 저장됩니다.
"""

import time
import datetime
import pandas as pd
from pykrx import stock

# ===== 설정값 (여기만 바꾸시면 됩니다) =====
LOOKBACK_DAYS = 60          # 몇 거래일(봉) 이내로 갭을 찾을지. 60봉 ≈ 3개월
GAP_THRESHOLD = 5.0         # 최소 갭 크기(%). 5.0 이면 5% 이상 벌어진 것만
SLEEP_SEC = 0.05            # 종목별 조회 사이 딜레이(초). 에러 나면 늘리세요.
MARKETS = ["KOSPI", "KOSDAQ"]

MA_PERIOD = 224              # 이동평균선 기간 (224일선)
BELOW_MA_MONTHS = 4          # 224일선 아래 연속으로 있어야 하는 최소 개월 수
TRADING_DAYS_PER_MONTH = 20  # 1개월≈20거래일로 환산 (대략적인 값)
BELOW_MA_DAYS = BELOW_MA_MONTHS * TRADING_DAYS_PER_MONTH  # ≈80거래일
# ==========================================


def get_date_range(lookback_days: int, extra_days: int = 0):
    """오늘 기준으로 (lookback_days + extra_days) 거래일치를 커버할 수 있게
    여유있게 캘린더일로 환산한 조회 시작일을 계산.
    extra_days에는 224일선 계산에 필요한 과거 데이터 분량을 넣어줍니다."""
    end = datetime.date.today()
    total_trading_days = lookback_days + extra_days
    # 거래일 기준이라 주말/공휴일 감안해서 넉넉히 1.6배 캘린더일로 잡음
    start = end - datetime.timedelta(days=int(total_trading_days * 1.6) + 10)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


def get_all_tickers():
    today = datetime.date.today().strftime("%Y%m%d")
    tickers = []
    for market in MARKETS:
        codes = stock.get_market_ticker_list(today, market=market)
        for code in codes:
            name = stock.get_market_ticker_name(code)
            tickers.append((code, name))
    return tickers


def find_gaps_for_ticker(code: str, start: str, end: str, lookback_days: int,
                          gap_threshold: float, ma_period: int, below_ma_days: int):
    """해당 종목의 최근 구간에서 진짜 window gap 하락 + 224일선 아래 장기체류 조건을 검사."""
    try:
        df = stock.get_market_ohlcv_by_date(start, end, code)
    except Exception:
        return []

    # 224일선을 계산하려면 최소 ma_period일치 데이터가 있어야 하고,
    # 거기에 below_ma_days(연속 체류 최소일수) + lookback_days(갭 탐색 구간)만큼 더 필요
    if df is None or len(df) < ma_period + below_ma_days + 2:
        return []

    df = df.rename(columns={"시가": "open", "고가": "high", "저가": "low", "종가": "close"})

    # 224일 이동평균선 계산 (전체 구간 기준으로 계산해야 정확함)
    df["ma224"] = df["close"].rolling(window=ma_period).mean()
    df["below_ma"] = df["close"] < df["ma224"]

    # 종가가 224일선 아래에 있는 "연속 일수(streak)"를 날짜별로 계산
    # (below_ma가 False로 끊기면 streak가 0부터 다시 시작)
    reset_group = (~df["below_ma"]).cumsum()
    streak = df.groupby(reset_group).cumcount() + 1
    df["below_ma_streak"] = streak.where(df["below_ma"], 0)

    # 갭 탐색은 최근 lookback_days 구간에서만 수행 (단, ma224/streak는 위에서 전체 구간 기준으로 이미 계산됨)
    recent = df.tail(lookback_days + 1)
    if len(recent) < 2:
        return []

    hits = []
    for i in range(1, len(recent)):
        prev_low = recent["low"].iloc[i - 1]
        today_high = recent["high"].iloc[i]
        today_close = recent["close"].iloc[i]
        prev_close = recent["close"].iloc[i - 1]
        # 거래정지/매매정지 등으로 그날 시세가 아예 없었던 경우(고가=0 또는 종가=0)는
        # 진짜 갭이 아니라 데이터 결측이므로 건너뜀
        if prev_low <= 0 or today_high <= 0 or today_close <= 0 or prev_close <= 0:
            continue
        if today_high >= prev_low:
            continue

        gap_pct = (prev_low - today_high) / prev_low * 100
        if gap_pct < gap_threshold:
            continue

        row_label = recent.index[i]
        ma_val = df.loc[row_label, "ma224"]
        streak_val = df.loc[row_label, "below_ma_streak"]

        # 224일선 값 자체가 없으면(데이터 부족) 판단 불가 -> 제외
        if pd.isna(ma_val):
            continue
        # 갭 발생 시점 기준, 224일선 아래에서 연속으로 머문 일수가 기준 미달이면 제외
        if streak_val < below_ma_days:
            continue

        hits.append({
            "date": row_label.strftime("%Y-%m-%d"),
            "gap_pct": round(gap_pct, 2),
            "prev_low": prev_low,
            "today_high": today_high,
            "below_ma224_days": int(streak_val),
        })
    return hits


def main():
    # 224일선 계산 + 4개월 연속체류 확인까지 하려면 데이터를 더 길게 받아야 함
    start, end = get_date_range(LOOKBACK_DAYS, extra_days=MA_PERIOD + BELOW_MA_DAYS)
    print(f"조회 기간: {start} ~ {end}")
    print(f"조건: 최근 {LOOKBACK_DAYS}봉 이내 갭하락 {GAP_THRESHOLD}% 이상 "
          f"+ 224일선 아래 {BELOW_MA_MONTHS}개월(≈{BELOW_MA_DAYS}거래일) 이상 연속 체류")

    tickers = get_all_tickers()
    print(f"전체 종목 수: {len(tickers)}")

    results = []
    for idx, (code, name) in enumerate(tickers, 1):
        hits = find_gaps_for_ticker(code, start, end, LOOKBACK_DAYS, GAP_THRESHOLD,
                                     MA_PERIOD, BELOW_MA_DAYS)
        for h in hits:
            results.append({
                "code": code,
                "name": name,
                **h,
            })
        if idx % 100 == 0:
            print(f"  ... {idx}/{len(tickers)} 종목 처리 완료")
        time.sleep(SLEEP_SEC)

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        # 갭 크기(gap_pct) 큰 순서로 정렬해서 바로 훑어보기 쉽게 저장
        result_df = result_df.sort_values("gap_pct", ascending=False)
        result_df.to_csv("gap_down_result.csv", index=False, encoding="utf-8-sig")
        print(f"\n완료! 총 {len(result_df)}건 발견 (종목 기준 {result_df['code'].nunique()}개)")
        print("결과 저장: gap_down_result.csv")
    else:
        print("\n조건을 만족하는 종목이 없습니다. GAP_THRESHOLD를 낮춰보세요.")


if __name__ == "__main__":
    main()
