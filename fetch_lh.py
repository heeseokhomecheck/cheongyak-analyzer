# -*- coding: utf-8 -*-
"""LH(한국토지주택공사) 분양임대공고문 → lh_auto.js (공공분양 보강)
data.go.kr '한국토지주택공사_분양임대공고문 조회 서비스'(B552555) 활용신청 후 같은 _apikey.txt 키로 동작.
첫 정상 호출 시 응답 구조를 _lh_debug.json 에 덤프 → 필드 매핑 확정에 사용.
"""
import json, os, sys, io, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(HERE, "_apikey.txt")
LH_KEYFILE = os.path.join(HERE, "_lh_key.txt")  # LH 전용 키(있으면 우선) — 청약홈 키와 다를 때
OUT = os.path.join(HERE, "lh_auto.js")
DEBUG = os.path.join(HERE, "_lh_debug.json")
# 경로 후보(상세기능 경로=이중, End Point=단일). 게이트웨이 열리면 200 주는 쪽을 자동 채택.
BASES = ["https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1",
         "https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1"]
_ok_base = None

# 순수 아파트 공공분양/분양주택만. 유형(분양주택·공공분양) 기준 + 비아파트/매각 키워드 제외.
KEEP_UPP = ("분양주택", "공공분양")  # UPP_AIS_TP_NM에 포함되면 분양계열
EXCLUDE_NM = ("잔여", "매각", "미분양", "수의계약", "중단", "단지내", "상가",
              "오피스텔", "토지", "점포", "임대", "도시형생활주택")


def get_key():
    for f in (LH_KEYFILE, KEYFILE):  # LH 전용 키 우선
        if os.path.exists(f):
            return open(f, encoding="utf-8").read().strip()
    return None


def fetch_page(key, page, sz=100):
    import datetime
    global _ok_base
    yr = datetime.date.today().year
    # stdt(조회시작년도) 필수. 2년 전부터 조회해 최근 공고 확보.
    q = urllib.parse.urlencode({"serviceKey": key, "stdt": yr - 2, "PG_SZ": sz, "PAGE": page}, safe="=")
    cands = [_ok_base] if _ok_base else BASES
    last = None
    for base in cands:
        try:
            req = urllib.request.Request(f"{base}?{q}", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            _ok_base = base  # 성공 경로 기억
            return data
        except Exception as e:
            last = e
    raise last


def extract_records(payload):
    """LH 응답: [{dsSch:[...]},{dsList:[...records...],resHeader:[{SS_CODE:'Y'}]}] → dsList 반환.
    (미리보기로 확인한 실제 구조)"""
    blocks = payload if isinstance(payload, list) else [payload]
    for b in blocks:
        if isinstance(b, dict) and isinstance(b.get("dsList"), list):
            return b["dsList"]
    return []


def first(rec, *keys):
    for k in keys:
        if rec.get(k) not in (None, ""):
            return rec.get(k)
    return ""


def is_sale(rec):
    upp = rec.get("UPP_AIS_TP_NM") or ""
    ais = rec.get("AIS_TP_CD_NM") or ""
    nm = rec.get("PAN_NM") or ""
    if "행복주택" in ais:                          # 행복주택(신혼희망)=임대형 제외
        return False
    if not any(k in upp for k in KEEP_UPP):        # 분양주택·공공분양(신혼희망) 유형만
        return False
    if any(k in nm for k in EXCLUDE_NM):           # 오피스텔·상가·토지·임대·매각·잔여 제외
        return False
    return True


def dedup_name(nm):
    """정정공고 등 접두어 제거한 정규화 이름(중복판정용)."""
    import re
    return re.sub(r"\[[^\]]*\]", "", nm or "").replace(" ", "")


def norm_date(s):
    """'2026.07.21' / '20260721' → '2026-07-21' (도구 parseD가 '-' 분리)."""
    digits = "".join(ch for ch in str(s or "") if ch.isdigit())
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}" if len(digits) == 8 else ""


def main():
    key = get_key()
    if not key:
        print("⚠️ _apikey.txt 없음")
        return
    all_recs, dumped = [], False
    fetched_any = False
    for page in range(1, 8):
        try:
            payload = fetch_page(key, page)
            fetched_any = True
        except Exception as e:
            print(f"요청 실패 page{page}: {e}")
            if page == 1:
                print("→ LH API 활용신청(승인) 여부를 확인하세요. data.go.kr > 마이페이지 > 활용신청.")
            break
        recs = extract_records(payload)
        if page == 1 and not dumped:
            json.dump(payload if isinstance(payload, (list, dict)) else {}, open(DEBUG, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            dumped = True
            if recs:
                print("샘플 레코드 키:", list(recs[0].keys()))
        if not recs:
            break
        all_recs.extend(recs)
        if len(recs) < 100:
            break

    if not fetched_any:
        print("⚠️ LH API 호출 실패(미승인 추정) — lh_auto.js 미생성. 활용신청 후 재시도.")
        return
    sales = [r for r in all_recs if is_sale(r)]
    # 정정공고 중복 제거: 정규화 이름별로 PAN_DT(공고일) 최신 1건만
    best = {}
    for r in sales:
        k = dedup_name(r.get("PAN_NM"))
        if k not in best or str(r.get("PAN_DT") or "") >= str(best[k].get("PAN_DT") or ""):
            best[k] = r
    sales = list(best.values())
    print(f"수집 {len(all_recs)}건 중 공공분양(중복제거) {len(sales)}건")
    presets = []
    for r in sales:
        nm = first(r, "PAN_NM", "BSNS_MBY_NM", "AIS_TP_CD_NM") or "LH 분양공고"
        stype = "신혼희망타운" if "신혼희망" in nm else "공공"  # 신혼희망=배점·총자산, 공공=순차제
        presets.append({
            "name": nm,
            "region": first(r, "CNP_CD_NM", "ARA_NM", "CTPV_NM"),
            "supplyType": stype,
            "_lh": True, "_scraped": True,
            "types": [], "special": [],
            "_source": {
                "접수시작": norm_date(first(r, "PAN_NT_ST_DT", "RCRIT_BGN_DT")),
                "접수종료": norm_date(first(r, "CLSG_DT", "PAN_NT_END_DT", "RCRIT_END_DT")),
                "공고URL": first(r, "DTL_URL", "AIS_TP_CD"),
            },
        })
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.LH_PRESETS=" + json.dumps(presets, ensure_ascii=False) + ";\n")
    print(f"✅ lh_auto.js 생성 — 공공분양 {len(presets)}건 (구조 확인 후 필드 매핑 보정 필요시 _lh_debug.json 참고)")


if __name__ == "__main__":
    main()
