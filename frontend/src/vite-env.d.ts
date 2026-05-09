/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL?: string;
  readonly VITE_VRM_URL?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_CONFIG_PUT_TOKEN?: string;
}

interface ElectronDisplay {
  id: number;
  label: string;
  bounds: { x: number; y: number; width: number; height: number };
  isPrimary: boolean;
}

interface Window {
  assystent?: {
    version: string;
    wsUrl?: string;
    vrmUrl?: string;
    apiUrl?: string;
    configPutToken?: string;
    setClickThrough?: (enabled: boolean) => void;
    setTrayHealth?: (health: string) => void;
    openConfigWindow?: () => void;
    getDisplays?: () => Promise<ElectronDisplay[]>;
    setDisplay?: (id: number) => void;
  };
}
