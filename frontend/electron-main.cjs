const { app, BrowserWindow, Tray, Menu, nativeImage, globalShortcut, ipcMain, session } = require("electron");

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
const DEFAULT_W = 520;
const DEFAULT_H = 720;

function loadWindowState() {
  try {
    const s = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
    if (
      typeof s.width === "number" && s.width > 100 &&
      typeof s.height === "number" && s.height > 100
    ) {
      return s;
    }
  } catch (_) { /* first run or corrupt — use defaults */ }
  return { width: DEFAULT_W, height: DEFAULT_H };
}

function saveWindowState(bounds) {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(bounds), "utf8");
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
  const saved = loadWindowState();
  mainWindow = new BrowserWindow({
    width: saved.width || DEFAULT_W,
    height: saved.height || DEFAULT_H,
    x: typeof saved.x === "number" ? saved.x : undefined,
    y: typeof saved.y === "number" ? saved.y : undefined,
    show: true,
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
        saveWindowState(mainWindow.getBounds());
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
