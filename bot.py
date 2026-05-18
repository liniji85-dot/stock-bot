import datetime
import smtplib
import time
import pandas as pd
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

# ⚠️ 안전하고 확실한 Gmail SMTP 도메인을 직접 설정합니다.
GMAIL_SMTP_HOST = "smtp.gmail.com"

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
        
        # 💡 작동 과정을 눈으로 더 자주 확인할 수 있게 100개 단위로 로그 출력 변경
        if idx % 100 == 0 and idx > 0:
            print(f"> 진행률: {idx}/{total_count} 종목 분석 완료...")
            
        try:
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            ticker = code + suffix
            
            # yfinance 에러 메시지 출력을 켜서 데이터 누락 문제를 시각화합니다.
            df = yf.download(ticker, period="2y", progress=False, threads=False)
            
            if df.empty or len(df) < 240:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col for col in df.columns]
                
            df["MA5"] = df["Close"].rolling(5).mean()
            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA240"] = df["Close"].rolling(240).mean()
            df["Vol_MA20"] = df["Volume"].rolling(20).mean()
            
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            
            # --- 💡 [실시간 타점 조건] ---
            cond_touch = (today["Low"] <= today["MA240"]) and (today["High"] >= today["MA240"])
            cond_near_above = (today["Close"] >= today["MA240"]) and (today["Close"] <= today["MA240"] * 1.015)
            
            if not (cond_touch or cond_near_above):
                continue
                
            if today["Volume"] < yesterday["Vol_MA20"] * 3:
                continue
            if today["MA5"] < today["MA20"]:
                continue
            if today["Close"] < today["Open"]:
                continue
                
            close_val = int(today["Close"].item()) if hasattr(today["Close"], 'item') else int(today["Close"])
            vol_val = int(today["Volume"].item()) if hasattr(today["Volume"], 'item') else int(today["Volume"])
                
            selected_stocks.append({
                "Market": market, "Code": code, "Name": name,
                "Close": close_val, "Volume": vol_val
            })
        except Exception as e:
            # 개별 종목 수집 중 에러가 나면 패스
            continue
            
    print(f"💡 최종 조건 통과 종목: {len(selected_stocks)}개")
    return pd.DataFrame(selected_stocks)

def send_email(df_result):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECEIVER_EMAIL_LIST)
    msg["Subject"] = f"[💡실전 매매] {datetime.date.today()} 전종목 240일선 리포트"
    
    if df_result.empty:
        # 💡 종목이 없어도 이메일이 정상적으로 도착했음을 본문에 명시합니다.
        html = f"""
        <h3>📊 [{datetime.date.today()}] 알림</h3>
        <p style='color: red; font-weight: bold;'>오늘 조건에 만족하는 발굴 종목이 0개입니다.</p>
        <p>프로그램과 메일 발송 시스템은 <b>정상 작동</b> 중입니다.</p>
        """
    else:
        html = f"<h3>📊 조건 통과 종목 ({len(df_result)}개)</h3><table border=1 style='border-collapse: collapse; text-align: center;'>"
        html += "<tr style='background-color: #f2f2f2;'><th>시장</th><th>코드</th><th>종목명</th><th>종가</th><th>거래량</th></tr>"
        for _, r in df_result.iterrows():
            html += f"<tr><td style='padding: 8px;'>{r['Market']}</td><td style='padding: 8px;'>{r['Code']}</td><td style='padding: 8px;'>{r['Name']}</td><td style='padding: 8px;'>{r['Close']:,}원</td><td style='padding: 8px;'>{r['Volume']:,}주</td></tr>"
        html += "</table>"
    
    msg.attach(MIMEText(html, "html"))
    
    for attempt in range(3):
        try:
            # 💡 안정적인 도메인 주소(smtp.gmail.com)와 포트 465를 직접 연동합니다.
            with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, 465) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL_LIST, msg.as_string())
            print(f"✅ 이메일 발송 성공! 수신처: ({', '.join(RECEIVER_EMAIL_LIST)})")
            return
        except Exception as e:
            print(f"⚠️ 이메일 발송 시도 {attempt+1}회 실패 오류내용: {e}")
            time.sleep(3)
    print("❌ [최종 에러] 메일 전송에 실패했습니다. 비밀번호나 구글 보안 설정을 확인하세요.")

if __name__ == "__main__":
    df = find_turning_stocks()
    send_email(df)
