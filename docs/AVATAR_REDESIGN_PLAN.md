# AVATAR_REDESIGN_PLAN — overlay 1/3 + warstwy animacji

> Status: **PLAN** (do implementacji) · Wersja: 0.1 · Data: 2026-05-12 · Język: PL

## 1. Cel i kontekst

Obecny awatar VRM jest dominującym overlay'em na pulpicie (okno Electrona **400×600 px**, canvas Three.js o wysokości **340 px**) z działającą mimiką emocji i body sway, ale:

- nie reaguje wizualnie na `visual_state` (idle / listening / thinking / speaking → tylko zmiana koloru kropki w UI; awatar wygląda identycznie),
- nie ma eye trackingu — oczy stoją w martwym punkcie,
- emocje są poprawne, ale subtelne (crossfade 0.42 s, brak peak hold).

**Cel:** awatar staje się dyskretnym widgetem zajmującym **1/9 obecnej powierzchni** ekranu (~133×200 px), ale **„żyje" intensywniej** dzięki czterem nowym warstwom animacji:

1. **Oddychanie / micro-ruch ciała** — klatka piersiowa unosi się i opada, ramiona delikatnie rotują w fazie z oddechem.
2. **Pozy per `visual_state`** — głowa, sway, częstość mrugania reagują na to, w jakim stanie jest backend.
3. **Eye tracking / look-at** — awatar wodzi wzrokiem za kursorem; po 2 s bez ruchu myszy wykonuje saccade (powolne losowe spojrzenie w bok).
4. **Wzmocnienie istniejących emocji** — multiplier wagi blendshape'ów (1.25×), dłuższy crossfade (0.7 s), opcjonalna afterglow phase.

**Filozofia:** ponieważ overlay jest 3× mniejszy, każda mikro-zmiana liczy się bardziej. Drobne ruchy zastępują efekt skali.

---

## 2. Decyzje techniczne

### 2.1 Skalowanie UI — CSS transform, nie rewrite styli

Cały overlay (`<div>` w trybie `isElectron && !isConfigView`) dostaje `transform: scale(overlay_scale)` z `transformOrigin: "top left"`. Nie przepisujemy każdej wartości px/rem osobno. Konsekwencje:

- Zachowuje proporcje wszystkich elementów (avatar, chat panel, ikony, fonty).
- Memory/rendering Three.js bez zmian — canvas dalej renderuje w natywnej rozdzielczości, scale tylko visualizuje.
- Window Electrona zmniejszany niezależnie (`BrowserWindow.setBounds`) — szerokość/wysokość pomnożona przez `overlay_scale` na starcie.
- Trade-off: hit-areas są mniejsze, ale to akceptowalne dla widget mode'a.

**Alternatywa odrzucona:** rewrite każdego stylu inline. Powód: ~400 LoC zmian, ryzyko regresji, brak benefitu.

### 2.2 Animacje — czyste @pixiv/three-vrm 3.3.1, bez GSAP/Anime.js

Wszystkie animacje wykonywane w `useFrame` (R3F) z `clock.elapsedTime` + spring damping `1 - exp(-delta * k)`. Powody:

- Już używamy tej techniki dla body sway (`AvatarCanvas.tsx:181-183`) — spójność.
- Brak nowych dependencies — bundle size bez zmian.
- @pixiv/three-vrm 3.3.1 ma już `vrm.lookAt.target` (look-at), `vrm.expressionManager` (mimika), `vrm.humanoid.getNormalizedBoneNode` (bone control), `vrm.springBoneManager.update(delta)` (włosy / akcesoria).

### 2.3 Bone targets — humanoid normalized API

Wszystkie animacje ciała używają **normalizowanych nazw bone'ów** z VRM humanoid spec (`chest`, `spine`, `head`, `neck`, `leftUpperArm`, `rightUpperArm`). Działa cross-model (każdy VRM zgodny ze spec mapuje na te same nazwy).

### 2.4 Konfiguracja sterowana z backendu

Wszystkie parametry (skala, włączenie warstw, intensity, crossfade) w `UIConfig` (Pydantic) → YAML / PUT `/api/v1/config` → broadcast WS `ui_config_changed`. Hot-reload bez restartu Electrona dla większości pól (skala okna wymaga `setBounds`).

---

## 3. Specyfikacja warstw

### 3.1 Skalowanie overlay

