import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr  # -- 전체 종목을 가져오기 위한 라이브러리

# ================= Config =================
SENDER_EMAIL = liniji85@gmail.com
SENDER_PASSWORD = aloq mltc requ xciy
RECEIVER_EMAIL = forother1@naver.com

def get_krx_stocks()
    print(국내 시장 전체 종목 리스트 불러오는 중...)
    # KOSPI와 KOSDAQ 전체 종목 수집
    df_kospi = fdr.StockListing('KOSPI')
    df_kosdaq = fdr.StockListing('KOSDAQ')
    
    df_kospi['Market'] = 'KOSPI'
    df_kosdaq['Market'] = 'KOSDAQ'
    
    # 필요한 컬럼만 추출하여 합치기
    df_total = pd.concat([df_kospi, df_kosdaq], ignore_index=True)
    df_total = df_total[['Code', 'Name', 'Market']]
    
    print(f📊 분석 대상 전체 종목 수 {len(df_total)}개)
    return df_total

def find_turning_stocks()
    print(종목 분석 시작 (전체 종목 대상)...)
    df_krx = get_krx_stocks()
    selected_stocks = []
    
    # 속도 향상을 위해 진행 상황 표시 생성
    total_count = len(df_krx)
    
    for idx, row in df_krx.iterrows()
        code = row[Code]
        name = row[Name]
        market = row[Market]
        
        # 500개 종목마다 진행 상황 출력
        if idx % 500 == 0 and idx  0
            print(f 진행률 {idx}{total_count} 종목 분석 완료...)
            
        try
            # yfinance는 코스피는 .KS, 코스닥은 .KQ를 붙여야 합니다.
            suffix = .KS if market == KOSPI else .KQ
            ticker = code + suffix
            
            df = yf.download(ticker, period=2y, progress=False, threads=False)
            
            if isinstance(df.columns, pd.MultiIndex)
                df.columns = [col[0] for col in df.columns]
                
            if len(df)  240
                continue
                
            df[MA5] = df[Close].rolling(5).mean()
            df[MA20] = df[Close].rolling(20).mean()
            df[MA240] = df[Close].rolling(240).mean()
            df[Vol_MA20] = df[Volume].rolling(20).mean()
            
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            
            cond_breakout = (yesterday[Close]  yesterday[MA240]) and (today[Close] = today[MA240])
            cond_near = (today[Close] = today[MA240]  0.98) and (today[Close] = today[MA240]  1.03)
            
            if not (cond_breakout or cond_near)
                continue
            if today[Volume]  yesterday[Vol_MA20]  3
                continue
            if today[MA5]  today[MA20]
                continue
            if today[Close]  today[Open]
                continue
                
            close_val = int(today[Close].iloc[0]) if isinstance(today[Close], pd.Series) else int(today[Close])
            vol_val = int(today[Volume].iloc[0]) if isinstance(today[Volume], pd.Series) else int(today[Volume])
                
            selected_stocks.append({
                Market market, Code code, Name name,
                Close close_val, Volume vol_val
            })
        except
            continue
            
    print(f💡 최종 조건 통과 종목 {len(selected_stocks)}개)
    return pd.DataFrame(selected_stocks)

def send_email(df_result)
    msg = MIMEMultipart()
    msg[From] = SENDER_EMAIL
    msg[To] = RECEIVER_EMAIL
    msg[Subject] = f[💡실전 매매] {datetime.date.today()} 전종목 240일선 리포트
    
    if df_result.empty
        html = h3오늘 조건에 맞는 종목이 전 시장에 없습니다.h3
    else
        html = fh3📊 조건 통과 종목 ({len(df_result)}개)h3table border=1 style='border-collapse collapse; text-align center;'
        html += tr style='background-color #f2f2f2;'th시장thth코드thth종목명thth종가thth거래량thtr
        for _, r in df_result.iterrows()
            html += ftrtd style='padding 8px;'{r['Market']}tdtd style='padding 8px;'{r['Code']}tdtd style='padding 8px;'{r['Name']}tdtd style='padding 8px;'{r['Close'],}원tdtd style='padding 8px;'{r['Volume'],}주tdtr
        html += table
    
    msg.attach(MIMEText(html, html))
    try
        with smtplib.SMTP_SSL(gmail.com, 465) as server
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(✅ 이메일 발송 완료!)
    except Exception as e
        print(f❌ 이메일 발송 실패 {e})

if __name__ == __main__
    df = find_turning_stocks()
    send_email(df)
