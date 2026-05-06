const { app, BrowserWindow, Tray, Menu, nativeImage, globalShortcut, session } = require("electron");

/** Bez tego Chromium w Electron często zatrzymuje `AudioContext` / TTS dopóki użytkownik nie „obudzi” audio gestem. */
app.commandLine.appendSwitch("autoplay-policy", "no-user-gesture-required");

const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");

let mainWindow = null;
let tray = null;
let allowQuit = false;
/** Proces uvicorn przy instalatorze „Komplet”; null w pakiecie tylko-klient. */
let bundledBackendProc = null;

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
  mainWindow = new BrowserWindow({
    width: 520,
    height: 720,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      backgroundThrottling: false,
    },
  });
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
      const icon = nativeImage.createEmpty();
      tray = new Tray(icon);
      tray.setToolTip("Assystent");
      tray.setContextMenu(
        Menu.buildFromTemplate([
          {
            label: "Pokaż",
            click: () => {
              mainWindow.show();
              mainWindow.focus();
            },
          },
          { type: "separator" },
          { label: "Zakończ", click: () => { allowQuit = true; app.quit(); } },
        ]),
      );
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
  try {
    globalShortcut.register("CommandOrControl+Shift+A", () => {
      const w = BrowserWindow.getFocusedWindow() || mainWindow;
      if (w && !w.webContents.isDevToolsOpened()) {
        w.webContents.openDevTools({ mode: "detach" });
      }
    });
    globalShortcut.register("CommandOrControl+Shift+S", () => {
      const w = BrowserWindow.getFocusedWindow() || mainWindow;
      if (w) {
        w.show();
        w.focus();
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
