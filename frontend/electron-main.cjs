const { app, BrowserWindow, Tray, Menu, nativeImage, globalShortcut, ipcMain, session, screen } = require("electron");

/** Bez tego Chromium w Electron często zatrzymuje `AudioContext` / TTS dopóki użytkownik nie „obudzi" audio gestem. */
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");

const path = require("path");
const fs = require("fs");
const zlib = require("zlib");
const { spawn } = require("child_process");

let mainWindow = null;
let configWindow = null;
let tray = null;
let allowQuit = false;
let currentHealth = "unknown";
/** Proces uvicorn przy instalatorze „Komplet"; null w pakiecie tylko-klient. */
let bundledBackendProc = null;

// ---------------------------------------------------------------------------
// Window state persistence — saves/restores {x, y, width, height}
// ---------------------------------------------------------------------------

const STATE_FILE = path.join(app.getPath("userData"), "window-state.json");
const DEFAULT_W = 400;
const DEFAULT_H = 600;
const DEFAULT_OVERLAY_SCALE = 0.333;
let currentOverlayScale = DEFAULT_OVERLAY_SCALE;

function parseOverlayScale(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n)) return DEFAULT_OVERLAY_SCALE;
  return Math.min(1.5, Math.max(0.2, n));
}

function scaledSize(width, height, scale) {
  return {
    width: Math.max(80, Math.round(width * scale)),
    height: Math.max(120, Math.round(height * scale)),
  };
}

function loadWindowState() {
  try {
    const s = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
    const out = {
      x: typeof s.x === "number" ? s.x : undefined,
      y: typeof s.y === "number" ? s.y : undefined,
      logicalWidth: typeof s.logicalWidth === "number" && s.logicalWidth > 100 ? s.logicalWidth : DEFAULT_W,
      logicalHeight: typeof s.logicalHeight === "number" && s.logicalHeight > 100 ? s.logicalHeight : DEFAULT_H,
    };
    if (typeof s.width === "number" && s.width > 100) {
      out.logicalWidth = Math.round(s.width / currentOverlayScale);
    }
    if (typeof s.height === "number" && s.height > 100) {
      out.logicalHeight = Math.round(s.height / currentOverlayScale);
    }
    return out;
  } catch (_) { /* first run or corrupt — use defaults */ }
  return { logicalWidth: DEFAULT_W, logicalHeight: DEFAULT_H };
}

function saveWindowState(bounds, scale = currentOverlayScale) {
  try {
    const logicalWidth = Math.round(bounds.width / scale);
    const logicalHeight = Math.round(bounds.height / scale);
    fs.writeFileSync(
      STATE_FILE,
      JSON.stringify({ ...bounds, logicalWidth, logicalHeight }),
      "utf8",
    );
  } catch (_) { /* ignore — non-critical */ }
}

// ---------------------------------------------------------------------------
// Tray icon PNG generation (no external deps — pure Node.js zlib + CRC32)
// ---------------------------------------------------------------------------

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc & 1) ? (0xEDB88320 ^ (crc >>> 1)) : (crc >>> 1);
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function pngChunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBytes = Buffer.from(type, "ascii");
  const crcVal = crc32(Buffer.concat([typeBytes, data]));
  const crcBuf = Buffer.alloc(4);
  crcBuf.writeUInt32BE(crcVal);
  return Buffer.concat([len, typeBytes, data, crcBuf]);
}

