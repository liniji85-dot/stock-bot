import datetime
import smtplib
import time
import pandas as pd
import socket
import pyupbit  # 업비트 공식 라이브러리
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ================= Config =================
SENDER_EMAIL = "liniji85@gmail.com"
SENDER_PASSWORD = "aloq mltc requ xciy"

# 💡 두 명의 수신자 리스트
RECEIVER_EMAIL_LIST = [
    "forother1@naver.com",
    "zldzhd052@naver.com"
]

# 💡 안전한 구글 SMTP 도메인 설정
GMAIL_SMTP_IP = "://gmail.com"

def check_240_breakout(df):
    """30분봉, 1시간봉, 일봉 모두에 적용되는 실시간 240선 터치 및 돌파 초입 검증"""
    if df.empty or len(df) < 240:
        return False
    
    # 240 이평선 계산
    df['MA240'] = df['close'].rolling(240).mean()
    
    today = df.iloc[-1]
    
    # 💡 [모든 주기 공통 적용] 현재 진행 중인 봉의 실시간 타점 검증
    # 1. 현재 봉의 저가와 고가 사이에 240선이 위치함 (실시간 터치 또는 관통)
    # 2. 현재 가격이 240선 위 +1.5% 이내의 아주 가까운 매수 사정권 영역에 머무름
    cond_touch = (today['low'] <= today['MA240']) and (today['high'] >= today['MA240'])
    cond_near_above = (today['close'] >= today['MA240']) and (today['close'] <= today['MA240'] * 1.015)
    
    # 당일/당해 봉 양봉 유지 (매수세 유입 확인)
    cond_bullish = today['close'] >= today['open']
    
    if (cond_touch or cond_near_above) and cond_bullish:
        return True
    return False

def analyze_crypto_market():
    print("🪙 업비트 원화 마켓 멀티 타임프레임 분석 시작...")
    
    try:
        raw_coins = pyupbit.get_tickers()
        coins = [c for c in raw_coins if c.startswith('KRW-')]
        print(f"📊 분석 대상 원화 코인 수: {len(coins)}개")
    except Exception as e:
        print(f"❌ 코인 목록 조회 실패: {e}")
        return {}, {}
        
    # 💡 30분봉, 1시간봉, 일봉(day) 순서대로 모두 분석합니다.
    intervals = ['minute30', 'minute60', 'day']
    intervals_kor = {'minute30': '30분봉', 'minute60': '1시간봉', 'day': '일봉'}
    
    results = {k: [] for k in intervals}
    
    for idx, market in enumerate(coins):
        if idx % 30 == 0 and idx > 0:
            print(f"> 진행 상황: {idx}/{len(coins)}개 원화 코인 분석 완료...")
            
        time.sleep(0.05)
        
        for interval in intervals:
            try:
                df = pyupbit.get_ohlcv(market, interval=interval, count=250)
                if check_240_breakout(df):
                    current_price = df.iloc[-1]['close']
                    # 표에 심볼이 깔끔하게 나오도록 가공 (예: KRW-BTC -> BTC)
                    coin_symbol = market.split('-')[1] if '-' in market else market
                    results[interval].append({
                        "Name": coin_symbol,
                        "Price": current_price
                    })
            except:
                continue
                
    return results, intervals_kor

def send_crypto_email(results, intervals_kor):
    if not results:
        return
        
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAIL_LIST) 
    
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg["Subject"] = f"[🪙코인 정각타점] {now_str} 주기별 240선 돌파 리포트"
    
    html = f"<h2>🪙 업비트 원화 마켓 주기별 리포트</h2>"
    html += f"<p>조회 시간: {now_str} (컴퓨터를 꺼두셔도 깃허브가 정기적으로 발송)</p><hr>"
    
    for interval, kor_name in intervals_kor.items():
        coin_list = results[interval]
        html += f"<h3>📊 {kor_name} 조건 만족 종목 ({len(coin_list)}개)</h3>"
        
        if not coin_list:
            html += "<p style='color: gray;'>조건을 만족하는 코인이 없습니다.</p>"
        else:
            html += "<table border=1 style='border-collapse: collapse; text-align: center; width: 400px;'>"
            html += "<tr style='background-color: #f2f2f2;'><th>코인 심볼</th><th>현재가 / 종가</th></tr>"
            for c in coin_list:
                price_format = f"{c['Price']:,}원" if c['Price'] >= 1 else f"{c['Price']:.4f}원"
                html += f"<tr><td style='padding: 6px; font-weight: bold; color: #1e3a8a;'>{c['Name']}</td><td>{price_format}</td></tr>"
            html += "</table>"
        html += "<br>"
        
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL(GMAIL_SMTP_IP, 465, timeout=15) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL_LIST, msg.as_string())
            print(f"✅ [{now_str}] 리포트 발송 성공! ({', '.join(RECEIVER_EMAIL_LIST)})")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 {attempt+1}회 실패, 5초 후 재시도... ({e})")
            time.sleep(5)
    print("❌ 코인 리포트 최종 발송 실패")

if __name__ == "__main__":
    res, kor_names = analyze_crypto_market()
    if res:
        send_crypto_email(res, kor_names)
