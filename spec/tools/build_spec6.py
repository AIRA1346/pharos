#!/usr/bin/env python3
"""파로스 6차 대량 적재(v17, 1,400종 돌파) 스펙 빌더.

신규 비교군 7개(앱 5 · 게임 2) + 기존 비교군 대폭 보강.
- 앱: 웹툰·만화·전자책 / 습관·집중·타이머 / 2단계 인증·OTP / 마인드맵·화이트보드 / 커뮤니티·RSS·뉴스레터
- 게임: 모바일·크로스플랫폼 MMORPG / 스포츠 매니저·구단 운영
- 계획서의 '디지털 TCG · 카드 대전' 과 '리듬 · 음악 게임' 은 기존 비교군
  (`card-board-digital` · `rhythm-music`)에 이미 각 22종·17종이 있어, 같은 이름의 비교군을
  하나 더 만들면 중복 가드로 대부분 스킵되어 빈 비교군이 된다 → 기존 비교군 보강으로 넣는다.

실행: python3 projects/pharos/drafts/bulk6-2026-11-26/build_spec6.py
출력: 같은 폴더의 spec6.json
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

CATEGORIES = [
    dict(id="reading-comics", domain="app", label="웹툰 · 만화 · 전자책",
         label_en="Webtoons, Comics & eBooks",
         description="웹툰·만화·전자책을 읽는 앱 — 작품 보유량, 무료 대여·쿠폰 구조, 구매한 책의 락인이 판정을 가른다.",
         description_en="Apps for reading webtoons, comics and eBooks — catalogue depth, free-rental coupon structures and lock-in of purchased books decide the verdict."),
    dict(id="habit-focus", domain="app", label="습관 · 집중 · 타임트래킹",
         label_en="Habits, Focus & Time Tracking",
         description="습관을 쌓고 집중 시간을 재는 앱 — 무료 기능 한도, 구독 강제, 기록 내보내기가 판정을 가른다.",
         description_en="Apps that build habits and time focus sessions — free-tier limits, subscription pressure and record export decide the verdict."),
    dict(id="sports-management", domain="game", label="스포츠 매니저 · 구단 운영",
         label_en="Sports Management & Club Sims",
         description="구단을 맡아 선수·전술·재정을 운영하는 매니지먼트 게임 — 시즌 데이터 갱신, 1회 구매 범위, 모바일 과금이 판정을 가른다.",
         description_en="Management games where you run a club — season data updates, one-purchase scope and mobile monetization decide the verdict."),
]

ARENAS = [
    dict(id="reading-comics-webtoon", domain="app", category="reading-comics",
         label="웹툰 · 만화 · 전자책 서비스", label_en="Webtoon, Comic & eBook Services",
         description="웹툰·만화·전자책 서비스 — 작품 수, 무료 열람·대여 쿠폰, 구매 작품의 락인과 해외 접근성을 나란히 둔다.",
         description_en="Webtoon, comic and eBook services — catalogue size, free episodes and rental coupons, purchase lock-in and overseas access side by side.",
         data_file="app/reading-comics-webtoon.json"),
    dict(id="habit-focus-timer", domain="app", category="habit-focus",
         label="습관 · 집중 · 타이머", label_en="Habit, Focus & Timer Apps",
         description="습관 추적과 뽀모도로·집중 타이머 — 무료 기능 한도, 구독 가격, 기록 내보내기와 오픈소스를 비교한다.",
         description_en="Habit trackers and pomodoro or focus timers — free-tier limits, subscription price, record export and open source compared.",
         data_file="app/habit-focus-timer.json"),
    dict(id="security-2fa-auth", domain="app", category="security-utilities",
         label="2단계 인증 · OTP · 인증기", label_en="Two-Factor Auth & OTP",
         description="2단계 인증 코드를 만드는 인증기 — 백업·이전 가능성, 클라우드 동기화 여부, 광고·계정 강제를 비교한다.",
         description_en="Authenticators that generate two-factor codes — backup and migration, cloud sync, and ads or account requirements compared.",
         data_file="app/security-2fa-auth.json"),
    dict(id="mindmap-diagram-whiteboard", domain="app", category="office-docs",
         label="마인드맵 · 다이어그램 · 화이트보드", label_en="Mind Map, Diagram & Whiteboard",
         description="생각을 구조화하는 마인드맵·다이어그램·화이트보드 — 무료 보드 수, 내보내기 형식, 오프라인 동작을 비교한다.",
         description_en="Mind maps, diagrams and whiteboards that structure thinking — free board limits, export formats and offline behaviour compared.",
         data_file="app/mindmap-diagram-whiteboard.json"),
    dict(id="community-rss-newsletter", domain="app", category="social-community",
         label="커뮤니티 · RSS · 뉴스레터", label_en="Community, RSS & Newsletter",
         description="커뮤니티·RSS 리더·뉴스레터 구독 도구 — 알고리즘 의존도, 자체 호스팅 가능성, 유료 장벽을 비교한다.",
         description_en="Community platforms, RSS readers and newsletter tools — algorithmic feed dependence, self-hosting and paywalls compared.",
         data_file="app/community-rss-newsletter.json"),
    dict(id="mobile-cross-mmorpg", domain="game", category="mmorpg",
         label="모바일 · 크로스플랫폼 MMORPG", label_en="Mobile & Cross-Platform MMORPG",
         description="폰과 PC를 오가는 MMORPG — 자동 사냥·과금 구조, 크로스플레이, 시즌 운영을 비교한다.",
         description_en="MMORPGs played across phone and PC — auto-play and monetization structure, cross-play and seasonal operation compared.",
         data_file="game/mobile-cross-mmorpg.json"),
    dict(id="sports-manager-sim", domain="game", category="sports-management",
         label="스포츠 매니저 · 구단 운영", label_en="Sports Manager & Club Sim",
         description="축구·야구·모터스포츠 구단을 운영하는 매니저 게임 — 시즌 데이터 갱신, 1회 구매 범위, 모바일 과금을 비교한다.",
         description_en="Manager games that run football, baseball and motorsport clubs — season data updates, one-purchase scope and mobile monetization compared.",
         data_file="game/sports-manager-sim.json"),
]


def steam(id_, name, arena, term=None, aliases=()):
    row = {"id": id_, "name": name, "arena": arena, "steam": term or name}
    if aliases:
        row["aliases"] = list(aliases)
    return row


def ios(id_, name, arena, term=None, aliases=(), name_en=None):
    row = {"id": id_, "name": name, "arena": arena, "ios": term or name}
    if aliases:
        row["aliases"] = list(aliases)
    if name_en:
        row["name_en"] = name_en
    return row


def play(id_, name, arena, package, aliases=(), name_en=None):
    row = {"id": id_, "name": name, "arena": arena, "play": package}
    if aliases:
        row["aliases"] = list(aliases)
    if name_en:
        row["name_en"] = name_en
    return row


def gh(id_, name, arena, repo, aliases=(), platforms=("windows", "macos", "linux")):
    row = {"id": id_, "name": name, "arena": arena, "github": repo, "platforms": list(platforms)}
    if aliases:
        row["aliases"] = list(aliases)
    return row


ITEMS = []

# ══════════════════════════════════════════════════ 신규 앱 비교군 1: 웹툰 · 만화 · 전자책
ITEMS += [
    play("kakao-page", "KakaoPage", "reading-comics-webtoon", "com.kakao.page", aliases=["카카오페이지"]),
    play("ridi", "RIDI", "reading-comics-webtoon", "com.initialcoms.ridi", aliases=["리디", "리디북스"], name_en="RIDI"),
    play("lezhin-comics", "Lezhin Comics", "reading-comics-webtoon", "com.lezhin.comics", aliases=["레진코믹스"]),
    ios("millie", "밀리의 서재", "reading-comics-webtoon", term="밀리의 서재", aliases=["밀리"], name_en="Millie"),
    ios("kyobo-ebook", "교보eBook", "reading-comics-webtoon", term="교보eBook", aliases=["교보이북"], name_en="Kyobo eBook"),
    play("naver-series", "NAVER Series", "reading-comics-webtoon", "com.nhn.android.nbooks", aliases=["네이버시리즈", "SERIES"]),
    play("bomtoon", "봄툰", "reading-comics-webtoon", "com.bomcomics.bomtoon.playstore", aliases=["Bomtoon"], name_en="Bomtoon"),
    play("manta", "Manta", "reading-comics-webtoon", "net.manta.comic", aliases=["만타"]),
    play("manga-plus", "MANGA Plus by SHUEISHA", "reading-comics-webtoon", "jp.co.shueisha.mangaplus", aliases=["망가플러스"]),
    play("viz-manga", "VIZ Manga", "reading-comics-webtoon", "com.vizmanga.android", aliases=["비즈 망가"]),
    play("tapas", "Tapas", "reading-comics-webtoon", "com.tapastic", aliases=["타파스"]),
    play("marvel-unlimited", "Marvel Unlimited", "reading-comics-webtoon", "com.marvel.unlimited", aliases=["마블 언리미티드"]),
    play("book-walker", "BOOK WALKER", "reading-comics-webtoon", "jp.bookwalker.kreader.android.epub", aliases=["북워커"]),
]

# ══════════════════════════════════════════════════ 신규 앱 비교군 2: 습관 · 집중 · 타이머
ITEMS += [
    gh("loop-habit-tracker", "Loop Habit Tracker", "habit-focus-timer", "iSoron/uhabits",
       aliases=["루프 습관 트래커"], platforms=["android"]),
    ios("finch", "Finch", "habit-focus-timer", term="Finch: Self-Care Pet", aliases=["핀치"]),
    ios("flora", "Flora", "habit-focus-timer", term="Flora - Green Focus", aliases=["플로라"]),
    play("focus-to-do", "Focus To-Do", "habit-focus-timer", "com.superelement.pomodoro", aliases=["포커스 투두"]),
    play("toggl-track", "Toggl Track", "habit-focus-timer", "com.toggl.giskard", aliases=["토글 트랙"]),
    play("clockify", "Clockify", "habit-focus-timer", "me.clockify.android", aliases=["클로키파이"]),
    play("structured", "Structured", "habit-focus-timer", "io.unorderly.structured", aliases=["스트럭처드"]),
    ios("streaks", "Streaks", "habit-focus-timer", term="Streaks", aliases=["스트릭스"]),
    play("habitnow", "HabitNow", "habit-focus-timer", "com.habitnow", aliases=["해빗나우"]),
    ios("session-focus", "Session Pomodoro Focus Timer", "habit-focus-timer", term="Session - Pomodoro Focus Timer",
        aliases=["Session Pomodoro"]),
    gh("activitywatch", "ActivityWatch", "habit-focus-timer", "ActivityWatch/activitywatch", aliases=["액티비티워치"]),
    play("routinery", "Routinery", "habit-focus-timer", "com.alt.goodmorning", aliases=["루티너리", "Routine Planner"]),
]

# ══════════════════════════════════════════════════ 신규 앱 비교군 3: 2단계 인증 · OTP
ITEMS += [
    play("ente-auth", "Ente Auth", "security-2fa-auth", "io.ente.auth", aliases=["엔테 어스"]),
    play("twofas", "2FAS", "security-2fa-auth", "com.twofasapp", aliases=["투에프에이에스"], name_en="2FAS"),
    gh("aegis-authenticator", "Aegis Authenticator", "security-2fa-auth", "beemdevelopment/Aegis",
       aliases=["아이기스"], platforms=["android"]),
    play("google-authenticator", "Google Authenticator", "security-2fa-auth", "com.google.android.apps.authenticator2",
         aliases=["구글 OTP"]),
    play("microsoft-authenticator", "Microsoft Authenticator", "security-2fa-auth", "com.azure.authenticator",
         aliases=["마이크로소프트 인증"]),
    play("yubico-authenticator", "Yubico Authenticator", "security-2fa-auth", "com.yubico.yubioath",
         aliases=["유비코", "YubiKey"]),
    play("bitwarden-authenticator", "Bitwarden Authenticator", "security-2fa-auth", "com.bitwarden.authenticator",
         aliases=["비트워든 인증"]),
    play("authy", "Twilio Authy", "security-2fa-auth", "com.authy.authy", aliases=["어시"]),
    play("duo-mobile", "Duo Mobile", "security-2fa-auth", "com.duosecurity.duomobile", aliases=["듀오 모바일"]),
    gh("freeotp", "FreeOTP", "security-2fa-auth", "freeotp/freeotp-android",
       aliases=["프리 OTP"], platforms=["android"]),
]

# ══════════════════════════════════════════════════ 신규 앱 비교군 4: 마인드맵 · 다이어그램 · 화이트보드
ITEMS += [
    play("xmind", "Xmind", "mindmap-diagram-whiteboard", "net.xmind.doughnut", aliases=["엑스마인드"]),
    play("mindmeister", "MindMeister", "mindmap-diagram-whiteboard", "com.meisterlabs.mindmeister", aliases=["마인드마이스터"]),
    play("simplemind", "SimpleMind", "mindmap-diagram-whiteboard", "com.modelmakertools.simplemindfree",
         aliases=["심플마인드"]),
    play("lucidchart", "Lucidchart", "mindmap-diagram-whiteboard", "com.lucidchart.android.chart", aliases=["루시드차트"]),
    play("mindomo", "Mindomo", "mindmap-diagram-whiteboard", "air.com.EXswap.Mindomo", aliases=["마인도모"]),
    play("concepts", "Concepts", "mindmap-diagram-whiteboard", "com.tophatch.concepts", aliases=["컨셉츠"]),
    gh("freeplane", "Freeplane", "mindmap-diagram-whiteboard", "freeplane/freeplane", aliases=["프리플레인"]),
    gh("drawio", "draw.io", "mindmap-diagram-whiteboard", "jgraph/drawio", aliases=["다이어그램스", "diagrams.net"]),
    gh("tldraw", "tldraw", "mindmap-diagram-whiteboard", "tldraw/tldraw", aliases=["티엘드로우"],
       platforms=["web", "windows", "macos"]),
    ios("mindnode", "MindNode", "mindmap-diagram-whiteboard", term="MindNode", aliases=["마인드노드"]),
]

# ══════════════════════════════════════════════════ 신규 앱 비교군 5: 커뮤니티 · RSS · 뉴스레터
ITEMS += [
    play("substack", "Substack", "community-rss-newsletter", "com.substack.app", aliases=["서브스택"]),
    gh("netnewswire", "NetNewsWire", "community-rss-newsletter", "Ranchero-Software/NetNewsWire",
       aliases=["넷뉴스와이어"], platforms=["macos", "ios"]),
    gh("freshrss", "FreshRSS", "community-rss-newsletter", "FreshRSS/FreshRSS", aliases=["프레시 RSS"],
       platforms=["web", "linux"]),
    gh("miniflux", "Miniflux", "community-rss-newsletter", "miniflux/v2", aliases=["미니플럭스"],
       platforms=["web", "linux"]),
    gh("tiny-tiny-rss", "Tiny Tiny RSS", "community-rss-newsletter", "tt-rss/tt-rss", aliases=["tt-rss"],
       platforms=["web", "linux"]),
    play("newsblur", "NewsBlur", "community-rss-newsletter", "com.newsblur", aliases=["뉴스블러"]),
    ios("reeder", "Reeder", "community-rss-newsletter", term="Reeder.", aliases=["리더"]),
    gh("lemmy", "Lemmy", "community-rss-newsletter", "LemmyNet/lemmy", aliases=["레미"],
       platforms=["web"]),
    gh("mbin", "Mbin", "community-rss-newsletter", "MbinOrg/mbin", aliases=["엠빈"], platforms=["web"]),
    gh("ghost", "Ghost", "community-rss-newsletter", "TryGhost/Ghost", aliases=["고스트"], platforms=["web"]),
    play("primal", "Primal", "community-rss-newsletter", "net.primal.android", aliases=["프라이멀"]),
    gh("amethyst", "Amethyst", "community-rss-newsletter", "vitorpamplona/amethyst", aliases=["아메시스트"],
       platforms=["android"]),
]

# ══════════════════════════════════════════════════ 신규 게임 비교군 1: 모바일 · 크로스플랫폼 MMORPG
ITEMS += [
    play("black-desert-mobile", "Black Desert Mobile", "mobile-cross-mmorpg", "com.pearlabyss.blackdesertm.gl",
         aliases=["검은사막 모바일"]),
    steam("old-school-runescape", "Old School RuneScape", "mobile-cross-mmorpg", aliases=["올드스쿨 룬스케이프", "OSRS"]),
    steam("runescape", "RuneScape", "mobile-cross-mmorpg", aliases=["룬스케이프"]),
    play("diablo-immortal", "Diablo Immortal", "mobile-cross-mmorpg", "com.blizzard.diablo.immortal",
         aliases=["디아블로 이모탈"]),
    steam("torchlight-infinite", "Torchlight: Infinite", "mobile-cross-mmorpg", aliases=["토치라이트 인피니트"]),
    play("maplestory-m", "MapleStory M", "mobile-cross-mmorpg", "com.nexon.maplem.global", aliases=["메이플스토리 M"]),
    play("toram-online", "Toram Online", "mobile-cross-mmorpg", "com.asobimo.toramonline", aliases=["토람 온라인"]),
    play("eve-echoes", "EVE Echoes", "mobile-cross-mmorpg", "com.netease.eve.en", aliases=["이브 에코즈"]),
    play("lineage2m", "Lineage2M", "mobile-cross-mmorpg", "com.ncsoft.lineage2mnu", aliases=["리니지2M"]),
    play("ragnarok-x", "Ragnarok X: Next Generation", "mobile-cross-mmorpg", "global.thedream.and.rox",
         aliases=["라그나로크 X"]),
    steam("summoners-war-chronicles", "Summoners War: Chronicles", "mobile-cross-mmorpg",
          aliases=["서머너즈 워: 크로니클"]),
    steam("pax-dei", "Pax Dei", "mobile-cross-mmorpg", aliases=["팍스 데이"]),
]

# ══════════════════════════════════════════════════ 신규 게임 비교군 2: 스포츠 매니저 · 구단 운영
ITEMS += [
    steam("pro-basketball-manager-2025", "Pro Basketball Manager 2025", "sports-manager-sim", aliases=["PBM 2025"]),
    steam("motorsport-manager", "Motorsport Manager", "sports-manager-sim", aliases=["모터스포츠 매니저"]),
    steam("f1-manager-2024", "F1 Manager 2024", "sports-manager-sim", aliases=["F1 매니저 2024"]),
    play("ea-sports-fc-mobile", "EA SPORTS FC Mobile", "sports-manager-sim", "com.ea.gp.fifamobile",
         aliases=["FC 모바일", "피파 모바일"]),
    play("baseball-9", "BASEBALL 9", "sports-manager-sim", "us.kr.baseballnine", aliases=["베이스볼 9"]),
    play("nba-2k-mobile", "NBA 2K Mobile", "sports-manager-sim", "com.catdaddy.nba2km",
         aliases=["NBA 2K 모바일"]),
    play("retro-bowl", "Retro Bowl", "sports-manager-sim", "com.newstargames.retrobowl", aliases=["레트로 볼"]),
    steam("eastside-hockey-manager", "Eastside Hockey Manager", "sports-manager-sim", aliases=["EHM"]),
    steam("tennis-manager-2024", "Tennis Manager 2024", "sports-manager-sim", aliases=["테니스 매니저 2024"]),
    steam("cricket-captain-2024", "Cricket Captain 2024", "sports-manager-sim", aliases=["크리켓 캡틴 2024"]),
    steam("ootp-26", "Out of the Park Baseball 26", "sports-manager-sim", aliases=["OOTP 26"]),
    steam("franchise-hockey-manager-11", "Franchise Hockey Manager 11", "sports-manager-sim", aliases=["FHM 11"]),
]

# ══════════════════════════════════════════════════ 기존 앱 비교군 보강
ITEMS += [
    # 노트 · 지식관리
    gh("standard-notes", "Standard Notes", "pkm-notes", "standardnotes/app", aliases=["스탠다드 노트"]),
    gh("zettlr", "Zettlr", "pkm-notes", "Zettlr/Zettlr", aliases=["제틀러"]),
    play("upnote", "UpNote", "pkm-notes", "com.getupnote.android", aliases=["업노트"]),
    play("amplenote", "Amplenote", "pkm-notes", "com.amplenote", aliases=["앰플노트"]),
    # 할 일 · 일정 관리
    play("akiflow", "Akiflow", "task-managers", "com.akiflow.mobile", aliases=["아키플로우"]),
    play("motion", "Motion", "task-managers", "com.usemotion.motion", aliases=["모션"]),
    play("amazing-marvin", "Amazing Marvin", "task-managers", "com.amazingmarvin.marvin", aliases=["어메이징 마빈"]),

    # 캘린더 · 시간 관리
    play("timetree", "TimeTree", "calendar-apps", "works.jubilee.timetree", aliases=["타임트리"]),
    play("calendly", "Calendly", "calendar-apps", "com.calendly.app", aliases=["캘린들리"]),
    play("groupcal", "GroupCal", "calendar-apps", "app.groupcal.www", aliases=["그룹캘"]),
    # 이메일 클라이언트
    play("tuta-mail", "Tuta Mail", "email-clients", "de.tutao.tutanota", aliases=["투타", "Tutanota"]),
    play("canary-mail", "Canary Mail", "email-clients", "io.canarymail.android", aliases=["카나리 메일"]),
    play("edison-mail", "Edison Mail", "email-clients", "com.easilydo.mail", aliases=["에디슨 메일"]),
    # 클라우드 스토리지
    play("icedrive", "Icedrive", "cloud-storage", "com.icedrive.app", aliases=["아이스드라이브"]),
    play("sync-com", "Sync.com", "cloud-storage", "com.sync.mobileapp", aliases=["싱크닷컴"]),
    play("tresorit", "Tresorit", "cloud-storage", "com.tresorit.mobile", aliases=["트레조릿"]),
    play("koofr", "Koofr", "cloud-storage", "net.koofr.app", aliases=["쿠퍼"]),
    # 백업 · 파일 동기화
    play("resilio-sync", "Resilio Sync", "backup-sync", "com.resilio.sync", aliases=["레실리오 싱크"]),
    play("foldersync", "FolderSync", "backup-sync", "dk.tacit.android.foldersync.lite", aliases=["폴더싱크"]),
    # 개발자 도구 · 터미널 · API
    gh("github-cli", "GitHub CLI", "dev-terminals-git", "cli/cli", aliases=["gh CLI"]),
    gh("zellij", "Zellij", "dev-terminals-git", "zellij-org/zellij", aliases=["젤리지"]),
    gh("atuin", "Atuin", "dev-terminals-git", "atuinsh/atuin", aliases=["아투인"]),
    gh("delta", "delta", "dev-terminals-git", "dandavison/delta", aliases=["git-delta"]),
    # 시스템 · 파일 · 유틸
    gh("notepad-plus-plus", "Notepad++", "system-file-utils", "notepad-plus-plus/notepad-plus-plus",
       aliases=["노트패드++"], platforms=["windows"]),
    gh("winmerge", "WinMerge", "system-file-utils", "WinMerge/winmerge", aliases=["윈머지"], platforms=["windows"]),
    gh("double-commander", "Double Commander", "system-file-utils", "doublecmd/doublecmd", aliases=["더블 커맨더"]),
    # 건강 · 운동 · 러닝
    play("whoop", "WHOOP", "health-fitness", "com.whoop.android", aliases=["후프"]),
    play("oura", "Oura", "health-fitness", "com.ouraring.oura", aliases=["오우라"]),
    play("nike-training-club", "Nike Training Club", "health-fitness", "com.nike.ntc", aliases=["NTC"]),
    play("peloton", "Peloton", "health-fitness", "com.onepeloton.callisto", aliases=["펠로톤"]),
    play("betterme", "BetterMe", "health-fitness", "com.gen.workoutme", aliases=["베터미"]),
    # 가계부 · 금융 · 자산 관리
    play("money-lover", "Money Lover", "finance-budget-crypto", "com.bookmark.money", aliases=["머니러버"]),
    gh("gnucash", "GnuCash", "finance-budget-crypto", "Gnucash/gnucash", aliases=["그누캐시"]),
    gh("maybe-finance", "Maybe", "finance-budget-crypto", "maybe-finance/maybe", aliases=["메이비"],
       platforms=["web"]),
    play("pocketguard", "PocketGuard", "finance-budget-crypto", "com.pocketguard.android.app", aliases=["포켓가드"]),
    # 오피스 · 문서 · 화이트보드
    play("polaris-office", "Polaris Office", "office-suite", "com.infraware.office.link", aliases=["폴라리스 오피스"]),
    play("microsoft-onenote", "Microsoft OneNote", "office-suite", "com.microsoft.office.onenote", aliases=["원노트"]),
    play("myscript-nebo", "Nebo", "office-suite", "com.myscript.nebo", aliases=["네보"]),
    play("zoho-workplace", "Zoho Workplace", "office-suite", "com.zoho.workplace", aliases=["조호"]),
    # 언어 · 학습
    play("cake", "Cake", "language-learning", "me.mycake", aliases=["케이크"]),
    play("hellotalk", "HelloTalk", "language-learning", "com.hellotalk", aliases=["헬로톡"]),
    play("tandem", "Tandem", "language-learning", "net.tandem", aliases=["탄뎀"]),
    play("elsa-speak", "ELSA Speak", "language-learning", "us.nobarriers.elsa", aliases=["엘사 스픽"]),
    # 지도 · 내비게이션 · 여행
    play("sygic", "Sygic", "maps-navigation-travel", "com.sygic.aura", aliases=["사이직"]),
    play("tomtom-go", "TomTom GO", "maps-navigation-travel", "com.tomtom.gplay.navapp", aliases=["톰톰"]),
    play("here-wego", "HERE WeGo", "maps-navigation-travel", "com.here.app.maps", aliases=["히어 위고"]),
    play("moovit", "Moovit", "maps-navigation-travel", "com.tranzmate", aliases=["무빗"]),
    # 음악 스트리밍 · 오디오
    play("bandcamp", "Bandcamp", "music-audio-daw", "com.bandcamp.android", aliases=["밴드캠프"]),
    play("qobuz", "Qobuz", "music-audio-daw", "com.qobuz.music", aliases=["코부즈"]),
    # 미디어 플레이어
    play("mx-player", "MX Player", "media-players", "com.mxtech.videoplayer.ad", aliases=["MX플레이어"]),
    gh("just-player", "Just Player", "media-players", "moneytoo/player", aliases=["저스트 플레이어"],
       platforms=["android"]),
    # 메신저 · 팀 협업
    play("wechat", "WeChat", "messaging-team", "com.tencent.mm", aliases=["위챗"]),
    play("google-meet", "Google Meet", "messaging-team", "com.google.android.apps.tachyon", aliases=["구글 미트"]),
    play("zalo", "Zalo", "messaging-team", "com.zing.zalo", aliases=["잘로"]),
    # 소셜 · 커뮤니티
    play("tumblr", "Tumblr", "social-community", "com.tumblr", aliases=["텀블러"]),
    play("mewe", "MeWe", "social-community", "com.mewe", aliases=["미위"]),
    play("clubhouse", "Clubhouse", "social-community", "com.clubhouse.app", aliases=["클럽하우스"]),
    # OTT · 영상 스트리밍
    play("tubi", "Tubi", "streaming-video", "com.tubitv", aliases=["투비"]),
    play("pluto-tv", "Pluto TV", "streaming-video", "tv.pluto.android", aliases=["플루토 TV"]),
    play("peacock", "Peacock", "streaming-video", "com.peacocktv.peacockandroid", aliases=["피콕"]),
    play("kanopy", "Kanopy", "streaming-video", "com.kanopy", aliases=["카노피"]),
    # 쇼핑 · 생활 · 배달
    play("ebay", "eBay", "shopping-delivery-korea", "com.ebay.mobile", aliases=["이베이"]),
    play("etsy", "Etsy", "shopping-delivery-korea", "com.etsy.android", aliases=["엣시"]),
    play("naver-shopping", "NAVER Plus Store", "shopping-delivery-korea", "com.navercorp.navershopping",
         aliases=["네이버쇼핑", "네이버플러스 스토어"]),
    # 사진 편집 · 카메라 · 스캔
    play("open-camera", "Open Camera", "photo-camera-filter", "net.sourceforge.opencamera", aliases=["오픈 카메라"]),
    play("blackmagic-camera", "Blackmagic Camera", "photo-camera-filter",
         "com.blackmagicdesign.android.blackmagiccam", aliases=["블랙매직 카메라"]),
    play("filmic-pro", "Filmic Pro", "photo-camera-filter", "com.filmic.filmicpro", aliases=["필믹 프로"]),
    # 이미지 · 그래픽 편집
    play("adobe-express", "Adobe Express", "image-editors", "com.adobe.spark.post", aliases=["어도비 익스프레스"]),
    play("fotor", "Fotor", "image-editors", "com.everimaging.photoeffectstudio", aliases=["포토르"]),
    # VPN
    play("windscribe", "Windscribe", "vpn", "com.windscribe.vpn", aliases=["윈드스크라이브"]),
    play("private-internet-access", "Private Internet Access", "vpn", "com.privateinternetaccess.android",
         aliases=["PIA"]),
    play("cyberghost", "CyberGhost VPN", "vpn", "de.mobileconcepts.cyberghost", aliases=["사이버고스트"]),
    # 웹 브라우저
    gh("cromite", "Cromite", "web-browsers", "uazo/cromite", aliases=["크로마이트"], platforms=["android"]),
    gh("fennec", "Fennec F-Droid", "web-browsers", "mozilla-mobile/firefox-android", aliases=["페넥"],
       platforms=["android"]),
    gh("ladybird", "Ladybird", "web-browsers", "LadyBirdBrowser/ladybird", aliases=["레이디버드"]),
    # 번역 · 필기 · 학습 도구
    play("squid", "Squid", "translation-study-notes", "com.steadfastinnovation.android.projectpapyrus",
         aliases=["스퀴드"]),
    play("drawboard-pdf", "Drawboard PDF", "translation-study-notes", "com.drawboard.pdf", aliases=["드로우보드"]),
    # 읽기 · 북마크 보관
    play("cubox", "Cubox", "read-later", "pro.cubox.androidapp", aliases=["큐박스"]),
]

# ══════════════════════════════════════════════════ 기존 게임 비교군 보강
ITEMS += [
    # FPS · 슈팅
    steam("battlefield-1", "Battlefield 1", "fps-shooters", aliases=["배틀필드 1"]),
    steam("battlefield-v", "Battlefield V", "fps-shooters", aliases=["배틀필드 V"]),
    steam("cod-modern-warfare-3", "Call of Duty: Modern Warfare III", "fps-shooters", aliases=["콜 오브 듀티 MW3"]),
    steam("stalker-2", "S.T.A.L.K.E.R. 2: Heart of Chornobyl", "fps-shooters", aliases=["스토커 2"]),
    steam("arc-raiders", "ARC Raiders", "fps-shooters", aliases=["아크 레이더스"]),
    steam("delta-force", "Delta Force", "fps-shooters", aliases=["델타 포스"]),
    steam("ultrakill", "ULTRAKILL", "fps-shooters", aliases=["울트라킬"]),
    steam("dusk", "DUSK", "fps-shooters", aliases=["더스크"]),
    # 오픈월드 RPG · 어드벤처
    steam("ac-origins", "Assassin's Creed Origins", "open-world-rpg", aliases=["어쌔신 크리드 오리진"]),
    steam("ac-mirage", "Assassin's Creed Mirage", "open-world-rpg", aliases=["어쌔신 크리드 미라지"]),
    steam("far-cry-5", "Far Cry 5", "open-world-rpg", aliases=["파 크라이 5"]),
    steam("far-cry-6", "Far Cry 6", "open-world-rpg", aliases=["파 크라이 6"]),
    steam("watch-dogs-2", "Watch Dogs 2", "open-world-rpg", aliases=["왓치독스 2"]),
    steam("rise-of-the-tomb-raider", "Rise of the Tomb Raider", "open-world-rpg", aliases=["라이즈 오브 더 툼 레이더"]),
    steam("shadow-of-the-tomb-raider", "Shadow of the Tomb Raider", "open-world-rpg",
          aliases=["섀도 오브 더 툼 레이더"]),
    steam("mafia-definitive-edition", "Mafia: Definitive Edition", "open-world-rpg", aliases=["마피아"]),
    # JRPG · 애니메이션 RPG
    steam("smv-vengeance", "Shin Megami Tensei V: Vengeance", "anime-jrpg", aliases=["진 여신전생 5"]),
    steam("tales-of-berseria", "Tales of Berseria", "anime-jrpg", aliases=["테일즈 오브 베르세리아"]),
    steam("trails-through-daybreak", "The Legend of Heroes: Trails through Daybreak", "anime-jrpg",
          aliases=["궤적 시리즈", "영의 궤적"]),
    steam("ys-x-nordics", "Ys X: Nordics", "anime-jrpg", aliases=["이스 X"]),
    steam("atelier-ryza-3", "Atelier Ryza 3: Alchemist of the End & the Secret Key", "anime-jrpg",
          aliases=["라이자의 아틀리에 3"]),
    steam("ni-no-kuni-2", "Ni no Kuni II: Revenant Kingdom", "anime-jrpg", aliases=["니노쿠니 2"]),
    steam("suikoden-1-2-hd", "Suikoden I&II HD Remaster", "anime-jrpg", term="Suikoden I&II HD Remaster",
          aliases=["환상수호전 I&II"]),
    # 소울라이크 · 하드코어 액션
    steam("steelrising", "Steelrising", "soulslike", aliases=["스틸라이징"]),
    steam("wuchang-fallen-feathers", "Wuchang: Fallen Feathers", "soulslike", aliases=["오창: 깃털의 몰락"]),
    steam("first-berserker-khazan", "The First Berserker: Khazan", "soulslike", aliases=["퍼스트 버서커: 카잔"]),
    steam("ai-limit", "AI LIMIT", "soulslike", aliases=["AI 리밋"]),
    steam("enotria-last-song", "Enotria: The Last Song", "soulslike", aliases=["에노트리아"]),
    # 서바이벌 · 크래프팅
    steam("nightingale", "Nightingale", "survival-crafting", aliases=["나이팅게일"]),
    steam("dune-awakening", "Dune: Awakening", "survival-crafting", aliases=["듄: 어웨이크닝"]),
    steam("aloft", "Aloft", "survival-crafting", aliases=["얼로프트"]),
    steam("bellwright", "Bellwright", "survival-crafting", aliases=["벨라이트"]),
    steam("aska", "ASKA", "survival-crafting", aliases=["아스카"]),
    steam("return-to-moria", "The Lord of the Rings: Return to Moria", "survival-crafting",
          aliases=["반지의 제왕: 모리아로의 귀환"]),
    # 도시 건설 · 경영 시뮬
    steam("anno-1404", "Anno 1404 - History Edition", "city-builder-management", term="Anno 1404", aliases=["안노 1404"]),
    steam("anno-2070", "Anno 2070", "city-builder-management", aliases=["안노 2070"]),
    steam("pharaoh-a-new-era", "Pharaoh: A New Era", "city-builder-management", aliases=["파라오"]),
    steam("steamworld-build", "SteamWorld Build", "city-builder-management", aliases=["스팀월드 빌드"]),
    # 턴제 전략 · 전술
    steam("old-world", "Old World", "turn-based-strategy", aliases=["올드 월드"]),
    steam("humankind", "HUMANKIND", "turn-based-strategy", aliases=["휴먼카인드"]),
    steam("millennia", "Millennia", "turn-based-strategy", aliases=["밀레니아"]),
    steam("songs-of-conquest", "Songs of Conquest", "turn-based-strategy", aliases=["송스 오브 컨퀘스트"]),
    steam("heroes-3", "Heroes of Might and Magic III", "turn-based-strategy", term="Heroes of Might and Magic III",
          aliases=["히어로즈 3"]),
    # 덱빌딩
    steam("dicey-dungeons", "Dicey Dungeons", "roguelike-deckbuilder", aliases=["다이시 던전"]),
    steam("cobalt-core", "Cobalt Core", "roguelike-deckbuilder", aliases=["코발트 코어"]),
    steam("luck-be-a-landlord", "Luck be a Landlord", "roguelike-deckbuilder", aliases=["럭 비 어 랜드로드"]),
    steam("backpack-hero", "Backpack Hero", "roguelike-deckbuilder", aliases=["백팩 히어로"]),
    # 퍼즐 · 두뇌 · 논리
    steam("antichamber", "Antichamber", "puzzle-logic", aliases=["안티체임버"]),
    steam("toki-tori-2", "Toki Tori 2+", "puzzle-logic", aliases=["토키 토리 2"]),
    steam("snakebird", "Snakebird", "puzzle-logic", aliases=["스네이크버드"]),
    steam("entropy-centre", "The Entropy Centre", "puzzle-logic", aliases=["엔트로피 센터"]),
    # 생활 · 농장 · 타이쿤 시뮬
    steam("graveyard-keeper", "Graveyard Keeper", "sim-tycoon-casual", aliases=["그레이브야드 키퍼"]),
    steam("my-time-at-portia", "My Time at Portia", "sim-tycoon-casual", aliases=["포트리아"]),
    steam("ranch-simulator", "Ranch Simulator", "sim-tycoon-casual", aliases=["랜치 시뮬레이터"]),
    steam("megaquarium", "Megaquarium", "sim-tycoon-casual", aliases=["메가아쿠아리움"]),
    # 공포 · 서바이벌 호러
    steam("mortuary-assistant", "The Mortuary Assistant", "horror-thriller", aliases=["모추어리 어시스턴트"]),
    steam("fears-to-fathom", "Fears to Fathom", "horror-thriller", aliases=["피어스 투 파덤"]),
    steam("iron-lung", "Iron Lung", "horror-thriller", aliases=["아이언 런"]),
    steam("poppy-playtime", "Poppy Playtime", "horror-thriller", aliases=["포피 플레이타임"]),
    steam("bendy-and-the-ink-machine", "Bendy and the Ink Machine", "horror-thriller", aliases=["벤디"]),
    # 스토리 · 내러티브 · 추리
    steam("the-wolf-among-us", "The Wolf Among Us", "story-narrative-vn", aliases=["울프 어몽 어스"]),
    steam("tales-from-the-borderlands", "Tales from the Borderlands", "story-narrative-vn",
          aliases=["테일즈 프롬 더 보더랜즈"]),
    steam("life-is-strange", "Life is Strange", "story-narrative-vn", term="Life is Strange", aliases=["라이프 이즈 스트레인지"]),
    steam("heavy-rain", "Heavy Rain", "story-narrative-vn", aliases=["헤비 레인"]),
    steam("man-of-medan", "The Dark Pictures Anthology: Man of Medan", "story-narrative-vn", aliases=["맨 오브 메단"]),
    # 잠입 · 전술
    steam("styx-shards-of-darkness", "Styx: Shards of Darkness", "stealth-tactical", aliases=["스틱스"]),
    steam("thief", "Thief", "stealth-tactical", aliases=["씨프"]),
    steam("dishonored-death-of-the-outsider", "Dishonored: Death of the Outsider", "stealth-tactical",
          aliases=["디스아너드: 방관자의 죽음"]),
    # 우주 · 비행 시뮬
    steam("avorion", "Avorion", "space-flight-sim", aliases=["아보리온"]),
    steam("terra-invicta", "Terra Invicta", "space-flight-sim", aliases=["테라 인빅타"]),
    steam("nebulous-fleet-command", "Nebulous: Fleet Command", "space-flight-sim", aliases=["네뷸러스"]),
    # 협동 · 파티
    steam("a-way-out", "A Way Out", "co-op-party", aliases=["어 웨이 아웃"]),
    steam("moving-out-2", "Moving Out 2", "co-op-party", aliases=["무빙 아웃 2"]),
    steam("pico-park", "PICO PARK", "co-op-party", aliases=["피코 파크"]),
    steam("we-were-here", "We Were Here", "co-op-party", aliases=["위 워 히어"]),
    # 레이싱 · 스포츠
    steam("wreckfest", "Wreckfest", "racing-sim", aliases=["레크페스트"]),
    steam("art-of-rally", "art of rally", "racing-sim", aliases=["아트 오브 랠리"]),
    steam("trackmania", "Trackmania", "racing-sim", aliases=["트랙매니아"]),
    steam("hot-wheels-unleashed-2", "HOT WHEELS UNLEASHED 2 - Turbocharged", "racing-sim", term="HOT WHEELS UNLEASHED 2",
          aliases=["핫휠 언리쉬드 2"]),
    # 격투 · 콤보 액션
    steam("dragon-ball-fighterz", "DRAGON BALL FighterZ", "fighting-action", aliases=["드래곤볼 파이터즈"]),
    steam("injustice-2", "Injustice 2", "fighting-action", aliases=["인저스티스 2"]),
    steam("soulcalibur-vi", "SOULCALIBUR VI", "fighting-action", aliases=["소울칼리버 6"]),
    steam("guilty-gear-xrd-rev2", "GUILTY GEAR Xrd REV 2", "fighting-action", aliases=["길티기어 Xrd"]),
    # 스포츠 · MOBA · 경쟁
    steam("madden-nfl-26", "EA SPORTS Madden NFL 26", "sports-competitive", aliases=["매든 NFL 26"]),
    steam("skate", "skate.", "sports-competitive", aliases=["스케이트"]),
    steam("session-skate-sim", "Session: Skate Sim", "sports-competitive", aliases=["세션 스케이트 심"]),
    # 리듬 · 음악 게임
    steam("just-shapes-and-beats", "Just Shapes & Beats", "rhythm-music", aliases=["저스트 셰이프 앤 비츠"]),
    steam("synth-riders", "Synth Riders", "rhythm-music", aliases=["신스 라이더스"]),
    steam("pistol-whip", "Pistol Whip", "rhythm-music", aliases=["피스톨 휩"]),
    steam("crypt-of-the-necrodancer", "Crypt of the NecroDancer", "rhythm-music", aliases=["네크로댄서"]),
    steam("metal-hellsinger", "Metal: Hellsinger", "rhythm-music", aliases=["메탈 헬싱어"]),
    steam("rhythm-sprout", "Rhythm Sprout", "rhythm-music", aliases=["리듬 스프라우트"]),
    # 디지털 보드 · 카드 · 체스 (TCG 보강)
    steam("gwent", "GWENT: The Witcher Card Game", "card-board-digital", aliases=["궨트"]),
    play("pokemon-tcg-live", "Pokémon TCG Live", "card-board-digital", "com.pokemon.pokemontcgl",
         aliases=["포켓몬 TCG 라이브"]),
    play("pokemon-tcg-pocket", "Pokémon TCG Pocket", "card-board-digital", "jp.pokemon.pokemontcgp",
         aliases=["포켓몬 TCG 포켓"]),
    steam("vanguard-dear-days", "Cardfight!! Vanguard Dear Days", "card-board-digital", aliases=["뱅가드 디어 데이즈"]),
    steam("tabletopia", "Tabletopia", "card-board-digital", aliases=["테이블토피아"]),
    steam("star-realms", "Star Realms", "card-board-digital", aliases=["스타 렐름"]),
    # 핵 앤 슬래시 · 액션 RPG
    steam("darksiders-genesis", "Darksiders Genesis", "arpg-hack-slash", aliases=["다크사이더스 제네시스"]),
    steam("warhammer-chaosbane", "Warhammer: Chaosbane", "arpg-hack-slash", aliases=["카오스베인"]),
    steam("the-ascent", "The Ascent", "arpg-hack-slash", aliases=["더 어센트"]),
    # 메트로배니아 · 플랫포머
    steam("afterimage", "Afterimage", "metroidvania-platformer", aliases=["애프터이미지"]),
    steam("islets", "Islets", "metroidvania-platformer", aliases=["아일렛"]),
    steam("la-mulana", "La-Mulana", "metroidvania-platformer", aliases=["라 무라나"]),
    steam("rabi-ribi", "Rabi-Ribi", "metroidvania-platformer", aliases=["라비리비"]),
    # 경영 · 자동화 · 공장 건설
    steam("plan-b-terraform", "Plan B: Terraform", "management-automation", aliases=["플랜 B"]),
    steam("astro-colony", "Astro Colony", "management-automation", aliases=["아스트로 콜로니"]),
    steam("nova-lands", "Nova Lands", "management-automation", aliases=["노바 랜즈"]),
    steam("the-crust", "The Crust", "management-automation", aliases=["더 크러스트"]),
    # 샌드박스 · 크리에이티브
    steam("instruments-of-destruction", "Instruments of Destruction", "sandbox-creative", aliases=["인스트루먼츠 오브 디스트럭션"]),
    steam("main-assembly", "Main Assembly", "sandbox-creative", aliases=["메인 어셈블리"]),
    steam("terratech", "TerraTech", "sandbox-creative", aliases=["테라테크"]),
    # 모바일 수집형 RPG
    steam("duet-night-abyss", "Duet Night Abyss", "mobile-gacha-rpg", aliases=["듀엣 나이트 어비스"]),
    steam("sword-of-convallaria", "Sword of Convallaria", "mobile-gacha-rpg", aliases=["콘발라리아"]),
    steam("p5-phantom-x", "Persona5: The Phantom X", "mobile-gacha-rpg", aliases=["페르소나5: 더 팬텀 X"]),
    # 모바일 캐주얼 · 퍼즐
    play("flow-free", "Flow Free", "mobile-casual-puzzle", "com.bigduckgames.flow", aliases=["플로우 프리"]),
    play("brain-test", "Brain Test", "mobile-casual-puzzle", "com.unicostudio.braintest", aliases=["브레인 테스트"]),
    play("water-sort-puzzle", "Water Sort Puzzle", "mobile-casual-puzzle",
         "water.sort.puzzle.game.color.sorting.free", aliases=["워터 소트 퍼즐"]),
    # 아케이드 · 리듬 · 클래식
    steam("pac-man-museum-plus", "PAC-MAN MUSEUM+", "arcade-retro-classic", aliases=["팩맨 뮤지엄"]),
    steam("atari-50", "Atari 50: The Anniversary Celebration", "arcade-retro-classic", aliases=["아타리 50"]),
    steam("sonic-mania", "Sonic Mania", "arcade-retro-classic", aliases=["소닉 매니아"]),
]

SPEC = {
    "batch": "2026-11-26-bulk6-1400",
    "note": (
        "파로스 6차 대량 적재 — 앱 5개 신규 비교군(웹툰·만화·전자책, 습관·집중·타이머, 2단계 인증·OTP, "
        "마인드맵·다이어그램·화이트보드, 커뮤니티·RSS·뉴스레터) + 게임 2개(모바일·크로스플랫폼 MMORPG, "
        "스포츠 매니저·구단 운영) = 신규 7개 비교군과 기존 30여 비교군 보강. 계획서의 디지털 TCG·리듬 게임은 "
        "기존 비교군(card-board-digital·rhythm-music) 보강으로 넣었다. 각 항목은 Steam 검색어 / Google Play "
        "패키지 / App Store 검색어 / GitHub 저장소 중 1개로 수집하며, bulk_ingest.py 중복 가드가 기존 1,189종과 "
        "겹치는 항목(id·정규화 이름·스토어 ID)을 자동 스킵한다."
    ),
    "catalog_note_marker": "2026-11-26 6차 대량 팩트 적재(v17)",
    "catalog_note": (
        "2026-11-26 6차 대량 팩트 적재(v17)로 앱에 웹툰·만화·전자책, 습관·집중·타이머, 2단계 인증·OTP, "
        "마인드맵·다이어그램·화이트보드, 커뮤니티·RSS·뉴스레터 5개 비교군이, 게임에 모바일·크로스플랫폼 MMORPG, "
        "스포츠 매니저·구단 운영 2개 비교군이 들어왔다(신규 7비교군 · 기존 30여 비교군 보강 · 총 {total}종)."
    ),
    "categories": CATEGORIES,
    "arenas": ARENAS,
    "items": ITEMS,
}


def main() -> int:
    ids = [row["id"] for row in ITEMS]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise SystemExit(f"스펙 내부 id 중복: {dupes}")
    out = HERE / "spec6.json"
    out.write_text(json.dumps(SPEC, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    from collections import Counter
    per = Counter(row["arena"] for row in ITEMS)
    print(f"→ {out} — 항목 {len(ITEMS)}종 · 신규 대분류 {len(CATEGORIES)} · 신규 비교군 {len(ARENAS)}")
    for arena, n in per.most_common():
        print(f"   {arena:<32} {n}")
    games = sum(n for a, n in per.items() if a in {x['id'] for x in ARENAS if x['domain'] == 'game'} or a in GAME_ARENAS)
    print(f"   게임 {games} · 앱 {len(ITEMS) - games}")
    return 0


GAME_ARENAS = {
    "fps-shooters", "open-world-rpg", "anime-jrpg", "soulslike", "survival-crafting",
    "city-builder-management", "turn-based-strategy", "roguelike-deckbuilder", "puzzle-logic",
    "sim-tycoon-casual", "horror-thriller", "story-narrative-vn", "stealth-tactical",
    "space-flight-sim", "co-op-party", "racing-sim", "fighting-action", "sports-competitive",
    "rhythm-music", "card-board-digital", "arpg-hack-slash", "metroidvania-platformer",
    "management-automation", "sandbox-creative", "mobile-gacha-rpg", "mobile-casual-puzzle",
    "arcade-retro-classic",
}

if __name__ == "__main__":
    raise SystemExit(main())
