# -*- coding: utf-8 -*-
"""청약홈 목록 페이지 실시간 스크래핑 — 공공데이터 API 지연 보완.
각 행: data-pbno/data-hmno/data-honm + 컬럼(구분/주택구분/공고일/청약기간/발표)."""
import re, html, urllib.request, io, sys

LISTS = [
    ("https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancListView.do", "APT"),
]
UA = {"User-Agent": "Mozilla/5.0"}

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")

def parse_rows(t):
    out = []
    for m in re.finditer(r'<tr\s+data-pbno="(\d+)"\s+data-hmno="(\d+)"\s+data-honm="([^"]*)"(.*?)</tr>', t, re.S):
        pbno, hmno, honm, body = m.groups()
        tds = [re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', x))).strip()
               for x in re.findall(r'<td[^>]*>(.*?)</td>', body, re.S)]
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', ' '.join(tds))
        htype = next((x for x in tds if x in ("민영", "국민")), "")
        out.append({
            "pbno": pbno, "hmno": hmno, "honm": honm.strip(),
            "htype": htype,
            "공고일": dates[0] if len(dates) > 0 else None,
            "접수시작": dates[1] if len(dates) > 1 else None,
            "접수종료": dates[2] if len(dates) > 2 else None,
            "발표": dates[3] if len(dates) > 3 else None,
        })
    return out

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    for url, label in LISTS:
        rows = parse_rows(fetch(url))
        print(f"[{label}] {len(rows)}개 행")
        for r in rows[:8]:
            print(f"  {r['hmno']} | {r['honm'][:24]} | {r['htype']} | 공고 {r['공고일']} | 접수 {r['접수시작']}~{r['접수종료']} | 발표 {r['발표']}")
