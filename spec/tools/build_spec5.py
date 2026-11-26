#!/usr/bin/env python3
"""파로스 5차 대량 적재(v16, 1,000종 돌파) 스펙 빌더.

신규 비교군 7개(게임 3 · 앱 4) + 기존 비교군 보강.
실행: python3 projects/pharos/drafts/bulk5-2026-11-26/build_spec5.py
출력: 같은 폴더의 spec5.json
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

CATEGORIES = [
    dict(id="visual-novel", domain="game", label="비주얼 노벨 · 어드벤처", label_en="Visual Novel & Adventure",
         description="텍스트와 선택으로 이야기를 진행하는 비주얼 노벨 — 본편 완결성, 루트 분량, 번역 품질이 판정을 가른다.",
         description_en="Visual novels told through text and choices — main-story completeness, route volume and translation quality decide the verdict."),
    dict(id="management-automation", domain="game", label="경영 · 자동화", label_en="Management & Automation",
         description="공장·물류·도시를 자동화하는 경영 시뮬 — 1회 구매 후 DLC, 얼리액세스 완성도, 모드 생태계가 판정을 가른다.",
         description_en="Management sims that automate factories, logistics and towns — post-purchase DLC, early-access completeness and the mod ecosystem decide the verdict."),
    dict(id="arcade-retro", domain="game", label="아케이드 · 클래식", label_en="Arcade & Classics",
         description="한 판이 짧고 점수·기록으로 승부하는 아케이드·리듬·레트로 게임 — 광고·과금 없는 완결성과 조작감이 판정을 가른다.",
         description_en="Short-run arcade, rhythm and retro games decided by score and records — ad-free, microtransaction-free completeness and feel decide the verdict."),
    dict(id="streaming-capture", domain="app", label="방송 · 화면 녹화", label_en="Streaming & Screen Capture",
         description="화면을 녹화하고 방송으로 내보내는 도구 — 무료 워터마크·녹화 시간 제한, 계정·클라우드 의존도가 판정을 가른다.",
         description_en="Tools that record the screen and broadcast it — free-tier watermarks, recording limits, and account or cloud dependence decide the verdict."),
    dict(id="audio-production", domain="app", label="음악 제작 · 팟캐스트", label_en="Music Production & Podcast",
         description="음악을 만들고 팟캐스트를 듣는 도구 — 무료 트랙·플러그인 한도, 구독 강제, 오프라인 재생이 판정을 가른다.",
         description_en="Tools for making music and listening to podcasts — free track and plug-in limits, subscription lock-in and offline playback decide the verdict."),
    dict(id="travel-mobility", domain="app", label="교통 · 숙박 · 여행", label_en="Travel & Mobility",
         description="숙박·항공·택시·기차를 예약하는 앱 — 예약 수수료와 취소 규정, 위치·결제 정보 수집 범위가 판정을 가른다.",
         description_en="Apps that book stays, flights, rides and trains — booking fees and cancellation rules, and how much location and payment data they collect decide the verdict."),
    dict(id="ai-writing-research", domain="app", label="AI 글쓰기 · 리서치", label_en="AI Writing & Research",
         description="AI로 쓰고 조사하고 요약·전사하는 도구 — 무료 크레딧 한도, 인용·출처 표시, 대화가 학습에 쓰이는지가 판정을 가른다.",
         description_en="Tools that write, research, summarize and transcribe with AI — free credit limits, citations, and whether conversations train models decide the verdict."),
]

ARENAS = [
    dict(id="visual-novel-narrative", domain="game", category="visual-novel",
         label="비주얼 노벨 · 인터랙티브 스토리", label_en="Visual Novel & Interactive Story",
         description="선택지와 텍스트로 이야기를 엮는 비주얼 노벨 — 1회 구매 완결성, 루트 분량, 리마스터·번역 상태를 나란히 둔다.",
         description_en="Visual novels woven from choices and text — one-purchase completeness, route volume, and remaster or translation status side by side.",
         data_file="game/visual-novel-narrative.json"),
    dict(id="management-automation", domain="game", category="management-automation",
         label="경영 · 자동화 · 공장 건설", label_en="Management, Automation & Factory",
         description="공장·물류·자원을 자동화하는 경영 게임 — 1회 구매 후 DLC, 얼리액세스 완성도, 모드 생태계를 비교한다.",
         description_en="Management games that automate factories, logistics and resources — post-purchase DLC, early-access completeness and mod ecosystems compared.",
         data_file="game/management-automation.json"),
    dict(id="arcade-retro-classic", domain="game", category="arcade-retro",
         label="아케이드 · 리듬 · 클래식", label_en="Arcade, Rhythm & Classics",
         description="한 판이 짧은 아케이드·리듬·레트로 게임 — 광고·과금 없는 완결성, 조작감, 리플레이 가치를 비교한다.",
         description_en="Short-run arcade, rhythm and retro games — ad-free completeness, feel and replay value compared.",
         data_file="game/arcade-retro-classic.json"),
    dict(id="streaming-screen-capture", domain="app", category="streaming-capture",
         label="화면 녹화 · 방송 · 스트리밍", label_en="Screen Recorder, Streaming & Broadcast",
         description="화면 녹화·방송 도구 — 무료 워터마크·시간 제한, 계정·클라우드 의존도, 방송 플랫폼 연동을 비교한다.",
         description_en="Screen recording and broadcast tools — free watermarks and time limits, account and cloud dependence, and platform integration compared.",
         data_file="app/streaming-screen-capture.json"),
    dict(id="audio-daw-podcast", domain="app", category="audio-production",
         label="음악 제작 · DAW · 팟캐스트", label_en="Music Production, DAW & Podcast",
         description="음악 제작 앱과 팟캐스트 플레이어 — 무료 트랙·플러그인 한도, 구독 강제, 오프라인 재생을 비교한다.",
         description_en="Music production apps and podcast players — free track and plug-in limits, subscription lock-in and offline playback compared.",
         data_file="app/audio-daw-podcast.json"),
    dict(id="travel-mobility-booking", domain="app", category="travel-mobility",
         label="교통 · 숙박 · 항공 · 모빌리티", label_en="Transport, Stays, Flights & Mobility",
         description="숙박·항공·택시·기차 예약 앱 — 수수료와 취소 규정, 위치·결제 정보 수집 범위를 비교한다.",
         description_en="Stay, flight, ride and rail booking apps — fees and cancellation rules, and location and payment-data collection compared.",
         data_file="app/travel-mobility-booking.json"),
    dict(id="ai-writing-research", domain="app", category="ai-writing-research",
         label="AI 글쓰기 · 리서치 · 전사", label_en="AI Writing, Research & Transcription",
         description="AI로 쓰고 조사하고 요약·전사하는 앱 — 무료 크레딧 한도, 출처 표시, 학습 이용 여부를 비교한다.",
         description_en="Apps that write, research, summarize and transcribe with AI — free credit limits, citations and training use compared.",
         data_file="app/ai-writing-research.json"),
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

# ── 신규 게임 비교군 1: 비주얼 노벨 · 인터랙티브 스토리
ITEMS += [
    steam("ddlc-plus", "Doki Doki Literature Club Plus!", "visual-novel-narrative", aliases=["도키도키 문학부 플러스"]),
    steam("coffee-talk", "Coffee Talk", "visual-novel-narrative", aliases=["커피 토크"]),
    steam("coffee-talk-episode-2", "Coffee Talk Episode 2: Hibiscus & Butterfly", "visual-novel-narrative", aliases=["커피 토크 2"]),
    steam("the-house-in-fata-morgana", "The House in Fata Morgana", "visual-novel-narrative", aliases=["파타 모르가나의 집"]),
    steam("umineko-question-arcs", "Umineko When They Cry - Question Arcs", "visual-novel-narrative", term="Umineko", aliases=["우미네코"]),
    steam("higurashi-hou-ch1", "Higurashi When They Cry Hou - Ch.1 Onikakushi", "visual-novel-narrative", term="Higurashi", aliases=["쓰르라미 울 적에"]),
    steam("clannad", "CLANNAD", "visual-novel-narrative", aliases=["클라나드"]),
    steam("steins-gate-0", "STEINS;GATE 0", "visual-novel-narrative", aliases=["슈타인즈 게이트 0"]),
    steam("ghost-trick", "Ghost Trick: Phantom Detective", "visual-novel-narrative", aliases=["고스트 트릭"]),
    steam("the-great-ace-attorney-chronicles", "The Great Ace Attorney Chronicles", "visual-novel-narrative", aliases=["대역전재판"]),
    steam("428-shibuya-scramble", "428: Shibuya Scramble", "visual-novel-narrative", aliases=["428 시부야"]),
    steam("suzerain", "Suzerain", "visual-novel-narrative", aliases=["수제레인"]),
    steam("long-live-the-queen", "Long Live The Queen", "visual-novel-narrative", aliases=["여왕 만세"]),
]

# ── 신규 게임 비교군 2: 경영 · 자동화 · 공장 건설
ITEMS += [
    steam("shapez-2", "shapez 2", "management-automation", aliases=["셰이프즈 2"]),
    steam("workers-resources-soviet-republic", "Workers & Resources: Soviet Republic", "management-automation", aliases=["워커스 앤 리소시스"]),
    steam("captain-of-industry", "Captain of Industry", "management-automation", aliases=["캡틴 오브 인더스트리"]),
    steam("mindustry", "Mindustry", "management-automation", aliases=["마인더스트리"]),
    steam("transport-fever-2", "Transport Fever 2", "management-automation", aliases=["트랜스포트 피버 2"]),
    steam("rise-of-industry", "Rise of Industry", "management-automation", aliases=["라이즈 오브 인더스트리"]),
    steam("production-line", "Production Line", "management-automation", aliases=["프로덕션 라인"]),
    steam("autonauts", "Autonauts", "management-automation", aliases=["오토노츠"]),
    steam("foundry", "FOUNDRY", "management-automation", aliases=["파운드리"]),
    steam("techtonica", "Techtonica", "management-automation", aliases=["테크토니카"]),
    steam("sweet-transit", "Sweet Transit", "management-automation", aliases=["스위트 트랜짓"]),
    steam("factory-town", "Factory Town", "management-automation", aliases=["팩토리 타운"]),
    steam("dwarf-fortress", "Dwarf Fortress", "management-automation", aliases=["드워프 포트리스"]),
]

# ── 신규 게임 비교군 3: 아케이드 · 리듬 · 클래식
ITEMS += [
    steam("tetris-effect-connected", "Tetris Effect: Connected", "arcade-retro-classic", aliases=["테트리스 이펙트"]),
    steam("neon-white", "Neon White", "arcade-retro-classic", aliases=["네온 화이트"]),
    steam("downwell", "Downwell", "arcade-retro-classic", aliases=["다운웰"]),
    steam("hotline-miami-2", "Hotline Miami 2: Wrong Number", "arcade-retro-classic", aliases=["핫라인 마이애미 2"]),
    steam("ikaruga", "Ikaruga", "arcade-retro-classic", aliases=["이카루가"]),
    steam("broforce", "Broforce", "arcade-retro-classic", aliases=["브로포스"]),
    steam("pacman-ce-dx", "PAC-MAN Championship Edition DX+", "arcade-retro-classic", aliases=["팩맨 CE"]),
    steam("pizza-tower", "Pizza Tower", "arcade-retro-classic", aliases=["피자 타워"]),
    steam("super-hexagon", "Super Hexagon", "arcade-retro-classic", aliases=["슈퍼 헥사곤"]),
    steam("thumper", "Thumper", "arcade-retro-classic", aliases=["썸퍼"]),
    steam("katana-zero", "Katana ZERO", "arcade-retro-classic", aliases=["카타나 제로"]),
    steam("furi", "Furi", "arcade-retro-classic", aliases=["후리"]),
    steam("sayonara-wild-hearts", "Sayonara Wild Hearts", "arcade-retro-classic", aliases=["사요나라 와일드 하츠"]),
    steam("vvvvvv", "VVVVVV", "arcade-retro-classic", aliases=["브이브이브이브이브이브이"]),
    steam("hotline-miami", "Hotline Miami", "arcade-retro-classic", aliases=["핫라인 마이애미"]),
]

# ── 기존 게임 비교군 보강
ITEMS += [
    # JRPG · 애니메이션 RPG
    steam("final-fantasy-vii-rebirth", "FINAL FANTASY VII REBIRTH", "anime-jrpg", aliases=["파이널 판타지 7 리버스"]),
    steam("final-fantasy-x-x2", "FINAL FANTASY X/X-2 HD Remaster", "anime-jrpg", aliases=["파이널 판타지 10"]),
    steam("final-fantasy-ix", "FINAL FANTASY IX", "anime-jrpg", aliases=["파이널 판타지 9"]),
    steam("chained-echoes", "Chained Echoes", "anime-jrpg", aliases=["체인드 에코즈"]),
    steam("sea-of-stars", "Sea of Stars", "anime-jrpg", aliases=["씨 오브 스타즈"]),
    steam("nier-replicant", "NieR Replicant ver.1.22474487139...", "anime-jrpg", aliases=["니어 레플리칸트"]),
    steam("ys-viii", "Ys VIII: Lacrimosa of DANA", "anime-jrpg", aliases=["이스 8"]),
    steam("trails-of-cold-steel", "The Legend of Heroes: Trails of Cold Steel", "anime-jrpg", aliases=["영웅전설 섬의 궤적"]),
    steam("dq3-hd2d", "DRAGON QUEST III HD-2D Remake", "anime-jrpg", aliases=["드래곤 퀘스트 3"]),
    # 턴제 전략 · 전술
    steam("pillars-of-eternity", "Pillars of Eternity", "turn-based-strategy", aliases=["필라스 오브 이터니티"]),
    steam("pillars-of-eternity-2", "Pillars of Eternity II: Deadfire", "turn-based-strategy", aliases=["필라스 오브 이터니티 2"]),
    steam("tyranny", "Tyranny", "turn-based-strategy", aliases=["티라니"]),
    steam("pathfinder-wrath", "Pathfinder: Wrath of the Righteous", "turn-based-strategy", aliases=["패스파인더 의인의 분노"]),
    steam("pathfinder-kingmaker", "Pathfinder: Kingmaker", "turn-based-strategy", aliases=["패스파인더 킹메이커"]),
    steam("solasta", "Solasta: Crown of the Magister", "turn-based-strategy", aliases=["솔라스타"]),
    steam("baldurs-gate-2-ee", "Baldur's Gate II: Enhanced Edition", "turn-based-strategy", aliases=["발더스 게이트 2"]),
    steam("baldurs-gate-ee", "Baldur's Gate: Enhanced Edition", "turn-based-strategy", aliases=["발더스 게이트"]),
    steam("planescape-torment-ee", "Planescape: Torment: Enhanced Edition", "turn-based-strategy", aliases=["플레인스케이프 토먼트"]),
    steam("xcom-enemy-unknown", "XCOM: Enemy Unknown", "turn-based-strategy", aliases=["엑스컴 에너미 언노운"]),
    steam("aoe2-de", "Age of Empires II: Definitive Edition", "turn-based-strategy", aliases=["에이지 오브 엠파이어 2"]),
    steam("age-of-wonders-4", "Age of Wonders 4", "turn-based-strategy", aliases=["에이지 오브 원더스 4"]),
    steam("total-war-three-kingdoms", "Total War: THREE KINGDOMS", "turn-based-strategy", aliases=["토탈 워 삼국"]),
    steam("endless-legend", "Endless Legend", "turn-based-strategy", aliases=["엔드리스 레전드"]),
    # 오픈월드 RPG · 어드벤처
    steam("fallout-new-vegas", "Fallout: New Vegas", "open-world-rpg", aliases=["폴아웃 뉴베가스"]),
    steam("fallout-3", "Fallout 3", "open-world-rpg", aliases=["폴아웃 3"]),
    steam("mass-effect-legendary", "Mass Effect Legendary Edition", "open-world-rpg", aliases=["매스 이펙트"]),
    steam("dragon-age-inquisition", "Dragon Age: Inquisition", "open-world-rpg", aliases=["드래곤 에이지 인퀴지션"]),
    steam("oblivion-remastered", "The Elder Scrolls IV: Oblivion Remastered", "open-world-rpg", aliases=["엘더 스크롤 4 오블리비언"]),
    steam("the-witcher-2", "The Witcher 2: Assassins of Kings Enhanced Edition", "open-world-rpg", aliases=["위처 2"]),
    steam("sleeping-dogs", "Sleeping Dogs: Definitive Edition", "open-world-rpg", aliases=["슬리핑 독스"]),
    steam("mad-max", "Mad Max", "open-world-rpg", aliases=["매드 맥스"]),
    # FPS · 슈팅
    steam("doom-2016", "DOOM", "fps-shooters", aliases=["둠 2016"]),
    steam("quake", "Quake", "fps-shooters", aliases=["퀘이크"]),
    steam("bioshock-remastered", "BioShock Remastered", "fps-shooters", aliases=["바이오쇼크"]),
    steam("bioshock-2-remastered", "BioShock 2 Remastered", "fps-shooters", aliases=["바이오쇼크 2"]),
    steam("prey", "Prey", "fps-shooters", aliases=["프레이"]),
    steam("metro-2033-redux", "Metro 2033 Redux", "fps-shooters", aliases=["메트로 2033"]),
    steam("borderlands-3", "Borderlands 3", "fps-shooters", aliases=["보더랜드 3"]),
    steam("crysis-remastered", "Crysis Remastered", "fps-shooters", aliases=["크라이시스"]),
    # 소울라이크 · 하드코어 액션
    steam("dark-souls-remastered", "DARK SOULS: REMASTERED", "soulslike", aliases=["다크 소울 리마스터"]),
    steam("dark-souls-2-sotfs", "DARK SOULS II: Scholar of the First Sin", "soulslike", aliases=["다크 소울 2"]),
    steam("hellpoint", "Hellpoint", "soulslike", aliases=["헬포인트"]),
    # 메트로배니아 · 플랫포머
    steam("hollow-knight-silksong", "Hollow Knight: Silksong", "metroidvania-platformer", aliases=["실크송"]),
    steam("axiom-verge", "Axiom Verge", "metroidvania-platformer", aliases=["액시엄 버지"]),
    steam("guacamelee-2", "Guacamelee! 2", "metroidvania-platformer", aliases=["과카몰리 2"]),
    steam("salt-and-sanctuary", "Salt and Sanctuary", "metroidvania-platformer", aliases=["솔트 앤 생츄어리"]),
    steam("gris", "GRIS", "metroidvania-platformer", aliases=["그리스"]),
    steam("inside", "INSIDE", "metroidvania-platformer", aliases=["인사이드"]),
    steam("limbo", "LIMBO", "metroidvania-platformer", aliases=["림보"]),
    # 액션 로그라이크
    steam("rogue-legacy-2", "Rogue Legacy 2", "action-roguelike", aliases=["로그 레거시 2"]),
    steam("children-of-morta", "Children of Morta", "action-roguelike", aliases=["칠드런 오브 모르타"]),
    steam("wizard-of-legend", "Wizard of Legend", "action-roguelike", aliases=["위자드 오브 레전드"]),
    steam("noita", "Noita", "action-roguelike", aliases=["노이타"]),
    steam("spelunky-2", "Spelunky 2", "action-roguelike", aliases=["스펠런키 2"]),
    steam("tiny-rogues", "Tiny Rogues", "action-roguelike", aliases=["타이니 로그"]),
    # 덱빌딩 게임
    steam("monster-train", "Monster Train", "roguelike-deckbuilder", aliases=["몬스터 트레인"]),
    steam("griftlands", "Griftlands", "roguelike-deckbuilder", aliases=["그리프트랜즈"]),
    steam("across-the-obelisk", "Across the Obelisk", "roguelike-deckbuilder", aliases=["어크로스 더 오벨리스크"]),
    steam("wildfrost", "Wildfrost", "roguelike-deckbuilder", aliases=["와일드프로스트"]),
    steam("slay-the-spire-2", "Slay the Spire 2", "roguelike-deckbuilder", aliases=["슬레이 더 스파이어 2"]),
    # 공포 · 서바이벌 호러
    steam("resident-evil-7", "Resident Evil 7 Biohazard", "horror-thriller", aliases=["바이오하자드 7"]),
    steam("resident-evil-3", "Resident Evil 3", "horror-thriller", aliases=["바이오하자드 3"]),
    steam("dead-space", "Dead Space", "horror-thriller", aliases=["데드 스페이스"]),
    steam("the-callisto-protocol", "The Callisto Protocol", "horror-thriller", aliases=["칼리스토 프로토콜"]),
    steam("alan-wake", "Alan Wake", "horror-thriller", aliases=["앨런 웨이크"]),
    steam("amnesia-dark-descent", "Amnesia: The Dark Descent", "horror-thriller", aliases=["암네시아"]),
    steam("outlast-2", "Outlast 2", "horror-thriller", aliases=["아웃라스트 2"]),
    # 스토리 · 내러티브 · 추리
    steam("kentucky-route-zero", "Kentucky Route Zero", "story-narrative-vn", aliases=["켄터키 루트 제로"]),
    steam("firewatch", "Firewatch", "story-narrative-vn", aliases=["파이어워치"]),
    steam("before-your-eyes", "Before Your Eyes", "story-narrative-vn", aliases=["비포 유어 아이즈"]),
    steam("as-dusk-falls", "As Dusk Falls", "story-narrative-vn", aliases=["애즈 더스크 폴즈"]),
    steam("the-forgotten-city", "The Forgotten City", "story-narrative-vn", aliases=["포가튼 시티"]),
    steam("norco", "NORCO", "story-narrative-vn", aliases=["노르코"]),
    steam("citizen-sleeper-2", "Citizen Sleeper 2: Starward Vector", "story-narrative-vn", aliases=["시티즌 슬리퍼 2"]),
    steam("1000xresist", "1000xRESIST", "story-narrative-vn", aliases=["1000x리지스트"]),
    # 퍼즐 · 두뇌 · 공간 논리
    steam("blue-prince", "Blue Prince", "puzzle-logic", aliases=["블루 프린스"]),
    steam("braid-anniversary", "Braid, Anniversary Edition", "puzzle-logic", aliases=["브레이드"]),
    steam("fez", "FEZ", "puzzle-logic", aliases=["페즈"]),
    steam("stephens-sausage-roll", "Stephen's Sausage Roll", "puzzle-logic", aliases=["스티븐 소시지 롤"]),
    steam("isles-of-sea-and-sky", "Isles of Sea and Sky", "puzzle-logic", aliases=["아일즈 오브 씨 앤 스카이"]),
    steam("the-roottrees-are-dead", "The Roottrees are Dead", "puzzle-logic", aliases=["루트트리"]),
    # 잠입 · 전술 액션
    steam("deus-ex-mankind-divided", "Deus Ex: Mankind Divided", "stealth-tactical", aliases=["데우스 엑스 맨카인드 디바이디드"]),
    steam("shadow-gambit", "Shadow Gambit: The Cursed Crew", "stealth-tactical", aliases=["섀도우 갬빗"]),
    steam("desperados-3", "Desperados III", "stealth-tactical", aliases=["데스페라도스 3"]),
    steam("invisible-inc", "Invisible, Inc.", "stealth-tactical", aliases=["인비저블"]),
    steam("gunpoint", "Gunpoint", "stealth-tactical", aliases=["건포인트"]),
    # 협동 · 파티
    steam("repo", "R.E.P.O.", "co-op-party", aliases=["레포"]),
    steam("peak", "PEAK", "co-op-party", aliases=["피크"]),
    steam("schedule-i", "Schedule I", "co-op-party", aliases=["스케줄 1"]),
    steam("chained-together", "Chained Together", "co-op-party", aliases=["체인드 투게더"]),
    steam("escape-simulator", "Escape Simulator", "co-op-party", aliases=["이스케이프 시뮬레이터"]),
    steam("ultimate-chicken-horse", "Ultimate Chicken Horse", "co-op-party", aliases=["얼티밋 치킨 호스"]),
    steam("keep-talking", "Keep Talking and Nobody Explodes", "co-op-party", aliases=["키프 토킹"]),
    steam("gang-beasts", "Gang Beasts", "co-op-party", aliases=["갱 비스트"]),
    # 서바이벌 · 크래프팅
    steam("kenshi", "Kenshi", "survival-crafting", aliases=["켄시"]),
    steam("the-planet-crafter", "The Planet Crafter", "survival-crafting", aliases=["플래닛 크래프터"]),
    steam("smalland", "Smalland: Survive the Wilds", "survival-crafting", aliases=["스몰랜드"]),
    steam("stranded-deep", "Stranded Deep", "survival-crafting", aliases=["스트랜디드 딥"]),
    # 도시 건설 · 경영
    steam("songs-of-syx", "Songs of Syx", "city-builder-management", aliases=["송스 오브 식스"]),
    steam("kingdoms-and-castles", "Kingdoms and Castles", "city-builder-management", aliases=["킹덤 앤 캐슬"]),
    # 생활 · 농장 · 타이쿤
    steam("two-point-museum", "Two Point Museum", "sim-tycoon-casual", aliases=["투 포인트 뮤지엄"]),
    steam("tcg-card-shop-simulator", "TCG Card Shop Simulator", "sim-tycoon-casual", aliases=["TCG 카드샵 시뮬레이터"]),
    steam("story-of-seasons-awl", "STORY OF SEASONS: A Wonderful Life", "sim-tycoon-casual", aliases=["목장이야기"]),
    # 샌드박스 · 크리에이티브
    steam("the-sims-4", "The Sims 4", "sandbox-creative", aliases=["심즈 4"]),
    steam("planet-coaster-2", "Planet Coaster 2", "sandbox-creative", aliases=["플래닛 코스터 2"]),
    steam("parkitect", "Parkitect", "sandbox-creative", aliases=["파키텍트"]),
    # 레이싱 · 스포츠
    steam("need-for-speed-heat", "Need for Speed Heat", "racing-sim", aliases=["니드 포 스피드 히트"]),
    steam("f1-25", "F1 25", "racing-sim", aliases=["F1 25"]),
    steam("motogp-25", "MotoGP 25", "racing-sim", aliases=["모토GP 25"]),
    steam("snowrunner", "SnowRunner", "racing-sim", aliases=["스노우러너"]),
    # 우주 · 비행 · SF 시뮬
    steam("chorus", "Chorus", "space-flight-sim", aliases=["코러스"]),
    steam("everspace", "EVERSPACE", "space-flight-sim", aliases=["에버스페이스"]),
    # 핵 앤 슬래시 · 액션 RPG
    steam("minecraft-dungeons", "Minecraft Dungeons", "arpg-hack-slash", aliases=["마인크래프트 던전스"]),
    steam("ghostlore", "Ghostlore", "arpg-hack-slash", aliases=["고스트로어"]),
    steam("the-slormancer", "The Slormancer", "arpg-hack-slash", aliases=["슬로만서"]),
    # 격투 · 콤보 액션
    steam("bayonetta", "Bayonetta", "fighting-action", aliases=["바요네타"]),
    steam("okami-hd", "Okami HD", "fighting-action", aliases=["오오카미", "ŌKAMI HD"]),
    # 모바일 서브컬처 · 방치형
    ios("honkai-impact-3rd", "Honkai Impact 3rd", "mobile-subculture-idle", aliases=["붕괴 3rd"]),
    ios("punishing-gray-raven", "Punishing: Gray Raven", "mobile-subculture-idle", aliases=["퍼니싱 그레이 레이븐"]),
    play("snowbreak", "Snowbreak: Containment Zone", "mobile-subculture-idle", "com.seasun.snowbreak.google", aliases=["스노우브레이크"]),
    ios("aether-gazer", "Aether Gazer", "mobile-subculture-idle", aliases=["이터 게이저"]),
    ios("path-to-nowhere", "Path to Nowhere", "mobile-subculture-idle", aliases=["패스 투 노웨어"]),
    ios("neural-cloud", "Neural Cloud", "mobile-subculture-idle", aliases=["뉴럴 클라우드"]),
    # 모바일 캐주얼 · 퍼즐
    ios("monument-valley-3", "Monument Valley 3", "mobile-casual-puzzle", aliases=["모뉴먼트 밸리 3"]),
    ios("threes", "Threes!", "mobile-casual-puzzle", aliases=["쓰리즈"]),
    ios("little-alchemy-2", "Little Alchemy 2", "mobile-casual-puzzle", aliases=["리틀 알케미 2"]),
    play("nyt-games", "NYT Games", "mobile-casual-puzzle", "com.nytimes.crossword", aliases=["뉴욕타임즈 게임즈"]),
    # 모바일 액션 · 아케이드
    play("stumble-guys", "Stumble Guys", "mobile-action-arcade", "com.kitkagames.fallbuddies", aliases=["스텀블 가이즈"]),
    ios("archero-2", "Archero 2", "mobile-action-arcade", aliases=["아처로 2"]),
    ios("soul-knight-prequel", "Soul Knight Prequel", "mobile-action-arcade", aliases=["소울 나이트 프리퀄"]),
    # 모바일 전략 · 디펜스
    play("rush-royale", "Rush Royale", "mobile-strategy-defense", "com.my.defense", aliases=["러시 로얄"]),
    play("boom-beach", "Boom Beach", "mobile-strategy-defense", "com.supercell.boombeach", aliases=["붐 비치"]),
    play("whiteout-survival", "Whiteout Survival", "mobile-strategy-defense", "com.gof.global", aliases=["화이트아웃 서바이벌"]),
    ios("last-war-survival", "Last War: Survival", "mobile-strategy-defense", aliases=["라스트 워"]),
    # 모바일 수집형 RPG
    ios("dokkan-battle", "DRAGON BALL Z DOKKAN BATTLE", "mobile-gacha-rpg", aliases=["드래곤볼Z 도칸 배틀"]),
    ios("one-piece-treasure-cruise", "ONE PIECE TREASURE CRUISE", "mobile-gacha-rpg", aliases=["원피스 트레저 크루즈"]),
    ios("bleach-brave-souls", "BLEACH Brave Souls", "mobile-gacha-rpg", aliases=["블리치 브레이브 소울즈"]),
    # 디지털 보드 · 카드 · 체스
    play("uno-mobile", "UNO!", "card-board-digital", "com.matteljv.uno", aliases=["우노"]),
    steam("codenames", "Codenames", "card-board-digital", aliases=["코드네임"]),
    steam("root-digital", "Root", "card-board-digital", aliases=["루트 보드게임"]),
    # 리듬 · 음악 게임
    steam("trombone-champ", "Trombone Champ", "rhythm-music", aliases=["트롬본 챔프"]),
    steam("spin-rhythm-xd", "Spin Rhythm XD", "rhythm-music", aliases=["스핀 리듬"]),
    # 스포츠 · MOBA · 경쟁
    steam("rematch", "Rematch", "sports-competitive", aliases=["리매치"]),
    steam("wwe-2k25", "WWE 2K25", "sports-competitive", aliases=["WWE 2K25"]),
]

# ── 신규 앱 비교군 1: 화면 녹화 · 방송 · 스트리밍
ITEMS += [
    ios("loom", "Loom", "streaming-screen-capture", aliases=["룸"]),
    gh("screenity", "Screenity", "streaming-screen-capture", "alyssaxuu/screenity", aliases=["스크리니티"], platforms=["windows", "macos", "linux", "web"]),
    gh("cap-screen-recorder", "Cap", "streaming-screen-capture", "CapSoftware/Cap", aliases=["캡"], platforms=["windows", "macos"]),
    ios("camtasia", "TechSmith Capture", "streaming-screen-capture", aliases=["캠테시아", "Camtasia"]),
    play("soop", "SOOP", "streaming-screen-capture", "kr.co.nowcom.mobile.afreeca", aliases=["아프리카TV", "AfreecaTV"], name_en="SOOP"),
    gh("streamlabs-desktop", "Streamlabs Desktop", "streaming-screen-capture", "streamlabs/desktop", aliases=["스트림랩스"], platforms=["windows", "macos"]),
    play("mobizen", "Mobizen", "streaming-screen-capture", "com.rsupport.mvagent", aliases=["모비즌"]),
    play("az-screen-recorder", "AZ Screen Recorder", "streaming-screen-capture", "com.hecorat.screenrecorder.free", aliases=["AZ 스크린 레코더"]),
    play("prism-live-studio", "PRISM Live Studio", "streaming-screen-capture", "com.prism.live", aliases=["프리즘 라이브"]),
    ios("medal-tv", "Medal - Game Clipping", "streaming-screen-capture", aliases=["메달", "Medal.tv"]),
]

# ── 신규 앱 비교군 2: 음악 제작 · DAW · 팟캐스트
ITEMS += [
    ios("castro", "Castro: Podcast App & Player", "audio-daw-podcast", aliases=["카스트로", "Castro"]),
    play("castbox", "Castbox", "audio-daw-podcast", "com.podcast.podcasts", aliases=["캐스트박스"]),
    play("podbean", "Podbean", "audio-daw-podcast", "com.podbean.app.podcast", aliases=["팟빈"]),
    ios("snipd", "Snipd | AI Podcast Player", "audio-daw-podcast", aliases=["스닙드", "Snipd"]),
    play("podcast-addict", "Podcast Addict", "audio-daw-podcast", "com.bambuna.podcastaddict", aliases=["팟캐스트 어딕트"]),
    ios("player-fm", "Player FM", "audio-daw-podcast", aliases=["플레이어 FM"]),
    ios("soundtrap", "Soundtrap", "audio-daw-podcast", aliases=["사운드트랩"]),
    ios("koala-sampler", "Koala Sampler", "audio-daw-podcast", aliases=["코알라 샘플러"]),
    ios("korg-gadget", "KORG Gadget", "audio-daw-podcast", aliases=["코르그 가젯"]),
    ios("cubasis-3", "Cubasis 3", "audio-daw-podcast", aliases=["큐베이시스"]),
    ios("ableton-note", "Ableton Note", "audio-daw-podcast", aliases=["에이블톤 노트"]),
    gh("ardour", "Ardour", "audio-daw-podcast", "Ardour/ardour", aliases=["아더"], platforms=["windows", "macos", "linux"]),
    gh("zrythm", "Zrythm", "audio-daw-podcast", "zrythm/zrythm", aliases=["지리듬"], platforms=["windows", "macos", "linux"]),
]

# ── 신규 앱 비교군 3: 교통 · 숙박 · 항공 · 모빌리티
ITEMS += [
    ios("kakao-t", "카카오 T", "travel-mobility-booking", aliases=["Kakao T"], name_en="Kakao T"),
    play("agoda", "Agoda", "travel-mobility-booking", "com.agoda.mobile.consumer", aliases=["아고다"]),
    play("expedia", "Expedia", "travel-mobility-booking", "com.expedia.bookings", aliases=["익스피디아"]),
    play("kayak", "Kayak", "travel-mobility-booking", "com.kayak.android", aliases=["카약"]),
    play("hotels-com", "Hotels.com", "travel-mobility-booking", "com.hcom.android", aliases=["호텔스닷컴"]),
    play("trivago", "trivago", "travel-mobility-booking", "com.trivago", aliases=["트리바고"]),
    play("klook", "Klook", "travel-mobility-booking", "com.klook", aliases=["클룩"]),
    play("getyourguide", "GetYourGuide", "travel-mobility-booking", "com.getyourguide.android", aliases=["겟유어가이드"]),
    play("trainline", "Trainline", "travel-mobility-booking", "com.thetrainline", aliases=["트레인라인"]),
    play("omio", "Omio", "travel-mobility-booking", "com.goeuro.rosie", aliases=["오미오"]),
    play("bolt", "Bolt", "travel-mobility-booking", "ee.mtakso.client", aliases=["볼트"]),
    play("grab", "Grab", "travel-mobility-booking", "com.grabtaxi.passenger", aliases=["그랩"]),
    play("lyft", "Lyft", "travel-mobility-booking", "me.lyft.android", aliases=["리프트"]),
    play("hopper", "Hopper", "travel-mobility-booking", "com.hopper.mountainview.play", aliases=["호퍼"]),
]

# ── 신규 앱 비교군 4: AI 글쓰기 · 리서치 · 전사
ITEMS += [
    play("grammarly", "Grammarly", "ai-writing-research", "com.grammarly.android.keyboard", aliases=["그래머리"]),
    ios("quillbot", "QuillBot", "ai-writing-research", aliases=["퀼봇"]),
    play("deepseek", "DeepSeek", "ai-writing-research", "com.deepseek.chat", aliases=["딥시크"]),
    play("poe", "Poe", "ai-writing-research", "com.poe.android", aliases=["포"]),
    play("otter-ai", "Otter.ai", "ai-writing-research", "com.aisense.otter", aliases=["오터"]),
    ios("scispace", "SciSpace", "ai-writing-research", aliases=["사이스페이스"]),
    play("kimi", "Kimi", "ai-writing-research", "com.moonshot.kimichat", aliases=["키미"]),
    ios("wordtune", "Wordtune", "ai-writing-research", aliases=["워드튠"]),
    ios("alphaxiv", "alphaXiv", "ai-writing-research", aliases=["알파엑시브"]),
    gh("zotero", "Zotero", "ai-writing-research", "zotero/zotero", aliases=["조테로"], platforms=["windows", "macos", "linux"]),
    ios("you-com", "You.com", "ai-writing-research", aliases=["유닷컴"]),
    ios("sudowrite", "Sudowrite - AI Novel Writing", "ai-writing-research", aliases=["수도라이트", "Sudowrite"]),
]

# ── 기존 앱 비교군 보강
ITEMS += [
    # 개발자 도구 · 터미널 · API
    gh("lazygit", "lazygit", "dev-terminals-git", "jesseduffield/lazygit", aliases=["레이지깃"]),
    gh("tmux", "tmux", "dev-terminals-git", "tmux/tmux", aliases=["티먹스"]),
    gh("fzf", "fzf", "dev-terminals-git", "junegunn/fzf", aliases=["에프지에프"]),
    gh("ripgrep", "ripgrep", "dev-terminals-git", "BurntSushi/ripgrep", aliases=["립그렙"]),
    gh("starship", "Starship", "dev-terminals-git", "starship/starship", aliases=["스타십"]),
    gh("bat", "bat", "dev-terminals-git", "sharkdp/bat", aliases=["뱃"]),
    gh("hoppscotch", "Hoppscotch", "dev-terminals-git", "hoppscotch/hoppscotch", aliases=["홉스카치"], platforms=["web", "windows", "macos", "linux"]),
    # 시스템 · 파일 · 유틸
    gh("nanazip", "NanaZip", "system-file-utils", "M2Team/NanaZip", aliases=["나나집"], platforms=["windows"]),
    gh("czkawka", "Czkawka", "system-file-utils", "qarmin/czkawka", aliases=["츠카프카"]),
    gh("bleachbit", "BleachBit", "system-file-utils", "bleachbit/bleachbit", aliases=["블리치빗"], platforms=["windows", "linux"]),
    gh("qbittorrent", "qBittorrent", "system-file-utils", "qbittorrent/qBittorrent", aliases=["큐비트토렌트"]),
    gh("transmission", "Transmission", "system-file-utils", "transmission/transmission", aliases=["트랜스미션"]),
    # 3D · CAD · 모델링
    gh("openscad", "OpenSCAD", "3d-cad-design", "openscad/openscad", aliases=["오픈스캐드"]),
    gh("blockbench", "Blockbench", "3d-cad-design", "JannisX11/blockbench", aliases=["블록벤치"]),
    gh("solvespace", "SolveSpace", "3d-cad-design", "solvespace/solvespace", aliases=["솔브스페이스"]),
    # 오피스 · 문서 · 화이트보드
    gh("appflowy", "AppFlowy", "office-suite", "AppFlowy-IO/AppFlowy", aliases=["앱플로우"]),
    gh("affine", "AFFiNE", "office-suite", "toeverything/AFFiNE", aliases=["어파인"]),
    gh("outline-wiki", "Outline", "office-suite", "outline/outline", aliases=["아웃라인"]),
    gh("cryptpad", "CryptPad", "office-suite", "cryptpad/cryptpad", aliases=["크립트패드"], platforms=["web"]),
    # 이미지 · 그래픽 편집
    gh("upscayl", "Upscayl", "image-editors", "upscayl/upscayl", aliases=["업스케일"]),
    gh("rawtherapee", "RawTherapee", "image-editors", "RawTherapee/RawTherapee", aliases=["로우데라피"]),
    gh("digikam", "digiKam", "image-editors", "KDE/digikam", aliases=["디지캠"]),
    gh("graphite", "Graphite", "image-editors", "GraphiteEditor/Graphite", aliases=["그래파이트"], platforms=["windows", "macos", "linux", "web"]),
    # 영상 편집 · 녹화
    gh("natron", "Natron", "video-editing", "NatronGitHub/Natron", aliases=["나트론"]),
    play("inshot", "InShot", "video-editing", "com.camerasideas.instashot", aliases=["인샷"]),
    play("powerdirector", "PowerDirector", "video-editing", "com.cyberlink.powerdirector.DRA140225_01", aliases=["파워디렉터"]),
    # 노트 · 지식관리
    gh("memos", "Memos", "pkm-notes", "usememos/memos", aliases=["메모스"], platforms=["windows", "macos", "linux", "android", "ios", "web"]),
    gh("silverbullet", "SilverBullet", "pkm-notes", "silverbulletmd/silverbullet", aliases=["실버불릿"], platforms=["web"]),
    gh("notesnook", "Notesnook", "pkm-notes", "streetwriters/notesnook", aliases=["노트스누크"]),
    # 할 일 · 일정 관리
    gh("vikunja", "Vikunja", "task-managers", "go-vikunja/vikunja", aliases=["비쿤야"]),
    gh("focalboard", "Focalboard", "task-managers", "mattermost-community/focalboard", aliases=["포컬보드"]),
    gh("plane", "Plane", "task-managers", "makeplane/plane", aliases=["플레인"], platforms=["web"]),
    # 비밀번호 관리
    gh("keepassdx", "KeePassDX", "password-managers", "Kunzisoft/KeePassDX", aliases=["키패스DX"], platforms=["android"]),
    gh("buttercup", "Buttercup", "password-managers", "buttercup/buttercup", aliases=["버터컵"]),
    # 캘린더 · 시간 관리
    gh("etar", "Etar", "calendar-apps", "Etar-Group/Etar-Calendar", aliases=["에타"], platforms=["android"]),
    gh("fossify-calendar", "Fossify Calendar", "calendar-apps", "FossifyOrg/Calendar", aliases=["포시파이 캘린더"], platforms=["android"]),
    # 이메일 클라이언트
    gh("mailspring", "Mailspring", "email-clients", "Foundry376/Mailspring", aliases=["메일스프링"]),
    gh("neomutt", "NeoMutt", "email-clients", "neomutt/neomutt", aliases=["네오머트"], platforms=["windows", "macos", "linux"]),
    # 클라우드 스토리지
    gh("seafile", "Seafile", "cloud-storage", "haiwen/seafile", aliases=["씨파일"]),
    gh("owncloud", "ownCloud", "cloud-storage", "owncloud/core", aliases=["오운클라우드"]),
    gh("filebrowser", "File Browser", "cloud-storage", "filebrowser/filebrowser", aliases=["파일 브라우저"]),
    # 백업 · 파일 동기화
    gh("pika-backup", "Pika Backup", "backup-sync", "pika-backup/pika-backup", aliases=["피카 백업"], platforms=["linux"]),
    gh("timeshift", "Timeshift", "backup-sync", "linuxmint/timeshift", aliases=["타임시프트"], platforms=["linux"]),
    gh("backrest", "Backrest", "backup-sync", "garethgeorge/backrest", aliases=["백레스트"]),
    # 읽기 · 북마크 보관
    gh("linkwarden", "Linkwarden", "read-later", "linkwarden/linkwarden", aliases=["링크워든"]),
    gh("karakeep", "Karakeep", "read-later", "karakeep-app/karakeep", aliases=["카라킵"]),
    # 번역 · 필기 · 학습
    ios("mathpix", "Mathpix", "translation-study-notes", aliases=["매스픽스"]),
    ios("gauth", "Gauth", "translation-study-notes", aliases=["고수"]),
    play("brainly", "Brainly", "translation-study-notes", "co.brainly", aliases=["브레인리"]),
    # 건강 · 운동 · 러닝
    play("withings", "Withings", "health-fitness", "com.withings.wiscale2", aliases=["위딩스"]),
    play("adidas-running", "Adidas Running", "health-fitness", "com.runtastic.android", aliases=["아디다스 러닝"]),
    play("lose-it", "Lose It!", "health-fitness", "com.fitnow.loseit", aliases=["루즈 잇"]),
    play("freeletics", "Freeletics", "health-fitness", "com.freeletics.lite", aliases=["프리레틱스"]),
    play("fiton", "FitOn", "health-fitness", "com.fiton.android", aliases=["피톤"]),
    # 가계부 · 금융 · 자산 관리
    gh("actual-budget", "Actual Budget", "finance-budget-crypto", "actualbudget/actual", aliases=["액추얼"]),
    gh("firefly-iii", "Firefly III", "finance-budget-crypto", "firefly-iii/firefly-iii", aliases=["파이어플라이 III"]),
    gh("ghostfolio", "Ghostfolio", "finance-budget-crypto", "ghostfolio/ghostfolio", aliases=["고스트폴리오"]),
    ios("copilot-money", "Copilot: Track & Budget Money", "finance-budget-crypto", aliases=["코파일럿 머니", "Copilot Money"]),
    ios("monarch-money", "Monarch: Budget & Track Money", "finance-budget-crypto", aliases=["모나크 머니", "Monarch Money"]),
    # 날씨 · 스마트홈 · IoT
    play("shelly-smart", "Shelly Smart Control", "weather-iot-smarthome", "cloud.shelly.smartcontrol", aliases=["셸리"]),
    play("ewelink", "eWeLink", "weather-iot-smarthome", "com.coolkit", aliases=["이위링크"]),
    play("switchbot", "SwitchBot", "weather-iot-smarthome", "com.theswitchbot.switchbot", aliases=["스위치봇"]),
    play("aqara-home", "Aqara Home", "weather-iot-smarthome", "com.lumiunited.aqarahome.play", aliases=["아카라 홈"]),
    play("tado", "tado°", "weather-iot-smarthome", "com.tado", aliases=["타도"]),
    # OTT · 영상 스트리밍
    play("vimeo", "Vimeo", "streaming-video", "com.vimeo.android.videoapp", aliases=["비메오"]),
    play("dailymotion", "Dailymotion", "streaming-video", "com.dailymotion.dailymotion", aliases=["데일리모션"]),
    play("watcha", "Watcha", "streaming-video", "com.frograms.watcha", aliases=["왓챠"], name_en="Watcha"),
    play("coupang-play", "Coupang Play", "streaming-video", "com.coupang.mobile.play", aliases=["쿠팡 플레이"], name_en="Coupang Play"),
    # 소셜 · 커뮤니티
    ios("damus", "Damus", "social-community", aliases=["다무스"]),
    play("lemon8", "Lemon8", "social-community", "com.bd.nproject", aliases=["레몬8"]),
    # 메신저 · 팀 협업
    gh("session", "Session", "messaging-team", "oxen-io/session-android", aliases=["세션"], platforms=["windows", "macos", "linux", "android", "ios"]),
    gh("briar", "Briar", "messaging-team", "briar/briar", aliases=["브라이어"], platforms=["android"]),
    gh("revolt", "Revolt", "messaging-team", "revoltchat/desktop", aliases=["리볼트"], platforms=["web"]),
    # 미디어 플레이어
    play("foobar2000", "foobar2000", "media-players", "com.foobar2000.foobar2000", aliases=["푸바2000"]),
    play("plexamp", "Plexamp", "media-players", "tv.plex.labs.plexamp", aliases=["플렉스앰프"]),
    gh("navidrome", "Navidrome", "media-players", "navidrome/navidrome", aliases=["나비드롬"], platforms=["windows", "macos", "linux", "web"]),
    # 사진 편집 · 카메라 · 스캔
    ios("procamera", "ProCamera", "photo-camera-filter", aliases=["프로카메라"]),
    ios("obscura", "Obscura", "photo-camera-filter", aliases=["옵스큐라"]),
    # 전자책 · 만화 · 뉴스 · 팟캐스트
    play("pressreader", "PressReader", "reading-ebooks-news", "com.newspaperdirect.pressreader.android", aliases=["프레스리더"]),
    play("magzter", "Magzter", "reading-ebooks-news", "com.dci.magzter", aliases=["매그스터"]),
    play("everand", "Everand", "reading-ebooks-news", "com.scribd.app.reader0", aliases=["에버랜드"]),
    # 쇼핑 · 배달 · 중고 · 예약
    play("coupang-eats", "Coupang Eats", "shopping-delivery-korea", "com.coupang.mobile.eats", aliases=["쿠팡이츠"], name_en="Coupang Eats"),
    ios("gmarket", "Gmarket", "shopping-delivery-korea", aliases=["지마켓"], name_en="Gmarket"),
    play("11st", "11st", "shopping-delivery-korea", "com.elevenst", aliases=["11번가"]),
    ios("ssg", "SSG.COM", "shopping-delivery-korea", aliases=["쓱닷컴"]),
    # 지도 · 내비게이션 · 여행
    play("mapy-cz", "Mapy.cz", "maps-navigation-travel", "cz.seznam.mapy", aliases=["마피"]),
    # 웹 브라우저
    gh("min-browser", "Min Browser", "web-browsers", "minbrowser/min", aliases=["민 브라우저"]),
    ios("orion-browser", "Orion Browser", "web-browsers", aliases=["오리온 브라우저"]),
]

SPEC = {
    "batch": "2026-11-26-bulk5-1000",
    "note": (
        "파로스 5차 대량 적재 — 게임 3개 신규 비교군(비주얼 노벨·인터랙티브 스토리, 경영·자동화·공장 건설, "
        "아케이드·리듬·클래식) + 앱 4개(화면 녹화·방송, 음악 제작·DAW·팟캐스트, 교통·숙박·항공·모빌리티, "
        "AI 글쓰기·리서치·전사) = 신규 7개 비교군과 기존 비교군 보강. 전체 1,000종 돌파 목표. "
        "각 항목은 Steam 검색어 / Google Play 패키지 / App Store 검색어 / GitHub 저장소 중 1개로 수집하며, "
        "bulk_ingest.py 중복 가드가 기존 867종과 겹치는 항목(id·정규화 이름·스토어 ID)을 자동 스킵한다."
    ),
    "catalog_note_marker": "2026-11-26 5차 대량 팩트 적재(v16)",
    "catalog_note": (
        "2026-11-26 5차 대량 팩트 적재(v16)로 게임에 비주얼 노벨·인터랙티브 스토리, 경영·자동화·공장 건설, "
        "아케이드·리듬·클래식 3개 비교군이, 앱에 화면 녹화·방송, 음악 제작·DAW·팟캐스트, 교통·숙박·항공·모빌리티, "
        "AI 글쓰기·리서치·전사 4개 비교군이 들어왔다(신규 7비교군 · 기존 40여 비교군 보강 · 총 {total}종)."
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
    out = HERE / "spec5.json"
    out.write_text(json.dumps(SPEC, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"→ {out} — 항목 {len(ITEMS)}종 · 신규 대분류 {len(CATEGORIES)} · 신규 비교군 {len(ARENAS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