| Parametr | Wartość | Zakres | Opis |
|----------|---------|--------|------|
| `ui.overlay_scale` | 0.333 | 0.2–1.5 | Skala CSS transform na overlay root |
| `BrowserWindow.width` | `400 * scale` | min 80 | Wymiar fizyczny okna |
| `BrowserWindow.height` | `600 * scale` | min 120 | Wymiar fizyczny okna |

Renderer Three.js dostosowuje się automatycznie do rozmiaru canvas (`<Canvas>` z R3F ma autoresize). FOV i pozycja kamery **bez zmian** — proporcje awatara w kadrze zostają.

### 3.2 Breathing layer

Sinusoidalna animacja oddychania, nakładana **po** body sway.

| Parametr | Wartość | Opis |
|----------|---------|------|
| Częstotliwość | 0.42 rad/s (~0.067 Hz) | ~2.4 s pełny cykl wdech-wydech |
| Amplituda klatki | 0.018 (skala Y `chest`) | ~2% rozszerzenia |
| Amplituda ramion | 0.012 rad rotacji Z | ~0.7° symetrycznie |

Aktywne tylko gdy `ui.avatar_breathing_enabled = true`. Wzór:

```
breathT = clock.elapsedTime * 0.42
chest.scale.y = 1 + sin(breathT) * 0.018
leftUpperArm.rotation.z  = +sin(breathT) * 0.012
rightUpperArm.rotation.z = -sin(breathT) * 0.012
```

### 3.3 State pose layer

Nakłada offsety pozy głowy + modyfikatory innych systemów w zależności od `visualState`.