function makeSolidPng(size, r, g, b) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(size, 0);
  ihdrData.writeUInt32BE(size, 4);
  ihdrData[8] = 8; // bit depth
  ihdrData[9] = 2; // color type RGB
  // compression, filter, interlace = 0

  const row = Buffer.alloc(1 + size * 3);
  row[0] = 0; // filter: none
  for (let x = 0; x < size; x++) {
    row[1 + x * 3] = r;
    row[1 + x * 3 + 1] = g;
    row[1 + x * 3 + 2] = b;
  }
  const rows = Array.from({ length: size }, () => row);
  const compressed = zlib.deflateSync(Buffer.concat(rows));

  return Buffer.concat([
    sig,
    pngChunk("IHDR", ihdrData),
    pngChunk("IDAT", compressed),
    pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

const HEALTH_RGB = {
  ok:       [34, 197,  94],   // green
  healthy:  [34, 197,  94],
  degraded: [234, 179,   8],  // amber
  error:    [239,  68,  68],  // red
  unknown:  [107, 114, 128],  // gray
};

function buildTrayIcon(health) {
  const [r, g, b] = HEALTH_RGB[health] || HEALTH_RGB.unknown;
  try {
    return nativeImage.createFromBuffer(makeSolidPng(16, r, g, b));
  } catch (_) {
    return nativeImage.createEmpty();
  }
}

function createConfigWindow() {
  if (configWindow && !configWindow.isDestroyed()) {
    configWindow.show();
    configWindow.focus();
    return;
  }
  configWindow = new BrowserWindow({
    width: 680,
    height: 780,
    title: "Assystent — Konfiguracja",
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      backgroundThrottling: false,
    },
  });
  const devUrl = process.env.VITE_DEV_SERVER_URL || "http://localhost:5173";
  if (process.env.ASSYSTENT_DEV === "1") {
    configWindow.loadURL(devUrl + "#config");
  } else {
    configWindow.loadFile(path.join(__dirname, "dist", "index.html"), { hash: "config" });
  }
  configWindow.on("closed", () => {
    configWindow = null;
  });
}

function buildTrayMenu() {
  const h = currentHealth;
  const statusLabel =
    h === "ok" || h === "healthy" ? "Asystent aktywny" :
    h === "degraded"              ? "⚠ Zdegradowany"   :
                                    "Rozłączony";
  return Menu.buildFromTemplate([
    { label: statusLabel, enabled: false },
    { type: "separator" },
    {
      label: "Pokaż",
      click: () => { if (mainWindow) { mainWindow.show(); mainWindow.focus(); } },
    },
    {
      label: "Konfiguracja",
      click: () => createConfigWindow(),
    },
    { type: "separator" },
    { label: "Zakończ", click: () => { allowQuit = true; app.quit(); } },
  ]);
}

function updateTrayHealth(health) {
  currentHealth = health;
  if (!tray) return;
  tray.setImage(buildTrayIcon(health));
  tray.setToolTip(`Assystent — ${health}`);
  tray.setContextMenu(buildTrayMenu());
}

// ---------------------------------------------------------------------------

function getBundledPythonAppRoot() {
  try {
    const base = process.resourcesPath;
    if (!base) {
      return null;
    }
    const p = path.join(base, "bundled", "python-app");
    if (fs.existsSync(path.join(p, "backend", "main.py"))) {
      return p;
    }
  } catch (_) {
    /* ignore */
  }
  return null;
}

function spawnBundledBackend() {
  const root = getBundledPythonAppRoot();
  if (!root || process.env.ASSYSTENT_NO_AUTO_BACKEND === "1") {
    return;
  }
  const args = ["-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"];
  let cmd = process.env.ASSYSTENT_PYTHON_EXE?.trim();
  if (!cmd && process.platform === "win32") {
    bundledBackendProc = spawn("python", args, {
      cwd: root,
      stdio: "ignore",
      windowsHide: true,
      shell: false,
    });
  } else if (!cmd) {
    bundledBackendProc = spawn("python3", args, {
      cwd: root,
      stdio: "ignore",
      windowsHide: true,
      shell: false,
    });
  } else {
    bundledBackendProc = spawn(cmd, args, {
      cwd: root,
      stdio: "ignore",
      windowsHide: true,
      shell: false,
    });
  }
  bundledBackendProc.on("error", () => {
    bundledBackendProc = null;
  });
  bundledBackendProc.on("exit", (code, signal) => {
    if (code !== 0 && code != null && process.env.ASSYSTENT_DEV !== "1") {
      console.warn("Bundled backend exited:", code, signal);
    }
    bundledBackendProc = null;
  });
}

function stopBundledBackend() {
  const p = bundledBackendProc;
  if (!p || p.killed) {
    bundledBackendProc = null;
    return;
  }
  try {
    p.kill();
  } catch (_) {
    /* ignore */
  }
  if (process.platform === "win32" && p.pid) {
    try {
      spawn("taskkill", ["/pid", String(p.pid), "/T", "/F"], {
        stdio: "ignore",
        windowsHide: true,
        shell: true,
      });
    } catch (_) {
      /* ignore */
    }
  }
  bundledBackendProc = null;
}

function createWindow() {
  currentOverlayScale = parseOverlayScale(
    process.env.ASSYSTENT_OVERLAY_SCALE || process.env.VITE_OVERLAY_SCALE || DEFAULT_OVERLAY_SCALE,
  );
  const saved = loadWindowState();
  const initialSize = scaledSize(saved.logicalWidth || DEFAULT_W, saved.logicalHeight || DEFAULT_H, currentOverlayScale);
  mainWindow = new BrowserWindow({
    width: initialSize.width,
    height: initialSize.height,
    x: typeof saved.x === "number" ? saved.x : undefined,
    y: typeof saved.y === "number" ? saved.y : undefined,
    show: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      backgroundThrottling: false,
    },
  });

  let _saveTimer = null;
  const scheduleSave = () => {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isMinimized()) {
        saveWindowState(mainWindow.getBounds(), currentOverlayScale);
      }
    }, 500);
  };
  mainWindow.on("moved", scheduleSave);
  mainWindow.on("resized", scheduleSave);
  try {
    mainWindow.webContents.setAudioMuted(false);
  } catch (_) {
    /* ignore */
  }
  const devUrl = process.env.VITE_DEV_SERVER_URL || "http://localhost:5173";
  if (process.env.ASSYSTENT_DEV === "1") {
    mainWindow.loadURL(devUrl);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "dist", "index.html"));
  }

  mainWindow.on("close", (ev) => {
    if (tray && !allowQuit) {
      ev.preventDefault();
      mainWindow.hide();
    }
  });

  if (!tray) {
    try {
      tray = new Tray(buildTrayIcon("unknown"));
      tray.setContextMenu(buildTrayMenu());
      tray.on("click", () => {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      });
    } catch (_) {
      tray = null;
    }
  }
}

