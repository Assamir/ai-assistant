const { app, BrowserWindow, Tray, Menu, nativeImage, globalShortcut } = require("electron");
const path = require("path");

let mainWindow = null;
let tray = null;
let allowQuit = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 520,
    height: 720,
    show: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
    },
  });
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
  } catch (_) {}
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("window-all-closed", () => {
  if (!tray) {
    app.quit();
  }
});
