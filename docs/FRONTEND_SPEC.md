# DOK-12: FRONTEND_SPEC.md — Specyfikacja Frontendu (Electron + React + Three.js)

> **Status:** v1.0 — 2026-04-30
> **Materiały źródłowe:** PRD_02_FUNCTIONAL.md (§1 Awatar, §8 UI), PRD_05_UX_BEHAVIOR.md (§6 Audio UX), DOK-04 api-plan.md, DOK-06 EMOTION_SPEC.md, DECISIONS_LOG.md (DOK-12)

---

## 1. Architektura Electron

### 1.1 Process model

```
Main Process (main.js)
├── Avatar Window (renderer) — frameless, transparent, AOT
├── Config Window (renderer) — standard frame, resizable
├── System Tray (tray.js)
├── IPC handlers (globalny hotkey, window management)
└── preload.js — bezpieczny bridge contextIsolation

Renderer Process (Avatar Window)
├── React App (Three.js canvas + overlays)
├── WebSocket Client → ws://localhost:8000/ws
└── REST API Client → http://localhost:8000

Renderer Process (Config Window)
├── React App (settings panels)
└── REST API Client
```

### 1.2 Window configurations

```javascript
// Avatar window (main.js)
const avatarWindow = new BrowserWindow({
  width: 400, height: 600,
  transparent: true,
  frame: false,
  alwaysOnTop: true,
  resizable: true,
  skipTaskbar: false,
  webPreferences: {
    preload: path.join(__dirname, "preload.js"),
    contextIsolation: true,
    nodeIntegration: false,
  },
});
avatarWindow.setIgnoreMouseEvents(false);  // domyślnie: avatar blokuje klik
avatarWindow.setVisibleOnAllWorkspaces(true);

// Config window (osobne BrowserWindow — DECISIONS_LOG DOK-12 #2)
const configWindow = new BrowserWindow({
  width: 800, height: 600,
  minWidth: 600, minHeight: 400,
  frame: true,
  alwaysOnTop: false,
  skipTaskbar: false,
  parent: avatarWindow,
  show: false,   // ukryte do jawnego otwarcia
  webPreferences: {
    preload: path.join(__dirname, "preload.js"),
    contextIsolation: true,
    nodeIntegration: false,
  },
});
```

### 1.3 Click-through toggle (DECISIONS_LOG DOK-12 #1)

Obsługiwany przez OBOJE: komendę głosową I UI button.

```javascript
// IPC handler (main.js)
ipcMain.on("window:click_through_on", () => {
  avatarWindow.setIgnoreMouseEvents(true, { forward: true });
  // forward: true = kliknięcia trafiają do okna pod spodem (gra)
});
ipcMain.on("window:click_through_off", () => {
  avatarWindow.setIgnoreMouseEvents(false);
});
```

### 1.4 IPC Events

| Event | Kierunek | Payload |
|-------|---------|---------|
| `window:click_through_on/off` | renderer → main | — |
| `config:open` | renderer → main | — |
| `config:save` | renderer → main | `{key, value}` |
| `avatar:reload_vrm` | main → renderer | `{filepath}` |
| `tray:action` | main → renderer | `{action}` |
| `window:set_bounds` | renderer → main | `{x, y, w, h}` |

---

## 2. System Tray

```javascript
// tray.js
const tray = new Tray(path.join(__dirname, "../assets/tray-icon.png"));

const buildMenu = (health) => Menu.buildFromTemplate([
  { label: health === "healthy" ? "✅ Asystent aktywny" : "⚠️ Zdegradowany",
    enabled: false },
  { type: "separator" },
  { label: "Pokaż awatar", click: () => avatarWindow.show() },
  { label: "Pokaż ustawienia", click: () => configWindow.show() },
  { type: "separator" },
  { label: "Otwórz logi", click: () => shell.openPath(logsPath) },
  { label: "Restart backendu", click: () => restartBackend() },
  { type: "separator" },
  { label: "Zakończ", click: () => app.quit() },
]);

// Kolor ikony: green (healthy) / yellow (degraded) / red (error)
function updateTrayIcon(health: string) {
  const icons = { healthy: "tray-green.png", degraded: "tray-yellow.png", error: "tray-red.png" };
  tray.setImage(path.join(__dirname, "../assets", icons[health] || icons.error));
}
```