| State | headPitch | headYaw | headTiltZ | swayMul | blinkPeriodMul | emotionMul |
|-------|-----------|---------|-----------|---------|----------------|------------|
| `idle` | 0 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| `listening` | +0.06 (do przodu) | +0.04 | +0.05 | 0.6 | 1.4 (rzadziej mruga, „uważa") | 1.05 |
| `thinking` | −0.12 (lekko w górę) | +0.08 | +0.10 | 0.5 | 0.8 (częściej, „rusza myśli") | 1.0 |
| `speaking` | +0.02 | 0 | 0 | 1.4 | 1.6 | 1.2 |

Wartości w radianach (głowa) i mnożnikach. Przejście między stanami: damping `exp(-delta * 4.5)` (~0.2 s do 95% target).

### 3.4 LookAt layer

Awatar śledzi kursor myszki (znormalizowany do −1..+1 w obu osiach), z dampingiem `exp(-delta * 6)` (~150 ms).

| Tryb | Warunek | Cel |
|------|---------|-----|
| Track mouse | `now - lastMouseMove < 2.0 s` | `(mouseX * 0.8, mouseY * 0.5 + 1.3, 1.5)` |
| Saccade | `now - lastMouseMove >= 2.0 s` | Losowy w zakresie `(±0.3, ±0.15) + offset`, co 4–7 s |
| No mouse | `mousePos === null` | Domyślnie `(0, 1.3, 1.5)` (na wprost) |

VRM-side: `vrm.lookAt.target = lookTargetObject` + `vrm.lookAt.update(delta)` (już w `vrm.update`). Tracker rotuje oczy + opcjonalnie szyję (zależnie od `vrm.lookAt.type`).

### 3.5 Emotion intensity boost

| Parametr | Stara wartość | Nowa | Opis |
|----------|---------------|------|------|
| `EMOTION_INTENSITY` | brak (= 1.0) | 1.25 (configurable) | Mnoży każdą wagę blendshape'a, clamped do 1.0 |
| `EMOTION_CROSSFADE_SEC` | 0.42 s | 0.7 s | Dłuższe przejście — bardziej widoczne |
| `EMOTION_AFTERGLOW` | brak | 0.4 s (Phase 2) | Hold peak przed decay — pomijane w iteracji 1 |

Wzór apply (linia 200-214 w `AvatarCanvas.tsx`):

```
em.resetValues()
for (name, w) in blended:
    em.setValue(name, min(1.0, w * emotionIntensity * stateBonus))
```

Gdzie `stateBonus = STATE_POSE[visualState].emotionWeightMul`.

---

## 4. Diagram warstw (kolejność w `useFrame`)

```
┌─ useFrame (każda klatka) ─────────────────────────────────────────┐
│                                                                    │
│  1. emotion target update    (jeśli emotion prop się zmienił)     │
│         │                                                          │
│         ▼                                                          │
│  2. interpolacja EMOTION_BODY (sway params per emotion)            │
│         │                                                          │
│         ▼                                                          │
│  3. state pose interp        (head offsets + multipliers)         │
│         │                                                          │
│         ▼                                                          │
│  4. apply body sway          (chest/spine rotation × swayMul)     │
│         │                                                          │
│         ▼                                                          │
│  5. apply breathing          (chest.scale.y + arms rotation Z)    │
│         │                                                          │
│         ▼                                                          │
│  6. apply state pose         (head rotation += offsets)           │
│         │                                                          │
│         ▼                                                          │
│  7. update lookAt target     (mouse pos / saccade)                │
│         │                                                          │
│         ▼                                                          │
│  8. blink update             (period × blinkPeriodMul)            │
│         │                                                          │
│         ▼                                                          │
│  9. expression crossfade     (emotion × intensity × stateBonus)   │
│         │                                                          │
│         ▼                                                          │
│  10. lipsync apply           (em.setValue("aa", level))           │
│         │                                                          │
│         ▼                                                          │
│  11. vrm.update(delta)       (lookAt eyes, expressions, springs)  │
│         │                                                          │
│         ▼                                                          │
│  12. render                  (R3F renderuje scenę)                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Niezmienione:** lip-sync (warstwa 10) działa jak dziś, nakłada się na expressions.

---

## 5. Tabela hot-reload kluczy `ui.*`

| Klucz | Hot-reload | Wymagany restart Electron | Uwagi |
|-------|------------|---------------------------|-------|
| `ui.chat_panel_*` | ✅ | — | Już działa |
| `ui.overlay_scale` | ⚠ częściowo | Tylko BrowserWindow bounds (Electron API `setBounds`) | CSS transform aplikuje się natychmiast, ale fizyczne okno wymaga `setBounds` |
| `ui.avatar_breathing_enabled` | ✅ | — | Prop do VrmRoot, natychmiast |
| `ui.avatar_state_poses_enabled` | ✅ | — | Prop |
| `ui.avatar_look_at_enabled` | ✅ | — | Prop |
| `ui.avatar_emotion_intensity` | ✅ | — | Prop, kolejny crossfade już ze zmienioną wartością |
| `ui.avatar_emotion_crossfade_sec` | ✅ | — | Prop |

Implementacja w `backend/services/runtime_config.py`: broadcast eventu `ui_config_changed` z pełnym `cfg.ui` do wszystkich sesji WS. Frontend w `App.tsx` ma listener → setState → re-render `AvatarCanvas` z nowymi props.

---

## 6. Acceptance criteria

Po wdrożeniu wszystkie poniższe punkty muszą być spełnione (manualny smoke):

- [ ] **Skala**: po `npm run build && npm run electron` okno avatara wystartuje ~133×200 px (1/3 z 400×600). `PUT /api/v1/config` z `overlay_scale=1.0` → okno + CSS rozciągają się natychmiast (lub po `setBounds`).
- [ ] **Oddychanie**: w trybie `idle` przyglądając się klatce piersiowej widoczna jest delikatna pulsacja co ~2.4 s. Ramiona unoszą się i opadają symetrycznie.
- [ ] **State pose listening**: po PTT awatar pochyla głowę lekko do przodu i w bok, mruga rzadziej.
- [ ] **State pose thinking**: po zakończeniu PTT (przed odpowiedzią głosem) głowa idzie w górę i w bok („zastanawia się"), więcej mrugnięć.
- [ ] **State pose speaking**: w trakcie odpowiedzi sway ma większą amplitudę, mrugnięć jeszcze więcej, emocja jest 20% mocniejsza.
- [ ] **LookAt mouse**: ruch myszki nad oknem → oczy podążają z 150 ms opóźnieniem (smooth).
- [ ] **Saccade**: po 2 s bez ruchu myszki awatar wykonuje losowe spojrzenie w bok, kolejne po 4–7 s.
- [ ] **Emocja wzmocniona**: `[EMO:happy]` jest wizualnie wyraźniejsza niż dziś (oko porównawcze przed/po). Crossfade odczuwalnie wolniejszy (0.7 s vs 0.42 s).
- [ ] **Hot-reload bez restartu**: `curl -X PUT /api/v1/config -d '{"patch":{"ui":{"avatar_emotion_intensity":2.0}}}'` → następna emocja od razu silniejsza.
- [ ] **Brak regresji**: lip-sync działa dalej, mrugnięcie nie blokuje się, mimika nie miga.

---

## 7. Implementacja — pliki

| Plik | Zmiana | Linie istotne |
|------|--------|---------------|
| `backend/config/schema.py` | Dodać pola do `UIConfig` | 389-396 |
| `backend/services/runtime_config.py` | Broadcast `ui_config_changed` | `apply_reload_configuration` |
| `frontend/electron-main.cjs` | `createWindow` używa `overlay_scale` | 24-25, 257-275 |
| `frontend/preload.cjs` | Eksport `overlayScale` | bridge `window.assystent` |
| `frontend/src/App.tsx` | Wrapper `transform: scale`, mouse tracker, `visualState` + props do AvatarCanvas, listener `ui_config_changed` | 219, 885-930 |
| `frontend/src/AvatarCanvas.tsx` | 5 nowych warstw w `VrmRoot.useFrame`, props rozszerzone | 60-70, 165-252 |
| `docs/AVATAR_REDESIGN_PLAN.md` | Ten plik | — |
| `tests/unit/test_ui_config_schema.py` | Walidacja nowych pól | nowy |

### Reused (nie pisać od zera)

- `EMOTION_BODY` per emocja → `AvatarCanvas.tsx:40-58` — analogiczna struktura dla `STATE_POSE`
- `blendRecords` + `easeOutCubic` → `frontend/src/emotionBlend.ts` — wzorzec interpolacji
- `IDLE_SWAY_SPRING=9` damping → `AvatarCanvas.tsx:60` — wzór dla `STATE_POSE_SPRING=4.5` i `LOOK_AT_SPRING=6`
- `vrm.lookAt` z @pixiv/three-vrm 3.3.1 — już w deps
- `idleBonesRef.current` (chest/spine/head/neck) → dodać tylko `shoulders: [leftUpperArm, rightUpperArm]`
- `clock.elapsedTime` + delta z `useFrame` (R3F)
- `visualState` w `App.tsx:219` — już istnieje, tylko propagacja do AvatarCanvas

---

## 8. Weryfikacja

### Smoke manualny (krok po kroku)

```bash
# Backend
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload

# Frontend (rebuild po zmianach TSX)
cd frontend
npm run build
npm run electron
```

1. **Skala**: okno wystartuje ~133×200 px.
2. **Breathing**: obserwuj 30 s w idle → widoczna pulsacja klatki.
3. **State poses**: PTT (Caps Lock) → przejście listening/thinking/speaking, każdy z osobną pozą głowy.
4. **LookAt**: ruch myszki → oczy podążają. Bez ruchu 3 s → saccade.
5. **Emocje**: zapytaj „opowiedz dowcip" (happy) i „przegrałem" (sad/disappointed) — porównaj intensywność z poprzednią wersją.
6. **Hot-reload**: `PUT /api/v1/config` z różnymi wartościami `ui.avatar_*` — sprawdź że zmiany aplikują się bez restartu.

### Testy automatyczne

```bash
pytest tests/unit/test_ui_config_schema.py -v   # walidacja nowych pól UIConfig
pytest tests/ -q                                 # regresja pełna
```

Brak testów renderowania Three.js — to integration territory, polegamy na smoke. Można rozważyć Playwright e2e dla overlay'a w przyszłości.

---

## 9. Out of scope (świadomie pominięte)

- **Hand gestures / pointing / waving** — wymaga IK solvera (np. `three-ik`) lub zestawu keyframe'ów `.vrma`. Phase 2.
- **Łzy / rumieniec jako shader** — zostają obecne blendshapes (jeśli model VRM je ma, intensity boost zrobi swoje).
- **Custom animacje VRM (.vrma)** — `VRMAnimationLoader` nie jest w deps. Wszystko procedurally w `useFrame`.
- **Avatar w trybie przeglądarki (`!isElectron`)** — `overlay_scale` uwzględnia, ale priorytet to Electron overlay; widok przeglądarkowy zostaje jako dziś.
- **Per-`visual_state` expression overlays** (np. „concentration" przy thinking jako extra blendshape) — można w iteracji 2, na razie tylko bone poses + intensity bonus.
- **Animacja palca na brodzie przy `thinking`** — wymaga `leftHand` IK lub gotowej animacji. Pomijane.

---

## 10. Roadmap

- **Faza 1 (ten dokument)**: skala 1/3, breathing, state poses, look-at, intensity boost. Cel: lekki widget z większym „życiem".
- **Faza 2 (osobny plan)**: hand gestures + VRMA loader + `concentration`/`agreement` reactions na eventy backendu (`agent_activity`, `thread_resumed`, `daily_check_complete`).
- **Faza 3 (długoterminowo)**: voice-driven viseme detection (zamiast prostego RMS lip-sync), prosodic head bobs synchroniczne z TTS.