app.on("before-quit", () => {
  allowQuit = true;
});

app.whenReady().then(() => {
  try {
    session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
      if (permission === "media") {
        callback(true);
        return;
      }
      callback(false);
    });
  } catch (_) {
    /* ignore */
  }
  spawnBundledBackend();
  createWindow();

  ipcMain.on("click_through", (_event, enabled) => {
    if (mainWindow) {
      mainWindow.setIgnoreMouseEvents(!!enabled, { forward: true });
    }
  });

  ipcMain.on("open_config_window", () => {
    createConfigWindow();
  });

  ipcMain.on("tray_health", (_event, health) => {
    updateTrayHealth(typeof health === "string" ? health : "unknown");
  });

  ipcMain.handle("get-displays", () => {
    return screen.getAllDisplays().map((d) => ({
      id: d.id,
      label: `${d.isPrimary ? "Główny — " : ""}${d.bounds.width}×${d.bounds.height} (${d.bounds.x}, ${d.bounds.y})`,
      bounds: d.bounds,
      isPrimary: d.isPrimary,
    }));
  });

  ipcMain.on("set-display", (_event, displayId) => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const displays = screen.getAllDisplays();
    const target = displays.find((d) => d.id === displayId) || displays.find((d) => d.isPrimary) || displays[0];
    if (!target) return;
    const { width, height } = mainWindow.getBounds();
    mainWindow.setBounds({ x: target.bounds.x, y: target.bounds.y, width, height });
  });

  ipcMain.on("set-overlay-scale", (_event, nextScaleRaw) => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const prevScale = currentOverlayScale;
    const nextScale = parseOverlayScale(nextScaleRaw);
    if (Math.abs(nextScale - prevScale) < 1e-4) return;
    const b = mainWindow.getBounds();
    const logicalWidth = Math.max(DEFAULT_W, Math.round(b.width / prevScale));
    const logicalHeight = Math.max(DEFAULT_H, Math.round(b.height / prevScale));
    const next = scaledSize(logicalWidth, logicalHeight, nextScale);
    currentOverlayScale = nextScale;
    mainWindow.setBounds({ ...b, width: next.width, height: next.height });
    saveWindowState(mainWindow.getBounds(), currentOverlayScale);
  });

  try {
    globalShortcut.register("CommandOrControl+Shift+A", () => {
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    });
    globalShortcut.register("CommandOrControl+Shift+S", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    });
  } catch (_) {
    /* ignore */
  }
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  stopBundledBackend();
});

app.on("window-all-closed", () => {
  if (!tray) {
    app.quit();
  }
});
