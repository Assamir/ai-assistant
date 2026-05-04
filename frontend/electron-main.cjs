const { app, BrowserWindow } = require("electron");
const path = require("path");

function createWindow() {
  const win = new BrowserWindow({
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
    win.loadURL(devUrl);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    win.loadFile(path.join(__dirname, "dist", "index.html"));
  }
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
