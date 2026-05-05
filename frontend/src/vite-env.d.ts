/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL?: string;
  readonly VITE_VRM_URL?: string;
  readonly VITE_API_BASE_URL?: string;
}

interface Window {
  assystent?: {
    version: string;
    wsUrl?: string;
    vrmUrl?: string;
    apiUrl?: string;
  };
}
