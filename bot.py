import datetime
import smtplib
import time
import pandas as pd
import socket
import yfinance as yf
import FinanceDataReader as fdr  # 전체 종목을 자동으로 가져오기 위한 라이브러리
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ================= Config =================
SENDER_EMAIL = "liniji85@gmail.com"
SENDER_PASSWORD = "aloq mltc requ xciy" 

# 💡 두 명의 수신자 주소 리스트
RECEIVER_EMAIL_LIST = [
    "forother1@naver.com",
    "zldzhd052@naver.com"
]

try:
    GMAIL_SMTP_IP = socket.gethostbyname("://gmail.com")
except:
    GMAIL_SMTP_IP = "142.250.31.108"

def get_krx_stocks():
    print("국내 시장 전체 종목 리스트 불러오는 중...")
    df_kospi = fdr.StockListing('KOSPI')
    df_kosdaq = fdr.StockListing('KOSDAQ')
    
    df_kospi['Market'] = 'KOSPI'
    df_kosdaq['Market'] = 'KOSDAQ'
    
    df_total = pd.concat([df_kospi, df_kosdaq], ignore_index=True)
    df_total = df_total[['Code', 'Name', 'Market']]
    
    print(f"📊 분석 대상 전체 종목 수: {len(df_total)}개")
    return df_total

def find_turning_stocks():
    print("종목 분석 시작 (전체 종목 대상)...")
    df_krx = get_krx_stocks()
    selected_stocks = []
    
    total_count = len(df_krx)
    
    for idx, row in df_krx.iterrows():
        code = row["Code"]
        name = row["Name"]
        market = row["Market"]
        
        if idx % 500 == 0 and idx > 0:
            print(f"> 진행률: {idx}/{total_count} 종목 분석 완료...")
            
        try:
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            ticker = code + suffix
            
            df = yf.download(ticker, period="2y", progress=False, threads=False)
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col for col in df.columns]
                
            if len(df) < 240:
                continue
                
            df["MA5"] = df["Close"].rolling(5).mean()
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA240"] = df["Close"].rolling(240).mean()
            df["Vol_MA20"] = df["Volume"].rolling(20).mean()
            
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            
            # --- 💡 [실시간 타점 조건 수정] ---
            # 1. 당일 캔들 범위(저가~고가) 내에 240일선이 걸쳐있음 (실시간 터치/관통)
            # 2. 현재가가 240일선 위 +1.5% 이내의 아주 가까운 초입 영역에 머무름
            cond_touch = (today["Low"] <= today["MA240"]) and (today["High"] >= today["MA240"])
            cond_near_above = (today["Close"] >= today["MA240"]) and (today["Close"] <= today["MA240"] * 1.015)
            
            if not (cond_touch or cond_near_above):
                continue
                
            # 3. 거래량 급증 (평균의 3배 이상)
            if today["Volume"] < yesterday["Vol_MA20"] * 3:
                continue
            # 4. 정배열 초기 (5일선 > 20일선)
            if today["MA5"] < today["MA20"]:
                continue
            # 5. 당일 양봉 유지 (매수세 유입 확인)
            if today["Close"] < today["Open"]:
                continue
                
            close_val = int(today["Close"].item()) if hasattr(today["Close"], 'item') else int(today["Close"])
            vol_val = int(today["Volume"].item()) if hasattr(today["Volume"], 'item') else int(today["Volume"])
                
            selected_stocks.append({
                "Market": market, "Code": code, "Name": name,
                "Close": close_val, "Volume": vol_val
            })
        except:
            continue
            
    print(f"💡 최종 조건 통과 종목: {len(selected_stocks)}개")
    return pd.DataFrame(selected_stocks)

def send_email(df_result):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAIL_LIST)
    msg["Subject"] = f"[💡실전 매매] {datetime.date.today()} 전종목 240일선 리포트"
    
    if df_result.empty:
        html = f"<h3>{datetime.date.today()} 오늘 조건에 맞는 종목이 전 시장에 없습니다.</h3><p>(※ 장중 또는 장 마감 직후 분석 시 가장 정확한 실시간 타점이 검출됩니다.)</p>"
    else:
        html = f"<h3>📊 조건 통과 종목 ({len(df_result)}개)</h3><table border=1 style='border-collapse: collapse; text-align: center;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>시장</th><th>코드</th><th>종목명</th><th>종가</th><th>거래량</th></tr>"
        for _, r in df_result.iterrows():
            html += f"<tr><td style='padding: 8px;'>{r['Market']}</td><td style='padding: 8px;'>{r['Code']}</td><td style='padding: 8px;'>{r['Name']}</td><td style='padding: 8px;'>{r['Close']:,}원</td><td style='padding: 8px;'>{r['Volume']:,}주</td></tr>"
        html += "</table>"
    
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL(GMAIL_SMTP_IP, 465) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL_LIST, msg.as_string())
            print(f"✅ 이메일 발송 완료! ({', '.join(RECEIVER_EMAIL_LIST)})")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 시도 {attempt+1}회 실패: {e}")
            time.sleep(3)
    print("❌ 최종 이메일 발송 실패")

if __name__ == "__main__":
    df = find_turning_stocks()
    send_email(df)
