@echo off
REM 청약홈 API 자동수집 — Windows 작업 스케줄러가 매시간 실행
cd /d "C:\Users\tmani\cheongyak-analyzer"
"C:\Users\tmani\AppData\Local\Python\pythoncore-3.14-64\python.exe" fetch_cheongyak.py >> fetch.log 2>&1
"C:\Users\tmani\AppData\Local\Python\pythoncore-3.14-64\python.exe" fetch_rates.py >> fetch.log 2>&1
REM fetch_lh.py: LH 청약플러스 공공분양 아파트 수집(상가·임대·매각 제외 필터)
"C:\Users\tmani\AppData\Local\Python\pythoncore-3.14-64\python.exe" fetch_lh.py >> fetch.log 2>&1