---

## 3. Globalne Hotkeys

```javascript
// main.js
const { globalShortcut } = require("electron");

app.whenReady().then(() => {
  const registered = globalShortcut.register("Ctrl+Shift+A", () => {
    avatarWindow.isVisible() ? avatarWindow.hide() : avatarWindow.show();
  });
  if (!registered) {
    // Wyślij error event do renderera
    avatarWindow.webContents.send("hotkey:conflict", "Ctrl+Shift+A");
  }

  globalShortcut.register("Ctrl+Shift+S", () => {
    configWindow.show();
    configWindow.focus();
  });
});

app.on("will-quit", () => globalShortcut.unregisterAll());
```

PTT key: zarządzany przez **backend** (pynput) — frontend tylko wyświetla UI stan (listening indicator przez WebSocket event).

---

## 4. Struktura Komponentów React

```
frontend/src/
├── App.jsx                          # Router: avatar | config | wizard
├── components/
│   ├── Avatar3D/
│   │   ├── Avatar3D.jsx             # Three.js scene, render loop
│   │   ├── VRMLoader.js             # ładowanie + capabilities scan
│   │   ├── EmotionController.js     # apply emotion z emotions.json
│   │   ├── LipSync.js               # RMS → aa blendshape
│   │   ├── IdleAnimations.js        # oddychanie, mruganie, sway
│   │   └── AuraShader.js            # PointLight + material aura
│   ├── ConfigPanel/
│   │   ├── ConfigPanel.jsx          # tabs navigation
│   │   ├── AudioSettings.jsx        # mic, speakers, volume sliders
│   │   ├── AvatarSettings.jsx       # VRM file picker, scale, opacity
│   │   ├── PersonaSelector.jsx      # dropdown + preview
│   │   └── ObserverSettings.jsx     # interval, per-game toggles
│   ├── StatusOverlay/
│   │   ├── StatusOverlay.jsx        # debug info, state indicator
│   │   └── TextOverlay.jsx          # tryb cichy: tekst obok awatara
│   └── SetupWizard/
│       └── SetupWizard.jsx          # 6 kroków first-run
├── hooks/
│   ├── useWebSocket.js              # połączenie + reconnect
│   ├── useEmotion.js                # state machine emocji
│   ├── useAudioPlayer.js            # AudioContext + queue + duck
│   └── useConfig.js                 # GET/PUT /config
├── utils/
│   ├── api.js                       # REST client (fetch wrapper)
│   ├── audio.js                     # PCM → AudioBuffer
│   └── constants.js                 # BACKEND_URL, WS_URL, etc.
└── electron/
    ├── main.js
    ├── preload.js
    └── tray.js
```

---

## 5. Avatar3D — Three.js Setup

```javascript
// Avatar3D.jsx
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader";
import { VRMLoaderPlugin } from "@pixiv/three-vrm";

export function Avatar3D({ vrmPath, emotionsConfig }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(canvas.clientWidth, canvas.clientHeight);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(35, canvas.clientWidth / canvas.clientHeight, 0.1, 100);
    camera.position.set(0, 1.4, 2.5);  // head & shoulders framing

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(1, 2, 2);
    scene.add(dirLight);
    const rimLight = new THREE.DirectionalLight(0xa0c8ff, 0.3);
    rimLight.position.set(-2, 0, -2);
    scene.add(rimLight);

    let vrm, animationId;
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    loader.load(vrmPath, (gltf) => {
      vrm = gltf.userData.vrm;
      scene.add(vrm.scene);
      initEmotionController(vrm, emotionsConfig);
      initLipSync(vrm);
      initIdleAnimations(vrm);
    });

    const clock = new THREE.Clock();
    function animate() {
      animationId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      vrm?.update(delta);
      renderer.render(scene, camera);
    }
    animate();

    return () => {
      cancelAnimationFrame(animationId);
      renderer.dispose();
    };
  }, [vrmPath]);

  return <canvas ref={canvasRef} style={{ width: "100%", height: "100%", background: "transparent" }} />;
}
```

