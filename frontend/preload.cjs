const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("assystent", {
  version: "0.1.0-skeleton",
});
