# 청약 분석기

분양공고를 내 조건으로 풀어주는 단일 페이지 도구 — 어떤 전형(특공/일반·가점/추첨/순차제)을 넣을지, 소득·자산컷, 취득세·대출·실입주/전세 현금, 갭투자 가능성까지 한 화면에.

## 구성

- **`index.html`** — 도구 본체 (vanilla JS, 빌드 불필요). 정적 호스팅(GitHub Pages)으로 서빙.
- **`presets_auto.js`** — 청약홈 공고 자동수집 데이터 (`window.AUTO_PRESETS`)
- **`rates_auto.js`** — 1금융권 평균 주담대 금리 (`window.RATE_INFO`)
- **`lh_auto.js`** — LH 청약플러스 공공분양 (`window.LH_PRESETS`)

## 자동 데이터 갱신

`.github/workflows/fetch.yml` 가 **매시간** 아래 수집기를 실행해 위 3개 데이터 파일을 갱신·커밋한다(내 PC·클로드와 무관, GitHub 서버에서 동작).

| 수집기 | 소스 | 키(Secret) |
|--|--|--|
| `fetch_cheongyak.py` | 청약홈 OpenAPI + 웹스크랩 | `DATA_GO_KR_KEY` |
| `fetch_rates.py` | 금융감독원 finlife | `FINLIFE_KEY` |
| `fetch_lh.py` | LH 분양임대공고문 API | `DATA_GO_KR_KEY` |

상태파일 `api_공고/_master.json` 은 Actions 캐시로 보존(레포 비대화 방지). 인증키는 **GitHub Secrets**로만 관리(코드/커밋에 없음).

## 로컬 실행

`run_fetch.bat` 더블클릭(윈도우 작업 스케줄러용) → 로컬에서 수집. 도구는 `python -m http.server` 로 띄워 `index.html` 확인.
