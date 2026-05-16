import os
import datetime
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr
from concurrent.futures import ProcessPoolExecutor, as_completed

# ================= Config =================
SENDER_EMAIL = "liniji85@gmail.com"
# 💡 기존에 세팅해두신 깃허브 시크릿(SENDER_PASSWORD)을 그대로 호출합니다.
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

# 💡 두 명의 수신자 주소 리스트
RECEIVER_EMAIL_LIST = [
    "forother1@naver.com",
    "zldzhd052@naver.com"
]

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

def analyze_single_stock(row_data):
    """한 종목을 분석하는 독립된 함수 (멀티프로세싱에서 개별 호출됨)"""
    code, name, market = row_data
    try:
        suffix = ".KS" if market == "KOSPI" else ".KQ"
        ticker = code + suffix
        
        df = yf.download(ticker, period="2y", progress=False, threads=False, group_by='ticker')
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col for col in df.columns]
            
        if len(df) < 240:
            return None
            
        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA240"] = df["Close"].rolling(240).mean()
        df["Vol_MA20"] = df["Volume"].rolling(20).mean()
        
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        
        # --- 조건 검증 ---
        cond_breakout = (yesterday["Close"] < yesterday["MA240"]) and (today["Close"] >= today["MA240"])
        cond_near = (today["Close"] >= today["MA240"] * 0.98) and (today["Close"] <= today["MA240"] * 1.03)
        
        if not (cond_breakout or cond_near):
            return None
        if today["Volume"] < yesterday["Vol_MA20"] * 3:
            return None
        if today["MA5"] < today["MA20"]:
            return None
        if today["Close"] < today["Open"]:
            return None
            
        close_val = int(today["Close"].item()) if hasattr(today["Close"], 'item') else int(today["Close"])
        vol_val = int(today["Volume"].item()) if hasattr(today["Volume"], 'item') else int(today["Volume"])
            
        return {
            "Market": market, "Code": code, "Name": name,
            "Close": close_val, "Volume": vol_val
        }
    except:
        return None

def find_turning_stocks_multiprocess():
    print("🚀 멀티프로세싱 기반 종목 분석 시작...")
    df_krx = get_krx_stocks()
    selected_stocks = []
    
    stock_tasks = [(row['Code'], row['Name'], row['Market']) for _, row in df_krx.iterrows()]
    total_count = len(stock_tasks)
    
    # 깃허브 액션 가상 서버 사양에 맞추어 core 배분을 4개로 최적화합니다.
    with ProcessPoolExecutor(max_workers=4) as executor:
        future_to_stock = {executor.submit(analyze_single_stock, task): task for task in stock_tasks}
        
        completed_count = 0
        for future in as_completed(future_to_stock):
            completed_count += 1
            result = future.result()
            
            if result is not None:
                selected_stocks.append(result)
                
            if completed_count % 200 == 0:
                print(f"> 실시간 진행률: {completed_count}/{total_count} 종목 완료... (현재 탐색된 종목: {len(selected_stocks)}개)")
                
    print(f"💡 최종 조건 통과 종목: {len(selected_stocks)}개")
    return pd.DataFrame(selected_stocks)

def send_email(df_result):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAIL_LIST)
    msg["Subject"] = f"[💡실전 매매] {datetime.date.today()} 전종목 240일선 리포트"
    
    if df_result.empty:
        html = "<h3>오늘 조건에 맞는 종목이 전 시장에 없습니다.</h3>"
    else:
        html = f"<h3>📊 조건 통과 종목 ({len(df_result)}개)</h3><table border=1 style='border-collapse: collapse; text-align: center;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>시장</th><th>코드</th><th>종목명</th><th>종가</th><th>거래량</th></tr>"
        for _, r in df_result.iterrows():
            html += f"<tr><td style='padding: 8px;'>{r['Market']}</td><td style='padding: 8px;'>{r['Code']}</td><td style='padding: 8px;'>{r['Name']}</td><td style='padding: 8px;'>{r['Close']:,}원</td><td style='padding: 8px;'>{r['Volume']:,}주</td></tr>"
        html += "</table>"
    
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL("://gmail.com", 465) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL_LIST, msg.as_string())
            print(f"✅ 이메일 발송 완료! ({', '.join(RECEIVER_EMAIL_LIST)})")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 시도 {attempt+1}회 실패: {e}")
            time.sleep(3)
    print("❌ 최종 이메일 발송 실패")

if __name__ == "__main__":
    df = find_turning_stocks_multiprocess()
    send_email(df)