### 5.1 VRM Loading + Capabilities

```javascript
// VRMLoader.js
export async function loadVRM(path) {
  const loader = new GLTFLoader();
  loader.register((parser) => new VRMLoaderPlugin(parser));
  const gltf = await loader.loadAsync(path);
  const vrm = gltf.userData.vrm;
  const capabilities = scanCapabilities(vrm);
  return { vrm, capabilities };
}

function scanCapabilities(vrm) {
  const em = vrm.expressionManager;
  const SHAPES = ["happy","sad","angry","surprised","relaxed","neutral",
                  "aa","ih","ou","ee","oh","blinkLeft","blinkRight","lookUp","lookDown"];
  const blendshapes = {};
  for (const name of SHAPES) {
    blendshapes[name] = em?.getExpression(name) !== null;
  }
  const humanoid = vrm.humanoid;
  return {
    blendshapes,
    hasFullHumanoid: humanoid?.getNormalizedBoneNode("leftUpperArm") !== null,
  };
}
```

---

## 6. Lip-Sync Algorithm

```javascript
// LipSync.js — Web Audio API
export class LipSync {
  constructor(vrm, capabilities) {
    this._vrm = vrm;
    this._hasAA = capabilities.blendshapes["aa"];
    this._analyser = null;
    this._smoothed = 0;
    this.SMOOTHING = 0.4;  // lowpass alpha
    this.GAIN = 4.0;
  }

  attachToAudioContext(audioCtx, sourceNode) {
    this._analyser = audioCtx.createAnalyser();
    this._analyser.fftSize = 1024;
    this._analyser.smoothingTimeConstant = 0;
    sourceNode.connect(this._analyser);
  }

  update() {
    if (!this._analyser || !this._hasAA) return;
    const data = new Uint8Array(this._analyser.fftSize);
    this._analyser.getByteTimeDomainData(data);

    // RMS
    let sum = 0;
    for (const s of data) sum += ((s - 128) / 128) ** 2;
    const rms = Math.sqrt(sum / data.length);
    const normalized = Math.min(1, rms * this.GAIN);

    // Exponential smoothing (lowpass)
    this._smoothed = this._smoothed * (1 - this.SMOOTHING) + normalized * this.SMOOTHING;
    this._vrm.expressionManager?.setValue("aa", this._smoothed);
  }
}
```

---

## 7. Emotion System Frontend

```javascript
// useEmotion.js
import { useState, useCallback, useRef } from "react";
import emotionsConfig from "../../config/emotions.json";

export function useEmotion(vrm, capabilities) {
  const [current, setCurrent] = useState("neutral");
  const timerRef = useRef(null);

  const transitionTo = useCallback((name) => {
    const config = emotionsConfig.emotions[name] || emotionsConfig.emotions.neutral;
    clearTimeout(timerRef.current);

    // Layer 1: Blendshapes
    Object.entries(config.blendshapes).forEach(([shape, value]) => {
      if (capabilities?.blendshapes[shape]) {
        vrm.expressionManager?.setValue(shape, value);
      }
    });

    // Layer 2: Aura
    setAura(config.aura);

    // Layer 3: Body
    if (capabilities?.hasFullHumanoid) {
      applyBodyAnimation(vrm, config.body);
    }

    setCurrent(name);

    // Auto-fade po max_ms
    timerRef.current = setTimeout(() => transitionTo("neutral"),
      config.timing.max_ms);
  }, [vrm, capabilities]);

  return { currentEmotion: current, transitionTo };
}
```

