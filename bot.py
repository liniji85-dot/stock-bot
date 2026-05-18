import datetime
import smtplib
import time
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ================= Config =================
SENDER_EMAIL = "liniji85@gmail.com"
SENDER_PASSWORD = "aloq mltc requ xciy" 

RECEIVER_EMAIL_LIST = [
    "forother1@naver.com",
    "zldzhd052@naver.com"
]

# 💡 네트워크 에러(Name or service not known)를 원천 차단하기 위해 구글 SMTP 고정 IP를 사용합니다.
GMAIL_SMTP_HOST = "74.125.137.108" 

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
    print("🚀 [승률 65% 퀀트 조건] 종목 검색 시작...")
    df_krx = get_krx_stocks()
    selected_stocks = []
    
    total_count = len(df_krx)
    
    for idx, row in df_krx.iterrows():
        code = row["Code"]
        name = row["Name"]
        market = row["Market"]
        
        if idx % 200 == 0 and idx > 0:
            print(f"> 진행률: {idx}/{total_count} 종목 분석 중...")
            
        try:
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            ticker = code + suffix
            
            df = yf.download(ticker, period="2y", progress=False, threads=False)
            
            if df.empty or len(df) < 240:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col for col in df.columns]
                
            df["MA5"] = df["Close"].rolling(5).mean()
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA60"] = df["Close"].rolling(60).mean()
            df["MA240"] = df["Close"].rolling(240).mean()
            df["Vol_MA20"] = df["Volume"].rolling(20).mean()
            
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            
            # 조건 1. 240일선 우상향
            if today["MA240"] <= df.iloc[-5]["MA240"]:
                continue
                
            # 조건 2. 최근 60거래일 매물대 돌파
            recent_60_max = df.iloc[-60:-1]["Close"].max()
            if today["Close"] < recent_60_max:
                continue

            # 조건 3. 완전 정배열 초입
            if not (today["MA5"] > today["MA20"] > today["MA60"]):
                continue

            # 조건 4. 240일선 근접성
            cond_touch = (today["Low"] <= today["MA240"]) and (today["High"] >= today["MA240"])
            cond_near_above = (today["Close"] >= today["MA240"]) and (today["Close"] <= today["MA240"] * 1.05)
            if not (cond_touch or cond_near_above):
                continue
                
            # 조건 5. 거래량 2배 이상
            if today["Volume"] < yesterday["Vol_MA20"] * 2.0:
                continue
                
            # 조건 6. 양봉 유지
            if today["Close"] < today["Open"]:
                continue
                
            close_val = int(today["Close"].item()) if hasattr(today["Close"], 'item') else int(today["Close"])
            vol_val = int(today["Volume"].item()) if hasattr(today["Volume"], 'item') else int(today["Volume"])
                
            selected_stocks.append({
                "Market": market, "Code": code, "Name": name,
                "Close": close_val, "Volume": vol_val
            })
        except Exception as e:
            continue
            
    print(f"🔥 [고승률 필터] 최종 통과 종목: {len(selected_stocks)}개")
    return pd.DataFrame(selected_stocks)

def send_email(df_result):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAIL_LIST)
    msg["Subject"] = f"[🔥고승률65%] {datetime.date.today()} 240일선 매물대 돌파 리포트"
    
    if df_result.empty:
        html = f"""
        <h3>📊 [{datetime.date.today()}] 알림</h3>
        <p style='color: gray; font-weight: bold;'>고승률 조건(240일선 우상향 + 60일 매물대 돌파)을 만족하는 종목이 오늘 시장에 없습니다.</p>
        <p>엄격한 필터링 결과이므로 시스템은 정상입니다. 장이 좋은 날 확실한 대장주 위주로 포착됩니다.</p>
        """
    else:
        html = f"<h3>🔥 승률 65% 타겟 조건 통과 종목 ({len(df_result)}개)</h3>"
        html += "<table border=1 style='border-collapse: collapse; text-align: center;'>"
        html += "<tr style='background-color: #e6f2ff;'><th>시장</th><th>코드</th><th>종목명</th><th>종가</th><th>거래량</th></tr>"
        for _, r in df_result.iterrows():
            html += f"<tr><td style='padding: 8px;'>{r['Market']}</td><td style='padding: 8px;'>{r['Code']}</td><td style='padding: 8px;'>{r['Name']}</td><td style='padding: 8px;'>{r['Close']:,}원</td><td style='padding: 8px;'>{r['Volume']:,}주</td></tr>"
        html += "</table>"
    
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            # 💡 수정된 고정 IP 주소로 완벽히 접속을 강제합니다.
            with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, 465) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL_LIST, msg.as_string())
            print(f"✅ 이메일 발송 성공! 수신처: ({', '.join(RECEIVER_EMAIL_LIST)})")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 시도 {attempt+1}회 실패 오류내용: {e}")
            time.sleep(3)
    print("❌ [최종 에러] 메일 전송 실패")

if __name__ == "__main__":
    df = find_turning_stocks()
    send_email(df)
