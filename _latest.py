# -*- coding: utf-8 -*-
import fetch_cheongyak as F, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = F.call("getAPTLttotPblancDetail", {"perPage": 300}).get("data", [])
d = [r for r in d if r.get("RCRIT_PBLANC_DE")]
d.sort(key=lambda r: r["RCRIT_PBLANC_DE"], reverse=True)
print("총", len(d), "건 / 최신 모집공고일순 상위 8건:")
for r in d[:8]:
    nm = (r.get("HOUSE_NM") or "?")[:30]
    print(" ", r["RCRIT_PBLANC_DE"], "|", nm, "|", r.get("SUBSCRPT_AREA_CODE_NM",""),
          "|", r.get("HOUSE_DTL_SECD_NM",""), "| 접수", r.get("RCEPT_BGNDE","?"))
