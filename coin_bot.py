import datetime
import smtplib
import time
import pandas as pd
import socket
import pyupbit  # 💡 업비트 공식 파이썬 라이브러리 탑재
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
    
    # 💡 pyupbit 라이브러리로 원화 마켓 코인 목록 정식 수집 (차단 절대 없음)
    try:
        coins = pyupbit.get_tickers(fiat="KRW")
        print(f"📊 분석 대상 코인 수: {len(coins)}개")
    except Exception as e:
        print(f"❌ 코인 목록 조회 실패: {e}")
        return {}, {}
        
    intervals = ['minute5', 'minute15', 'minute60', 'minute240', 'day']
    intervals_kor = {'minute5': '5분봉', 'minute15': '15분봉', 'minute60': '1시간봉', 'minute240': '4시간봉', 'day': '일봉'}
    
    results = {k: [] for k in intervals}
    
    for idx, market in enumerate(coins):
        # API 초당 호출 제한 방지
        time.sleep(0.05)
        
        for interval in intervals:
            try:
                # 💡 pyupbit 정식 함수로 차트 데이터 수집
                df = pyupbit.get_ohlcv(market, interval=interval, count=250)
                if check_240_breakout(df):
                    current_price = df.iloc[-1]['close']
                    coin_symbol = market.split('-')[1] if '-' in market else market
                    results[interval].append({
                        "Name": coin_symbol, # pyupbit는 기호로 처리하므로 심볼 매칭
                        "Code": coin_symbol,
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
    msg["Subject"] = f"[🪙코인 실전] {now_str} 주기별 240선 돌파 리포트"
    
    html = f"<h2>🪙 업비트 240선 골든크로스 / 바로 위 안착 리포트</h2>"
    html += f"<p>조회 시간: {now_str} (1시간마다 자동 갱신)</p><hr>"
    
    for interval, kor_name in intervals_kor.items():
        coin_list = results[interval]
        html += f"<h3>📊 {kor_name} 조건 만족 종목 ({len(coin_list)}개)</h3>"
        
        if not coin_list:
            html += "<p style='color: gray;'>조건을 만족하는 코인이 없습니다.</p>"
        else:
            html += "<table border=1 style='border-collapse: collapse; text-align: center; width: 400px Gaza;'>"
            html += "<tr style='background-color: #f2f2f2;'><th>코인 심볼</th><th>현재가</th></tr>"
            for c in coin_list:
                price_format = f"{c['Price']:,}원" if c['Price'] >= 1 else f"{c['Price']:.4f}원"
                html += f"<tr><td style='padding: 6px; font-weight: bold;'>{c['Name']}</td><td>{price_format}</td></tr>"
            html += "</table>"
        html += "<br>"
        
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL(GMAIL_SMTP_IP, 465, timeout=15) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print(f"✅ [{now_str}] 코인 리포트 이메일 발송 완료!")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 {attempt+1}회 실패, 5초 후 재시도... ({e})")
            time.sleep(5)
    print("❌ 코인 리포트 최종 발송 실패")

if __name__ == "__main__":
    res, kor_names = analyze_crypto_market()
    if res:
        send_crypto_email(res, kor_names)
