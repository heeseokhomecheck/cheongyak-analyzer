# -*- coding: utf-8 -*-
"""정책 감시기 — 매일 부동산/대출 정책 뉴스를 훑어 '새 대책' 의심 항목 감지.
새 항목이 있으면 policy_alert.md 생성(워크플로우가 GitHub 이슈로 알림).
값(LTV/DSR 등)은 자동 변경하지 않음 — 사람이 보도자료 확인 후 POLICY 블록만 갱신.
"""
import os, sys, io, json, re, html, urllib.request, urllib.parse, datetime
import xml.etree.ElementTree as ET

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SEEN = os.path.join(HERE, "api_공고", "_policy_seen.json")   # Actions 캐시에 보존
ALERT = os.path.join(HERE, "policy_alert.md")

QUERY = "부동산 대출 규제 OR 주택담보대출 OR 청약 대책"
RSS = "https://news.google.com/rss/search?q=" + urllib.parse.quote(QUERY) + "&hl=ko&gl=KR&ceid=KR:ko"

# 제목에 [정책동작]+[대상] 둘 다 있어야 채택 (노이즈 감소)
ACT = ("대책", "규제", "발표", "강화", "완화", "개편", "시행", "도입")
TGT = ("대출", "주담대", "주택담보", "전세", "LTV", "DSR", "부동산", "청약", "가계부채", "한도", "분양가", "거주의무", "취득세")


def relevant(title):
    return any(a in title for a in ACT) and any(t in title for t in TGT)


def main():
    try:
        req = urllib.request.Request(RSS, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            xml = r.read().decode("utf-8", "replace")
    except Exception as e:
        print("RSS 요청 실패:", e)
        return
    try:
        root = ET.fromstring(xml)
    except Exception as e:
        print("RSS 파싱 실패:", e)
        return

    cutoff = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(days=2)
    items = []
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        if not relevant(title):
            continue
        # 최근 2일만
        try:
            dt = datetime.datetime.strptime(pub[:25], "%a, %d %b %Y %H:%M:%S")
            if dt < cutoff:
                continue
        except Exception:
            pass
        items.append({"title": title, "link": link, "pub": pub})

    seen = {}
    if os.path.exists(SEEN):
        try:
            seen = json.load(open(SEEN, encoding="utf-8"))
        except Exception:
            seen = {}
    key = lambda t: re.sub(r"\s+", "", t)[:60]
    fresh = [x for x in items if key(x["title"]) not in seen]

    # seen 갱신(최근 200건 유지)
    today = datetime.date.today().isoformat()
    for x in items:
        seen[key(x["title"])] = today
    if len(seen) > 200:
        seen = dict(sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:200])
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(seen, open(SEEN, "w", encoding="utf-8"), ensure_ascii=False)

    if not fresh:
        print(f"새 정책뉴스 없음 (검토대상 {len(items)}건 모두 기존).")
        if os.path.exists(ALERT):
            os.remove(ALERT)
        return

    with open(ALERT, "w", encoding="utf-8") as f:
        f.write(f"## ⚠️ 새 부동산/대출 정책 뉴스 {len(fresh)}건 감지 ({today})\n\n")
        f.write("정책 값이 바뀌었을 수 있어요. **보도자료 원문 확인 후** `index.html`의 POLICY_LOAN·POLICY_META·POLICY_ASOF만 갱신하세요.\n\n")
        for x in fresh:
            f.write(f"- **{x['title']}**  \n  {x['link']}\n")
    print(f"🔔 새 정책뉴스 {len(fresh)}건 → policy_alert.md 생성 (워크플로우가 이슈 알림)")
    for x in fresh[:5]:
        print("   •", x["title"][:60])


if __name__ == "__main__":
    main()
