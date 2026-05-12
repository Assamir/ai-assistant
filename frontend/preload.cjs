const { contextBridge, ipcRenderer } = require("electron");

const wsUrl =
  process.env.ASSYSTENT_WS_URL ||
  process.env.VITE_WS_URL ||
  "ws://127.0.0.1:8000/ws";

const vrmUrl = process.env.ASSYSTENT_VRM_URL || process.env.VITE_VRM_URL || "";

const apiUrl =
  process.env.ASSYSTENT_API_URL || process.env.VITE_API_BASE_URL || "";

const configPutToken =
  process.env.ASSYSTENT_CONFIG_PUT_TOKEN || process.env.VITE_CONFIG_PUT_TOKEN || "";
const overlayScaleRaw = process.env.ASSYSTENT_OVERLAY_SCALE || process.env.VITE_OVERLAY_SCALE || "0.333";
const overlayScale = Number.isFinite(Number(overlayScaleRaw)) ? Number(overlayScaleRaw) : 0.333;

contextBridge.exposeInMainWorld("assystent", {
  version: "0.1.0-skeleton",
  wsUrl,
  vrmUrl,
  apiUrl,
  configPutToken,
  overlayScale,
  setClickThrough: (enabled) => ipcRenderer.send("click_through", enabled),
  setTrayHealth: (health) => ipcRenderer.send("tray_health", health),
  openConfigWindow: () => ipcRenderer.send("open_config_window"),
  getDisplays: () => ipcRenderer.invoke("get-displays"),
  setDisplay: (id) => ipcRenderer.send("set-display", id),
  setOverlayScale: (scale) => ipcRenderer.send("set-overlay-scale", scale),
});
