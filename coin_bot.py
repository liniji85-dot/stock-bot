import datetime
import smtplib
import time
import requests
import pandas as pd
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ================= Config =================
SENDER_EMAIL = "liniji85@gmail.com"
SENDER_PASSWORD = "aloq mltc requ xciy"
RECEIVER_EMAIL = "forother1@naver.com"

# 차단 방지를 위한 브라우저 가짜 헤더 설정
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

try:
    GMAIL_SMTP_IP = socket.gethostbyname("://gmail.com")
except:
    GMAIL_SMTP_IP = "142.250.31.108"

def get_upbit_krw_markets():
    """업비트 원화(KRW) 마켓의 모든 코인 목록 수집"""
    # 💡 중요: 최신 업비트 정책에 맞추어 ?isDetails=false 조건을 필수 탑재하여 차단 원천 우회
    url = "https://upbit.com"
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                krw_markets = [coin for coin in response.json() if coin['market'].startswith('KRW-')]
                return krw_markets
        except Exception as e:
            print(f"⚠️ 코인 목록 수집 시도 {attempt+1}회 실패, 3초 후 재시도... ({e})")
            time.sleep(3)
    print("❌ 코인 목록 최종 조회 실패")
    return []

def get_ohlcv(market, interval, count=250):
    """업비트에서 특정 주기의 캔들 데이터 조회"""
    if interval == '5m': url = f"https://upbit.com{market}&count={count}"
    elif interval == '15m': url = f"https://upbit.com{market}&count={count}"
    elif interval == '1h': url = f"https://upbit.com{market}&count={count}"
    elif interval == '4h': url = f"https://upbit.com{market}&count={count}"
    elif interval == '1d': url = f"https://upbit.com{market}&count={count}"
    else: return pd.DataFrame()

    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200:
            return pd.DataFrame()
        
        response_json = response.json()
        if not isinstance(response_json, list) or len(response_json) < 240:
            return pd.DataFrame()
        
        df = pd.DataFrame(response_json)
        df = df.iloc[::-1].reset_index(drop=True)
        df = df[['trade_price', 'opening_price', 'candle_acc_trade_volume']]
        df.columns = ['Close', 'Open', 'Volume']
        return df
    except:
        return pd.DataFrame()

def check_240_breakout(df):
    """240선 바로 위로 돌파했는지 조건 검증"""
    if df.empty or len(df) < 240:
        return False
    
    df['MA240'] = df['Close'].rolling(240).mean()
    
    today = df.iloc[-1]
    yesterday = df.iloc[-2]
    
    cond_breakout = (yesterday['Close'] < yesterday['MA240']) and (today['Close'] >= today['MA240'])
    cond_near_above = (today['Close'] >= today['MA240']) and (today['Close'] <= today['MA240'] * 1.03)
    cond_bullish = today['Close'] >= today['Open']
    
    if (cond_breakout or cond_near_above) and cond_bullish:
        return True
    return False

def analyze_crypto_market():
    print("🪙 업비트 전 종목 멀티 타임프레임 분석 시작...")
    coins = get_upbit_krw_markets()
    if not coins:
        print("⚠️ 수집된 코인 목록이 없어 이번 회차 분석을 건너뜁니다.")
        return {}, {}
        
    intervals = ['5m', '15m', '1h', '4h', '1d']
    intervals_kor = {'5m': '5분봉', '15m': '15분봉', '1h': '1시간봉', '4h': '4시간봉', '1d': '일봉'}
    
    results = {k: [] for k in intervals}
    
    for idx, coin in enumerate(coins):
        market = coin['market']
        name = coin['korean_name']
        
        time.sleep(0.05)  # API 과부하 방지
        
        for interval in intervals:
            df = get_ohlcv(market, interval)
            if check_240_breakout(df):
                current_price = df.iloc[-1]['Close']
                # 리스트 형태로 된 코드를 문자열로 안전하게 변환 (예: KRW-BTC -> BTC)
                coin_symbol = market.split('-')[1] if '-' in market else market
                results[interval].append({
                    "Name": name,
                    "Code": coin_symbol,
                    "Price": current_price
                })
                
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
            html += "<table border=1 style='border-collapse: collapse; text-align: center; width: 400px;'>"
            html += "<tr style='background-color: #f2f2f2;'><th>코인명</th><th>심볼</th><th>현재가</th></tr>"
            for c in coin_list:
                price_format = f"{c['Price']:,}원" if c['Price'] >= 1 else f"{c['Price']:.4f}원"
                html += f"<tr><td style='padding: 6px;'>{c['Name']}</td><td>{c['Code']}</td><td>{price_format}</td></tr>"
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
