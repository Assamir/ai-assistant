const { contextBridge } = require("electron");

const wsUrl =
  process.env.ASSYSTENT_WS_URL ||
  process.env.VITE_WS_URL ||
  "ws://127.0.0.1:8000/ws";

const vrmUrl = process.env.ASSYSTENT_VRM_URL || process.env.VITE_VRM_URL || "";

contextBridge.exposeInMainWorld("assystent", {
  version: "0.1.0-skeleton",
  wsUrl,
  vrmUrl,
});
