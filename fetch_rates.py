# -*- coding: utf-8 -*-
"""finlife(금융감독원 금융상품통합비교공시) 1금융권 주택담보대출 평균금리 수집 → rates_auto.js
인증키: _finlife_key.txt (finlife.fss.or.kr 오픈API에서 무료 발급)
"""
import json, os, sys, io, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(HERE, "_finlife_key.txt")
OUT = os.path.join(HERE, "rates_auto.js")
BASE = "http://finlife.fss.or.kr/finlifeapi/mortgageLoanProductsSearch.json"
TOP_FIN_GRP = "020000"  # 020000 = 은행(1금융권)


def get_key():
    if not os.path.exists(KEYFILE):
        return None
    with open(KEYFILE, encoding="utf-8") as f:
        return f.read().strip()


def fetch(auth):
    mids, mins, maxs = [], [], []
    asof = ""
    for page in range(1, 8):
        q = urllib.parse.urlencode({"auth": auth, "topFinGrpNo": TOP_FIN_GRP, "pageNo": page})
        url = f"{BASE}?{q}"
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("요청 실패 page", page, e)
            break
        res = data.get("result", {}) or {}
        err = str(res.get("err_cd", ""))
        if err and err != "000":
            print("API 오류:", err, res.get("err_msg", ""))
            break
        if not asof:
            bl = res.get("baseList", []) or []
            if bl:
                asof = str(bl[0].get("dcls_month", ""))
        for o in (res.get("optionList", []) or []):
            mn, mx = o.get("lend_rate_min"), o.get("lend_rate_max")
            try:
                mn = float(mn) if mn not in (None, "") else None
                mx = float(mx) if mx not in (None, "") else None
            except (TypeError, ValueError):
                mn = mx = None
            if mn is not None:
                mins.append(mn)
            if mx is not None:
                maxs.append(mx)
            if mn is not None and mx is not None:
                mids.append((mn + mx) / 2)
        try:
            maxp = int(res.get("max_page_no") or 1)
        except (TypeError, ValueError):
            maxp = 1
        if page >= maxp:
            break
    return mids, mins, maxs, asof


def fmt_asof(s):  # "202606" → "2026.6"
    s = (s or "").strip()
    if len(s) == 6 and s.isdigit():
        return f"{s[:4]}.{int(s[4:]):d}"
    return s


def main():
    auth = get_key()
    if not auth:
        print("⚠️ _finlife_key.txt 없음 — finlife.fss.or.kr 오픈API 인증키를 넣어주세요. rates_auto.js 미생성.")
        return
    mids, mins, maxs, asof = fetch(auth)
    if not mids:
        print("⚠️ 수집된 금리 없음 — 인증키/네트워크 확인. rates_auto.js 미생성.")
        return
    # 평균 최저금리(우대 적용 시 실제 체결가에 근접) — 각 상품 최저금리의 평균
    avg = round(sum(mins) / len(mins), 2) if mins else round(sum(mids) / len(mids), 2)
    mid = round(sum(mids) / len(mids), 2)  # 참고: 최저·최고 중간값 평균
    lo = round(min(mins), 2) if mins else avg
    hi = round(max(maxs), 2) if maxs else avg
    info = {"avg": avg, "mid": mid, "min": lo, "max": hi, "asof": fmt_asof(asof),
            "n": len(mins), "src": "finlife 1금융권 주담대 평균 최저금리"}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.RATE_INFO=" + json.dumps(info, ensure_ascii=False) + ";\n")
    print(f"✅ rates_auto.js 생성 — {info['asof']} 1금융권 평균 {avg}% (범위 {lo}~{hi}%, n={len(mids)})")


if __name__ == "__main__":
    main()
