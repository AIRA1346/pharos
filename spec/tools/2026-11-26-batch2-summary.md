# 파로스 2차 대량 확장(107종) — 실측·판단 기록 (2026-11-26)

## 규모
- 도메인 3 · 대분류 15 · 비교군 22 · **107종** (87 → 107)
- 신규 대분류 3: `ai-image-gen`(AI · 이미지·디자인 생성), `document-design`(앱 · 문서·디자인), `strategy-tactics`(게임 · 전략·전술 RPG)
- 신규 비교군 4: `ai-image-gen`(AI 이미지 생성 5) · `pdf-tools`(PDF 뷰어·편집 5) · `image-editors`(이미지·그래픽 편집 5) · `turn-based-strategy`(턴제 전략·전술 5)

## 판정 (v0.5.0 · 0.50/0.25/0.25)
| 비교군 | 항목 | 점수 | 판정 | 핵심 근거 |
|---|---|---|---|---|
| AI 이미지 생성 | ComfyUI | 91.5 | 🟢 | GPL·노드 워크플로·데스크톱 무료, Comfy Cloud 월 $20 |
| | FLUX | 88.0 | 🟢 | 이미지당 $0.014~$0.07, 오픈 웨이트 [dev] 비상업 |
| | InvokeAI | 84.5 | 🟢 | Apache-2.0·캔버스·멀티유저, 공식 호스팅 2025-10 종료 |
| | Adobe Firefly | 79.0 | 🟡 | 상업적 안전성 최상, 무료 일일 생성 수치 미공개 |
| | Midjourney | 77.0 | 🟡 | 무료 플랜 없음, Fast 시간 이월 없음, 비공개 Pro부터 |
| PDF 뷰어·편집 | PDFgear | 86.0 | 🟢 | Play 4.50★(52,923) · 전 플랫폼 무료 · 워터마크 없음 |
| | SumatraPDF | 85.0 | 🟢 | Windows 전용·3.6.1·주석/서명, 본문 편집 없음 |
| | Okular | 83.0 | 🟢 | KDE 26.08.3·주석/양식·4플랫폼 |
| | Adobe Acrobat | 81.5 | 🟡 | Play 4.51★(809만)지만 편집 구독·AI 애드온·해지 위약 50% |
| | Foxit PDF Editor | 77.5 | 🟡 | 연 $129.99·모바일 Editor+·Play 3.89★ |
| 이미지·그래픽 편집 | Canva | 87.5 | 🟢 | Play 4.79★(2,791만)·Pro 월 ₩9,900 |
| | Photopea | 85.5 | 🟢 | 브라우저 PSD·기간권 €8~€50(구독 아님) |
| | GIMP | 85.0 | 🟢 | 3.2.8·비파괴 레이어·무료 |
| | Adobe Photoshop | 81.5 | 🟡 | 단일 앱 크레딧 500→25, Photography가 더 싸고 40배 |
| | Krita | 80.0 | 🟢 | 5.3.5·페인팅, 안드로이드 3.30★ 표본은 72로 보수 보정 |
| 턴제 전략·전술 | Baldur's Gate 3 | 94.0 | 🟢 | Steam 96%(454,406)·최근 97% |
| | Into the Breach | 90.5 | 🟢 | 93%·완결작 면제 |
| | Darkest Dungeon | 86.5 | 🟢 | 90%·2026-10 새 DLC |
| | XCOM 2 | 84.5 | 🟢 | 85%·완결작 면제(2022-08 이후 패치 없음) |
| | Civilization VI | 83.0 | 🟢 | 85%(108,296)·2026-11 핫픽스 |

## 파이프라인 실측
- `auto_collect.py`: 16건 자동 수집(아이콘 16), 요청 88건, 평균 자동 채움 65.8% (항목당 1.19초)
  - 첫 실행에서 PDFgear 는 Play 패키지명(`com.pdfeditor.pdfeditorandriod`)을 확인해 재수집.
- 수동 초안 4건: Midjourney·Adobe Firefly·GIMP·Photopea (공개 API 없음) → Wikimedia 공식 마크·공식 사이트 아이콘.
- 아이콘 20/20 신규, 전체 107/107 192×192 webp. FLUX·Midjourney는 검은 로고라 흰 배경에 합성(다크 테마 대응).
- `apply_review.py`: 20건 전부 스키마·의미 PASS, TODO 문자열 0.

## 검증
- `validate.py`: PASS — 107건 · 계층 3/15/22 · 아이콘 107/107 · 영문 107/107 · 음성 27/27 · 완결작 9/9 · 강도 3단계 10/10
- `verify_ui.py`: **734/734 PASS** — 신규 4비교군 29항목(5건·192px 아이콘·대표 판정·상세 가격·EN 한글 0) 추가.
  날짜 기반 신선도 단언은 오늘 날짜로 계산하도록 수정(11-26 기준 2일).
- `live_check_v11.py`: **33/33 PASS** — 라이브 107건·22비교군, 홈 22블록, 4비교군 아이콘, ComfyUI/BG3 상세, 390px 넘침 0, EN 한글 0.

## 남긴 판단
- **Krita 사용자 축 72 보정**: Play 3.30★(6,937)은 안드로이드 태블릿판 표본이라 데스크톱 점수로 전용하지 않았다(override_reason 기록).
- **Midjourney 비공개 갤러리**: Basic·Standard는 공개 기본, Pro부터 비공개 — 판정에 조건으로 남김.
- **PDFgear 유료화 예고**: 현재 무료, 일부 고급 기능 유료화 가능성·시점 미정을 condition_notes에 기록.
- **Acrobat·Photoshop 과금 구조**: 같은 회사의 반복된 과금 개편(크레딧 축소·AI 애드온)을 risky_terms/감점으로 반영.
- **XCOM 2·Into the Breach 완결작 처리**: 공식 완결 선언 원문은 확인하지 못했고(등급 B), 마지막 패치와 확장 주기 종료를 근거로 `feature_complete` + stale exempt.

## 확인하지 못한 것
- Krita·Animate 계열 안드로이드판 실제 사용성, GIMP 3.2 비파괴 레이어 안정성
- Foxit·Acrobat·Photoshop의 최근 데스크톱 릴리스 날짜와 한국 원화 결제 금액
- Midjourney 프롬프트 보관·학습 사용 조항, Firefly 무료 일일 생성 실제 장수
- 각 AI 도구의 한국 결제·세금 처리
