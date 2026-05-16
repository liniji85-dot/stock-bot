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
RECEIVER_EMAIL = "forother1@naver.com"

try:
    GMAIL_SMTP_IP = socket.gethostbyname("://gmail.com")
except:
    GMAIL_SMTP_IP = "142.250.31.108"

def check_240_breakout(df):
    """240선 바로 위로 돌파했는지 조건 검증"""
    if df.empty or len(df) < 240:
        return False
    
    # 240선 이동평균선 계산
    df['MA240'] = df['close'].rolling(240).mean()
    
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    
    # 조건: 어제 종가는 240선 아래, 현재 종가는 240선 돌파 혹은 바로 위 (+3% 이내)
    cond_breakout = (yesterday['close'] < yesterday['MA240']) and (today['close'] >= today['MA240'])
    cond_near_above = (today['close'] >= today['MA240']) and (today['close'] <= today['MA240'] * 1.03)
    cond_bullish = today['close'] >= today['open']
    
    if (cond_breakout or cond_near_above) and cond_bullish:
        return True
    return False

def analyze_crypto_market():
    print("🪙 업비트 전 종목 멀티 타임프레임 분석 시작...")
    
    try:
        # 업비트 전 종목 수집 (원화/BTC/USDT 포함 전체 마켓)
        coins = pyupbit.get_tickers()
        print(f"📊 분석 대상 코인 수: {len(coins)}개")
    except Exception as e:
        print(f"❌ 코인 목록 조회 실패: {e}")
        return {}, {}
        
    # 💡 [요청사항 반영] 5분/15분봉 전면 제거 ➡️ 30분봉, 1시간봉, 일봉으로 전면 재배치!
    intervals = ['minute30', 'minute60', 'day']
    intervals_kor = {'minute30': '30분봉', 'minute60': '1시간봉', 'day': '일봉'}
    
    results = {k: [] for k in intervals}
    
    for idx, market in enumerate(coins):
        # 50개 종목 분석할 때마다 터미널에 진행 상황 실시간 출력 (깃허브 모니터링용)
        if idx % 50 == 0 and idx > 0:
            print(f"> 진행 상황: {idx}/{len(coins)}개 코인 분석 완료...")
            
        time.sleep(0.02)  # 초고속 API 동기화 세팅
        
        for interval in intervals:
            try:
                df = pyupbit.get_ohlcv(market, interval=interval, count=250)
                if check_240_breakout(df):
                    current_price = df.iloc[-1]['close']
                    results[interval].append({
                        "Name": market,  # 마켓 기호 결합 (예: KRW-BTC, BTC-XRP)
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
    msg["To"] = RECEIVER_EMAIL
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    msg["Subject"] = f"[🪙코인 정각타점] {now_str} 주기별 240선 돌파 리포트"
    
    html = f"<h2>🪙 업비트 1시간 주기 자동화 리포트</h2>"
    html += f"<p>조회 시간: {now_str} (컴퓨터를 꺼두셔도 깃허브가 1시간마다 발송)</p><hr>"
    
    for interval, kor_name in intervals_kor.items():
        coin_list = results[interval]
        html += f"<h3>📊 {kor_name} 조건 만족 종목 ({len(coin_list)}개)</h3>"
        
        if not coin_list:
            html += "<p style='color: gray;'>조건을 만족하는 코인이 없습니다.</p>"
        else:
            html += "<table border=1 style='border-collapse: collapse; text-align: center; width: 450px;'>"
            html += "<tr style='background-color: #f2f2f2;'><th>마켓 및 코인 심볼</th><th>현재가 / 종가</th></tr>"
            for c in coin_list:
                price_format = f"{c['Price']:,}원" if c['Price'] >= 1 else f"{c['Price']:.8f}원"
                html += f"<tr><td style='padding: 6px; font-weight: bold; color: #1e3a8a;'>{c['Name']}</td><td>{price_format}</td></tr>"
            html += "</table>"
        html += "<br>"
        
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL(GMAIL_SMTP_IP, 465, timeout=15) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print(f"✅ [{now_str}] 1시간 주기가 완료되어 리포트 발송 성공!")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 {attempt+1}회 실패, 5초 후 재시도... ({e})")
            time.sleep(5)
    print("❌ 코인 리포트 최종 발송 실패")

if __name__ == "__main__":
    res, kor_names = analyze_crypto_market()
    if res:
        send_crypto_email(res, kor_names)
