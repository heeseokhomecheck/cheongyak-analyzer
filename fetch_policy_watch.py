# -*- coding: utf-8 -*-
"""정책 감시기 — 정부 '공식 보도자료'(대한민국 정책브리핑 korea.kr)만 감시.
금융위(대출 규제) + 국토부(부동산 대책) 보도자료에서 부동산/대출 관련 새 글 감지.
※ 기사·논평이 아니라 정부 공식 발표만 인용. 값(LTV/DSR 등)은 자동 변경 안 함 — 사람이 보도자료 확인 후 POLICY 블록만 갱신.
"""
import os, sys, io, json, re, html, urllib.request, datetime
import xml.etree.ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SEEN = os.path.join(HERE, "api_공고", "_policy_seen.json")   # Actions 캐시에 보존
ALERT = os.path.join(HERE, "policy_alert.md")

# 정부 공식 보도자료 RSS (대한민국 정책브리핑)
FEEDS = [
    ("금융위", "https://www.korea.kr/rss/dept_fsc.xml"),
    ("국토부", "https://www.korea.kr/rss/dept_molit.xml"),
]
# 부동산/대출 정책 키워드(하나라도 있으면 채택) — 인사·일반행사 노이즈 제외
KW = ("부동산", "주택", "주담대", "주택담보", "대출", "LTV", "DSR", "가계부채",
      "청약", "전세", "분양", "거주의무", "주택시장", "임대", "전매", "취득세", "양도세", "종부세", "공급")


def relevant(title):
    return any(k in title for k in KW)


def main():
    cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=3)
    items = []
    for dept, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                xml = r.read().decode("utf-8", "replace")
            root = ET.fromstring(xml)
        except Exception as e:
            print(f"{dept} 보도자료 피드 실패:", e)
            continue
        for it in root.iter("item"):
            title = html.unescape((it.findtext("title") or "").strip())
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            if not relevant(title):
                continue
            try:
                dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S")
                if dt < cutoff:
                    continue
            except Exception:
                pass
            items.append({"title": title, "link": link, "pub": pub, "dept": dept})

    seen = {}
    if os.path.exists(SEEN):
        try:
            seen = json.load(open(SEEN, encoding="utf-8"))
        except Exception:
            seen = {}
    key = lambda t: re.sub(r"\s+", "", t)[:60]
    fresh = [x for x in items if key(x["title"]) not in seen]

    today = datetime.date.today().isoformat()
    for x in items:
        seen[key(x["title"])] = today
    if len(seen) > 300:
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:300])
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(seen, open(SEEN, "w", encoding="utf-8"), ensure_ascii=False)

    if not fresh:
        print(f"새 정책 보도자료 없음 (검토대상 {len(items)}건 모두 기존).")
        if os.path.exists(ALERT):
            os.remove(ALERT)
        return

    with open(ALERT, "w", encoding="utf-8") as f:
        f.write(f"## 🏛️ 새 정부 보도자료(부동산/대출) {len(fresh)}건 ({today})\n\n")
        f.write("**정부 공식 발표**입니다. 정책 값이 바뀌었을 수 있어요 — 원문 확인 후 `index.html`의 "
                "`POLICY_LOAN`·`POLICY_META`·`POLICY_ASOF`만 갱신하세요. (기사·논평 아님, 보도자료 원문 인용)\n\n")
        for x in fresh:
            f.write(f"- **[{x['dept']}] {x['title']}**  \n  {x['link']}\n")
    print(f"🔔 새 정부 보도자료 {len(fresh)}건 → policy_alert.md 생성")
    for x in fresh[:6]:
        print(f"   • [{x['dept']}] {x['title'][:55]}")


if __name__ == "__main__":
    main()
