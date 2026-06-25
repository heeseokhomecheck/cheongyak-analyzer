#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
청약홈 분양정보 OpenAPI(공공데이터포털, odcloud.kr 기반)에서 최근 공고를
긁어와 청약 분석기 도구의 JSON 프리셋으로 변환한다.

준비:
  1) https://www.data.go.kr/data/15098547/openapi.do 에서 '활용신청' (무료, 보통 즉시 승인)
  2) 발급받은 서비스키를 같은 폴더의 _apikey.txt 에 한 줄로 저장 (Decoding 키 권장)

사용:
  python fetch_cheongyak.py --probe          # 실제 응답 필드 1~3건 확인(스키마 매핑용)
  python fetch_cheongyak.py --since 2026-05-01   # 해당일 이후 공고만 프리셋 생성
  python fetch_cheongyak.py                    # 최근 공고 자동 수집

산출: 공고_<주택관리번호>.json (도구에서 JSON 불러오기), 또는 --probe 시 raw 출력.
"""
import sys, os, json, urllib.parse, urllib.request, io

BASE = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
EP_LIST = "getAPTLttotPblancDetail"   # APT 분양정보(공고 단위)
EP_MODEL = "getAPTLttotPblancMdl"     # 주택형별 공급정보(주택관리번호 단위)
HERE = os.path.dirname(os.path.abspath(__file__))

def get_key():
    p = os.path.join(HERE, "_apikey.txt")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    return os.environ.get("DATA_GO_KR_KEY", "")

def call(endpoint, params):
    key = get_key()
    if not key:
        sys.exit("서비스키가 없습니다. _apikey.txt 에 키를 저장하거나 DATA_GO_KR_KEY 환경변수를 설정하세요.")
    q = {"page": 1, "perPage": 100, "serviceKey": key}
    q.update(params)
    url = f"{BASE}/{endpoint}?" + urllib.parse.urlencode(q, safe="[]:=")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def probe():
    """실제 응답 구조를 보여줘서 필드 매핑을 확정하기 위한 모드."""
    data = call(EP_LIST, {"perPage": 3})
    print(json.dumps(data, ensure_ascii=False, indent=2)[:6000])

# --- 도구 스키마로 매핑 (실제 API 필드 확정본) ---
import re

def regulated_of(rec):
    if (rec.get("SPECLT_RDN_EARTH_AT") or "N") == "Y": return "투기과열지구"
    if (rec.get("MDAT_TRGET_AREA_SECD") or "N") == "Y": return "청약과열지역"
    return "비규제"

def supply_type_of(rec):
    nm = (rec.get("HOUSE_NM") or "")
    dtl = (rec.get("HOUSE_DTL_SECD_NM") or "")
    if "신혼희망" in nm or "신혼희망" in dtl: return "신혼희망타운"
    if dtl == "민영": return "민영"
    if "국민" in dtl or "공공" in dtl: return "공공"
    return "민영"

def region_of(rec):
    # HSSPLY_ADRES 에서 시/군/구 추출, 실패 시 광역명
    adr = rec.get("HSSPLY_ADRES") or ""
    m = re.search(r"(\S+?[시군구])", adr)
    return m.group(1) if m else (rec.get("SUBSCRPT_AREA_CODE_NM") or "")

def area_of(house_ty):
    # "059.9928A" -> 59.9928
    m = re.match(r"\s*([0-9]+\.?[0-9]*)", house_ty or "")
    return round(float(m.group(1)), 2) if m else 0

def split_ga_ch(area, gen, regulated):
    """민영 일반공급을 법정 가점:추첨 비율로 분할. 가점=내림, 단수는 추첨(법규). 규제지역×면적 반영."""
    if gen <= 0: return 0, 0, 0, 0
    # 가점제 비율
    if regulated == "투기과열지구":
        ga_r = 0.4 if area <= 60 else (0.7 if area <= 85 else 0.8)
    elif regulated == "청약과열지역":
        ga_r = 0.4 if area <= 60 else (0.7 if area <= 85 else 0.5)
    else:  # 비규제: 85㎡↓ 가점40 / 85㎡↑ 전량 추첨
        ga_r = 0.4 if area <= 85 else 0.0
    ga = int(gen * ga_r); ch = gen - ga          # 가점 내림 → 단수는 추첨
    muju_r = 0.75 if regulated in ("투기과열지구", "청약과열지역") else 0.0
    chMuju = int(ch * muju_r); chMix = ch - chMuju  # 규제지역 추첨: 무주택 75% 우선
    return ga, ch, chMuju, chMix

# 특공 유형: (도구표시명, API필드, 민영 incSingle/incDual/asset/car, 공공 incSingle/incDual/asset/car)
SPECIAL_MAP = [
    ("신생아",     "NWBB_HSHLDCO",                (140,160,33100,0), (140,200,21550,4542)),
    ("신혼부부",   "NWWDS_HSHLDCO",               (100,120,33100,0), (130,200,21550,4542)),
    ("생애최초",   "LFE_FRST_HSHLDCO",            (130,130,33100,0), (130,200,21550,4542)),
    ("다자녀가구", "MNYCH_HSHLDCO",               (0,0,0,0),         (120,200,21550,4542)),
    ("노부모부양", "OLD_PARNTS_SUPORT_HSHLDCO",   (0,0,0,0),         (120,200,21550,4542)),
    ("기관추천",   "INSTT_RECOMEND_HSHLDCO",      (0,0,0,0),         (0,0,0,0)),
    ("협의양도인", "TRANSR_INSTT_ENFSN_HSHLDCO",  (0,0,0,0),         (0,0,0,0)),
]

def build_special(models, stype):
    out = []
    pub = stype != "민영"
    for disp, field, mn, gk in SPECIAL_MAP:
        qty = sum(int(t.get(field, 0) or 0) for t in models)
        if qty <= 0: continue
        inc_s, inc_d, asset, car = (gk if pub else mn)
        out.append({"type": disp, "apply": "국민" if pub else "공통",
                    "incSingle": inc_s, "incDual": inc_d, "qty": qty, "lottery": 0,
                    "asset": asset, "car": car,
                    "memo": "API 자동생성 — 소득%·자산은 기본값(공고문에서 확인 권장). 추첨세대수 미반영."})
    return out

def map_records(list_json, max_items=None):
    presets = []
    recs = list_json.get("data", [])
    if max_items: recs = recs[:max_items]
    for rec in recs:
        mng = rec.get("HOUSE_MANAGE_NO")
        stype = supply_type_of(rec)
        regulated = regulated_of(rec)
        try:
            md = call(EP_MODEL, {"perPage": 100, "cond[HOUSE_MANAGE_NO::EQ]": mng}).get("data", [])
        except Exception as e:
            print(f"  (주택형별 조회 실패 {mng}: {e})", file=sys.stderr); md = []
        htype = "민영" if stype == "민영" else "국민"
        types = []
        max_price = 0
        for t in md:
            area = area_of(t.get("HOUSE_TY"))
            gen = int(t.get("SUPLY_HSHLDCO", 0) or 0)
            sp = int(t.get("SPSPLY_HSHLDCO", 0) or 0)
            try: max_price = max(max_price, int(t.get("LTTOT_TOP_AMOUNT", 0) or 0))
            except: pass
            ga, ch, chMuju, chMix = split_ga_ch(area, gen, regulated) if stype == "민영" else (0,0,0,0)
            try: tp = int(t.get("LTTOT_TOP_AMOUNT", 0) or 0)
            except: tp = 0
            types.append({"name": t.get("HOUSE_TY","?"), "area": area, "htype": htype,
                          "deposit": 300, "total": gen+sp, "gen": gen, "price": tp,
                          "ga": ga, "ch": ch, "chMuju": chMuju, "chMix": chMix})
        presets.append({
            "name": rec.get("HOUSE_NM", "?"),
            "region": region_of(rec),
            "haedangMonths": 0,
            "regulated": regulated,
            "supplyType": stype,
            "acctMinMonths": 24 if regulated != "비규제" else 12,
            "redraw": 10 if (rec.get("PARCPRC_ULS_AT")=="Y" or regulated!="비규제") else 0,
            "incomeBase": [753,753,753,880,933,991,1049,1106],
            "types": types,
            "special": build_special(md, stype),
            "_source": (lambda bg,en: {"공고번호": rec.get("PBLANC_NO"), "주택관리번호": mng,
                        "공고일": norm_date(rec.get("RCRIT_PBLANC_DE")),
                        "접수시작": bg, "접수종료": en,
                        "특공종료": norm_date(rec.get("SPSPLY_RCEPT_ENDDE")), "발표": norm_date(rec.get("PRZWNER_PRESNATN_DE")),
                        "분양가최고": max_price, "공고URL": rec.get("PBLANC_URL")})(*pick_dates(rec)),
        })
    return presets

MASTER = os.path.join(HERE, "api_공고", "_master.json")
PRESETS_JS = os.path.join(HERE, "presets_auto.js")

def merge_scraped(master):
    """청약홈 목록 실시간 스크랩 → master 병합. 신규(API 미반영)는 경량 엔트리, 기존은 일정만 갱신."""
    try:
        from scrape_applyhome import parse_rows, fetch, LISTS
    except Exception as e:
        print(f"  (스크래퍼 로드 실패: {e})", file=sys.stderr); return 0
    added = 0
    for url, label in LISTS:
        try: rows = parse_rows(fetch(url))
        except Exception as e:
            print(f"  (청약홈 {label} 스크랩 실패: {e})", file=sys.stderr); continue
        new_here = 0
        for r in rows:
            mng = r["hmno"]
            if mng in master:  # 기존 → 스크랩 일정으로 갱신(웹이 더 신선)
                s = master[mng].get("_source", {})
                if r["접수종료"]: s["접수시작"], s["접수종료"] = r["접수시작"], r["접수종료"]
                if r["발표"]: s["발표"] = r["발표"]
                continue
            stype = "신혼희망타운" if "신혼희망" in r["honm"] else ("공공" if r["htype"] == "국민" else "민영")
            master[mng] = {
                "name": r["honm"], "region": "", "haedangMonths": 0, "regulated": "비규제",
                "supplyType": stype, "acctMinMonths": 0, "redraw": 0,
                "incomeBase": [753,753,753,880,933,991,1049,1106], "types": [], "special": [],
                "_scraped": True,
                "_source": {"공고번호": r["pbno"], "주택관리번호": mng, "공고일": r["공고일"],
                            "접수시작": r["접수시작"], "접수종료": r["접수종료"], "발표": r["발표"],
                            "분양가최고": 0,
                            "공고URL": f"https://www.applyhome.co.kr/ai/aia/selectAPTLttotPblancDetailView.do?houseManageNo={mng}&pblancNo={r['pbno']}"},
            }
            added += 1; new_here += 1
        print(f"  [청약홈 {label}] 스크랩 {len(rows)}건 / 신규 {new_here}건")
    return added

def norm_date(s):
    if not s: return None
    s = str(s)
    if len(s) == 8 and s.isdigit(): return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s

# 접수 일정 필드는 공고 유형마다 다름(RCEPT/SUBSCRPT_RCEPT/GNRL_RCEPT/SPSPLY_RCEPT).
# 비어있지 않은 것을 자동으로 골라 (시작, 종료) 반환 — 누락 방지.
_DATE_PAIRS = [("RCEPT_BGNDE","RCEPT_ENDDE"),("SUBSCRPT_RCEPT_BGNDE","SUBSCRPT_RCEPT_ENDDE"),
               ("GNRL_RCEPT_BGNDE","GNRL_RCEPT_ENDDE"),("SPSPLY_RCEPT_BGNDE","SPSPLY_RCEPT_ENDDE")]
def pick_dates(rec):
    best=(None,None)
    for b,e in _DATE_PAIRS:
        bv,ev = norm_date(rec.get(b)), norm_date(rec.get(e))
        if ev: return (bv,ev)          # 종료일 있는 첫 세트 우선
        if bv and not best[0]: best=(bv,ev)
    return best

def call_pages(ep, max_pages=12, params=None):
    out=[]
    for pg in range(1, max_pages+1):
        try:
            chunk = call(ep, {**(params or {}), "page":pg, "perPage":300}).get("data", [])
        except Exception:
            break   # 페이지 초과 등 오류 시 수집 종료(부분 결과 유지)
        out += chunk
        if len(chunk) < 300: break
    return out

# APT 외 공급유형 — 엔드포인트별 날짜 필드명이 다름. 특공/가점 없음(대부분 추첨).
OTHER_ENDPOINTS = [
    {"ep":"getUrbtyOfctlLttotPblancDetail","mdl":"getUrbtyOfctlLttotPblancMdl","stype":"오피스텔",  "bgn":"SUBSCRPT_RCEPT_BGNDE","end":"SUBSCRPT_RCEPT_ENDDE"},
    {"ep":"getRemndrLttotPblancDetail",    "mdl":"getRemndrLttotPblancMdl",    "stype":"무순위",    "bgn":"GNRL_RCEPT_BGNDE",    "end":"GNRL_RCEPT_ENDDE"},
    {"ep":"getOPTLttotPblancDetail",       "mdl":"getOPTLttotPblancMdl",       "stype":"임의공급",  "bgn":"SPSPLY_RCEPT_BGNDE",  "end":"SPSPLY_RCEPT_ENDDE"},
]

def enrich_prices(master):
    """노출 대상(접수 안 끝난) 공고의 타입별 분양가를 모델에서 보강. 이름(HOUSE_TY)으로 매칭."""
    import datetime
    TODAY = datetime.date.today().isoformat()
    mdl = {"민영":EP_MODEL, "공공":EP_MODEL, "신혼희망타운":EP_MODEL,
           "오피스텔":"getUrbtyOfctlLttotPblancMdl", "무순위":"getRemndrLttotPblancMdl", "임의공급":"getOPTLttotPblancMdl"}
    n = 0
    for mng, p in master.items():
        end = p.get("_source", {}).get("접수종료")
        if not (end and end >= TODAY): continue           # 노출 대상만
        types = p.get("types", [])
        if not types or all(t.get("price") for t in types): continue
        ep = mdl.get(p.get("supplyType"))
        if not ep: continue
        try:
            md = call(ep, {"perPage": 100, "cond[HOUSE_MANAGE_NO::EQ]": mng}).get("data", [])
        except Exception: continue
        pm = {}
        for t in md:
            nm = t.get("HOUSE_TY") or t.get("TP") or ""
            try: pr = int(t.get("LTTOT_TOP_AMOUNT") or t.get("SUPLY_AMOUNT") or 0)
            except: pr = 0
            if pr: pm[nm] = max(pm.get(nm, 0), pr)
        for t in types:
            if not t.get("price"): t["price"] = pm.get(t.get("name"), 0)
        n += 1
    print(f"  분양가 보강: {n}건")

def update_others(master, max_new=None):
    """오피스텔·무순위·임의공급 등 APT 외 유형을 master에 누적/갱신. 마감 지난 신규는 제외."""
    import datetime
    TODAY = datetime.date.today().isoformat()
    added = 0
    for cfg in OTHER_ENDPOINTS:
        try:
            listing = call_pages(cfg["ep"])   # 전체 페이지네이션 (무순위 1,600+건 포함)
        except Exception as e:
            print(f"  ({cfg['stype']} 목록 실패: {e})", file=sys.stderr); continue
        for r in listing: r["_pub"] = norm_date(r.get("RCRIT_PBLANC_DE"))
        listing = [r for r in listing if r.get("_pub")]
        listing.sort(key=lambda r: r["_pub"], reverse=True)
        new_here = 0
        for rec in listing:
            mng = str(rec.get("HOUSE_MANAGE_NO"))
            bgn, end = pick_dates(rec)   # 여러 접수일 필드 중 자동 선택
            if mng in master:  # 기존 → 일정만 갱신
                s = master[mng].get("_source", {})
                s["접수시작"], s["접수종료"] = bgn, end
                continue
            if end and end < TODAY: continue  # 마감 지난 신규는 추가 안 함(어차피 노출 안 됨)
            if max_new and new_here >= max_new: continue
            types, maxp = [], 0
            try:
                md = call(cfg["mdl"], {"perPage": 100, "cond[HOUSE_MANAGE_NO::EQ]": mng}).get("data", [])
                for t in md:
                    try: area = round(float(t.get("EXCLUSE_AR", 0) or 0), 2)
                    except: area = 0
                    gen = int(t.get("SUPLY_HSHLDCO", 0) or 0)
                    try: maxp = max(maxp, int(t.get("SUPLY_AMOUNT", 0) or 0))
                    except: pass
                    try: tp = int(t.get("SUPLY_AMOUNT", 0) or 0)
                    except: tp = 0
                    types.append({"name": t.get("TP") or t.get("HOUSE_TY") or "?", "area": area,
                                  "htype": cfg["stype"], "deposit": 0, "total": gen, "gen": gen, "price": tp,
                                  "ga": 0, "ch": 0, "chMuju": 0, "chMix": 0})
            except Exception as e:
                print(f"  ({cfg['stype']} 모델 실패 {mng}: {e})", file=sys.stderr)
            master[mng] = {
                "name": rec.get("HOUSE_NM", "?"), "region": region_of(rec),
                "haedangMonths": 0, "regulated": "비규제", "supplyType": cfg["stype"],
                "acctMinMonths": 0, "redraw": 0,
                "incomeBase": [753,753,753,880,933,991,1049,1106],
                "types": types, "special": [],
                "_source": {"공고번호": rec.get("PBLANC_NO"), "주택관리번호": mng, "공고일": rec["_pub"],
                            "접수시작": bgn, "접수종료": end, "발표": norm_date(rec.get("PRZWNER_PRESNATN_DE")),
                            "분양가최고": maxp, "공고URL": rec.get("PBLANC_URL")},
            }
            added += 1; new_here += 1
        print(f"  [{cfg['stype']}] 신규 {new_here}건")
    return added

def auto_update(max_new=None):
    """신규 공고만 추가 누적 → _master.json + presets_auto.js 생성. (스케줄러용)"""
    os.makedirs(os.path.dirname(MASTER), exist_ok=True)
    master = {}
    if os.path.exists(MASTER):
        try: master = json.load(open(MASTER, encoding="utf-8"))
        except Exception: master = {}
    import datetime as _dt
    TODAY = _dt.date.today().isoformat()
    listing = call_pages(EP_LIST)            # 전체 페이지네이션 (APT 2,700+건)
    listing = [r for r in listing if r.get("RCRIT_PBLANC_DE")]
    # 신규 = master에 없고 + 접수 안 끝난 것만(마감 지난 신규는 모델 호출/추가 안 함)
    new = []
    for r in listing:
        mng = str(r.get("HOUSE_MANAGE_NO"))
        ex = master.get(mng)
        if ex and not ex.get("_scraped"): continue   # 정식 데이터 있으면 skip / 스크랩분은 API로 업그레이드
        en = pick_dates(r)[1]
        if en and en < TODAY: continue
        new.append(r)
    new.sort(key=lambda r: r.get("RCRIT_PBLANC_DE"), reverse=True)
    if max_new: new = new[:max_new]
    added = 0
    for p in map_records({"data": new}):
        master[str(p["_source"]["주택관리번호"])] = p
        added += 1
        print(f"  + [{p['supplyType']}/{p['regulated']}] {p['name'][:24]} | {p['region']} ({p['_source'].get('접수종료')})")
    # 기존 APT 항목의 접수 일정 갱신 — 모델 재호출 없이 저렴
    by_mng = {str(r.get("HOUSE_MANAGE_NO")): r for r in listing}
    for mng, p in master.items():
        r = by_mng.get(mng)
        if r and isinstance(p.get("_source"), dict):
            bg, en = pick_dates(r)
            p["_source"]["접수시작"], p["_source"]["접수종료"] = bg, en
            p["_source"]["발표"] = norm_date(r.get("PRZWNER_PRESNATN_DE"))
    # APT 외 유형(오피스텔·무순위·임의공급) 추가/갱신
    added += update_others(master, max_new=max_new)
    # 청약홈 웹페이지 실시간 스크래핑 — API 지연분(오늘 새로 뜬 공고) 보완
    added += merge_scraped(master)
    enrich_prices(master)   # 노출 공고 타입별 분양가 보강
    # 민영 타입별 가점/추첨 재계산 — 규제지역 보정까지 반영해 일관 기록
    for p in master.values():
        if p.get("supplyType") == "민영":
            for t in p.get("types", []):
                ga, ch, cm, cx = split_ga_ch(t.get("area", 0), int(t.get("gen", 0) or 0), p.get("regulated"))
                t["ga"], t["ch"], t["chMuju"], t["chMix"] = ga, ch, cm, cx
    json.dump(master, open(MASTER, "w", encoding="utf-8"), ensure_ascii=False)
    # presets_auto.js 에는 '노출 대상'만(접수중·예정·막 마감) → 파일 경량화. 전체 이력은 _master.json.
    import datetime
    cutoff = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    def relevant(p):
        s = p.get("_source", {}); end = s.get("접수종료"); start = s.get("접수시작")
        if end: return end >= cutoff               # 마감 10일 이내~미래
        if start: return start >= cutoff           # 종료일 없으면 시작일로
        return False
    showable = [p for p in sorted(master.values(), key=lambda p:(p.get("_source",{}).get("접수종료") or "")) if relevant(p)]
    with open(PRESETS_JS, "w", encoding="utf-8") as f:
        f.write("/* 자동 생성 — 청약홈 API. fetch_cheongyak.py 가 매시간 갱신. 노출 대상만 포함 */\n")
        f.write("window.AUTO_PRESETS = " + json.dumps(showable, ensure_ascii=False) + ";\n")
    print(f"갱신 완료: 신규 {added}건 / 이력 {len(master)}개 / 노출 {len(showable)}개 → presets_auto.js")

def main():
    args = sys.argv[1:]
    if "--probe" in args:
        probe(); return
    if "--manual" in args:
        since = args[args.index("--since")+1] if "--since" in args else None
        max_items = int(args[args.index("--max")+1]) if "--max" in args else 15
        params = {"perPage": 100}
        if since: params["cond[RCRIT_PBLANC_DE::GTE]"] = since
        presets = map_records(call(EP_LIST, params), max_items=max_items)
        outdir = os.path.join(HERE, "api_공고"); os.makedirs(outdir, exist_ok=True)
        for p in presets:
            fn = os.path.join(outdir, f"공고_{p['_source']['주택관리번호']}.json")
            json.dump(p, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            print(f"OK {p['name'][:24]} -> {os.path.basename(fn)}")
        return
    # 기본: 자동 누적 갱신 (스케줄러)
    mx = int(args[args.index("--max")+1]) if "--max" in args else None
    auto_update(max_new=mx)

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    main()