---

## 8. Audio Player

```javascript
// useAudioPlayer.js
export function useAudioPlayer() {
  const ctxRef = useRef(null);
  const gainRef = useRef(null);
  const queueRef = useRef([]);

  function getCtx() {
    if (!ctxRef.current) {
      ctxRef.current = new AudioContext({ sampleRate: 22050 });
      gainRef.current = ctxRef.current.createGain();
      gainRef.current.connect(ctxRef.current.destination);
    }
    return ctxRef.current;
  }

  // Dodaj PCM chunk do kolejki
  function enqueuePCM(pcmBase64) {
    const ctx = getCtx();
    const raw = atob(pcmBase64);
    const buffer = ctx.createBuffer(1, raw.length / 2, 22050);
    const data = buffer.getChannelData(0);
    const view = new DataView(new ArrayBuffer(raw.length));
    for (let i = 0; i < raw.length; i++) view.setUint8(i, raw.charCodeAt(i));
    for (let i = 0; i < data.length; i++) {
      data[i] = view.getInt16(i * 2, true) / 32768;
    }
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(gainRef.current);
    src.start();
    queueRef.current.push(src);
  }

  // Duck: volume → 0 w 200ms (PTT)
  function duck() {
    const gain = gainRef.current;
    const ctx = getCtx();
    gain.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.2);
    queueRef.current.forEach(s => { try { s.stop(); } catch {} });
    queueRef.current = [];
  }

  function unduck() {
    gainRef.current?.gain.linearRampToValueAtTime(1, getCtx().currentTime + 0.1);
  }

  return { enqueuePCM, duck, unduck, audioCtx: ctxRef };
}
```

---

## 9. WebSocket Client

```javascript
// useWebSocket.js
import { useEffect, useRef, useCallback } from "react";

const WS_URL = "ws://localhost:8000/ws";
const BACKOFF = [1000, 2000, 4000, 8000, 16000, 30000];

export function useWebSocket({ onEmotion, onAudioChunk, onSystemState, onTextOverlay }) {
  const wsRef = useRef(null);
  const attemptRef = useRef(0);

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      ws.send(JSON.stringify({ type: "frontend_ready" }));
    };

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data);
      switch (msg.type) {
        case "emotion":        onEmotion?.(msg.payload.emotion); break;
        case "audio_stream":   onAudioChunk?.(msg.payload.chunk_base64); break;
        case "system_state":   onSystemState?.(msg.payload.state); break;
        case "text_overlay":   onTextOverlay?.(msg.payload.text); break;
        case "ping":           ws.send(JSON.stringify({ type: "pong" })); break;
      }
    };

    ws.onclose = () => {
      const delay = BACKOFF[Math.min(attemptRef.current, BACKOFF.length - 1)];
      attemptRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);

  const send = useCallback((type, payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload, timestamp: Date.now() }));
    }
  }, []);

  return { send };
}
```

---

## 10. Config Panel UI

### 10.1 Sekcje

| Zakładka | Zawartość |
|---------|-----------|
| Audio | Wybór mikrofonu, głośników, suwak głośności TTS, PTT key selector |
| Awatar | File picker `.vrm`, suwak scale (0.5–2.0), opacity, pozycja |
| Persona | Dropdown wyboru persony, podgląd tekstu |
| Obserwator | Interwał (suwak 5–300s), toggle per game |
| Hotkeys | Wyświetlenie aktywnych, info o konfliktach |
| Zaawansowane | Debug mode, model paths, logs folder, wersja |
| Status | VRAM, wątki, stan circuit breakers, observer state |

### 10.2 Save flow

```javascript
// useConfig.js
export function useConfig() {
  const [config, setConfig] = useState({});
  const debounceRef = useRef(null);

  const updateConfig = useCallback((key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      await fetch("http://localhost:8000/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: value }),
      });
    }, 500);  // debounce 500ms
  }, []);

  return { config, updateConfig };
}
```

---

## 11. Setup Wizard (First-Run)

6 kroków z PRD_05:

```
Step 1: Welcome
  → Informacja o projekcie, wymaganiach
  
Step 2: Check dependencies
  → GET /health → sprawdź: LM Studio online?, Python deps OK?
  → Pokazuj checklistę: ✅/❌ per komponent
  → "Napraw" button = link do ENV_SETUP.md
  
Step 3: Audio devices
  → GET /config → lista urządzeń audio
  → Wybór mikrofonu + test (record 3s → transcript)
  → Wybór głośników + test (TTS "Test audio")
  
Step 4: Avatar selection
  → Default VRM gotowy (dostarczony z aplikacją)
  → "Wybierz własny" = dialog.showOpenDialog(.vrm filter)
  
Step 5: Persona selection
  → Lista dostępnych person (default, komentator, ...)
  → Radio select + podgląd opisu
  
Step 6: Voice test (czeka na modele — DECISIONS_LOG DOK-12 #3)
  → "Powiedz coś" → PTT → STT → LLM → TTS
  → Background download progress jeśli modele jeszcze się pobierają
  → Ten krok jest BLOCKED dopóki STT/TTS nie pobrane

Marker: PUT /config {"setup_complete": true} → plik config/setup_complete.flag
```

---

## 12. Drag & Drop Avatar Position

```javascript
// Avatar3D.jsx — drag handler
const [dragging, setDragging] = useState(false);
const [offset, setOffset] = useState({ x: 0, y: 0 });

const onMouseDown = (e) => {
  if (e.button !== 0) return;
  setDragging(true);
  setOffset({ x: e.screenX, y: e.screenY });
};

const onMouseMove = (e) => {
  if (!dragging) return;
  const dx = e.screenX - offset.x;
  const dy = e.screenY - offset.y;
  window.electronAPI.moveWindow(dx, dy);  // IPC → setBounds
  setOffset({ x: e.screenX, y: e.screenY });
};
```

Pozycja zapisywana do config: `PUT /config {"ui.avatar_position": {x, y}}`.

---

## 13. Always-on-Top + Click-through State

```javascript
// Persystencja w system_state (backend)
// Frontend zarządza przez WebSocket IPC:
const toggleClickThrough = (enable) => {
  ws.send("click_through_" + (enable ? "on" : "off"), {});
  // Backend odbiera → IPC do main process
};
```

Domyślnie: AOT on, click-through OFF.

---

## 14. Build & Distribution

```json
// package.json (skrócony)
{
  "scripts": {
    "start": "electron .",
    "build": "electron-builder --win"
  },
  "build": {
    "appId": "com.antigravity.assystent",
    "productName": "Assystent",
    "win": {
      "target": "nsis",
      "icon": "assets/icon.ico"
    },
    "nsis": {
      "oneClick": false,
      "allowToChangeInstallationDirectory": true
    },
    "files": ["src/**", "assets/**", "!**/*.map"]
  }
}
```

- Code signing: opcjonalne (solo-dev, lokalna instalacja)
- Auto-update: WYŁĄCZONE (manual updates z PRD)
- Installer: NSIS — `.exe` do dystrybucji

---

## 15. Performance Targets

| Metryka | Target |
|---------|--------|
| GPU usage (rendering) | < 2% |
| Memory (renderer process) | < 300 MB |
| FPS (avatar visible) | 60 fps |
| FPS (minimized) | 30 fps (power saving) |
| Startup time (frontend) | < 5s od Electron launch |

---

*Dokument: DOK-12 FRONTEND_SPEC.md v1.0 — 2026-04-30*
*Następny: DOK-13 TEST_PLAN.md*
