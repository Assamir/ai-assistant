import React, { useState } from "react";

export type ConfigTabId = "connection" | "avatar" | "more";

interface ConfigPanelProps {
  tab: ConfigTabId;
  onTab: (t: ConfigTabId) => void;
  wsStatus: string;
  /** Świeci, gdy ostatnio przyszedł WS dot. profilu (liga); baner przy avatarze — przypomnienie na karcie „Połączenie”. */
  profileWsActive?: boolean;
  vrmUrl: string;
  onVrmSave: (url: string) => void;
  apiBaseUrl: string;
  onApiBaseSave: (url: string) => void;
  onFetchStatus: () => Promise<void>;
  statusJson: string | null;
  statusError: string | null;
  busyStatus: boolean;
  ttsVoiceSpeed: string;
  onTtsVoiceSpeedChange: (v: string) => void;
  onApplyTtsSpeed: () => Promise<void>;
  busyConfig: boolean;
  configMessage: string | null;
}

const tabs: { id: ConfigTabId; label: string }[] = [
  { id: "connection", label: "Połączenie" },
  { id: "avatar", label: "Avatar" },
  { id: "more", label: "Więcej" },
];

export function ConfigPanel({
  tab,
  onTab,
  wsStatus,
  profileWsActive = false,
  vrmUrl,
  onVrmSave,
  apiBaseUrl,
  onApiBaseSave,
  onFetchStatus,
  statusJson,
  statusError,
  busyStatus,
  ttsVoiceSpeed,
  onTtsVoiceSpeedChange,
  onApplyTtsSpeed,
  busyConfig,
  configMessage,
}: ConfigPanelProps) {
  const [draftVrm, setDraftVrm] = useState(vrmUrl);
  const [draftApi, setDraftApi] = useState(apiBaseUrl);

  React.useEffect(() => {
    setDraftVrm(vrmUrl);
  }, [vrmUrl]);

  React.useEffect(() => {
    setDraftApi(apiBaseUrl);
  }, [apiBaseUrl]);

  const wsDisplay =
    typeof window !== "undefined" && window.assystent?.wsUrl
      ? window.assystent.wsUrl
      : import.meta.env.VITE_WS_URL || "(domyślny z hosta + :8000/ws)";

  return (
    <section
      style={{
        border: "1px solid #2a2438",
        borderRadius: 10,
        padding: "1rem",
        background: "#141018",
        color: "#e8e4f0",
      }}
    >
      <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onTab(t.id)}
            style={{
              padding: "0.35rem 0.75rem",
              borderRadius: 6,
              border: tab === t.id ? "1px solid #8b7bb8" : "1px solid #3d3550",
              background: tab === t.id ? "#2a2438" : "#1a1525",
              color: "#e8e4f0",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "connection" && (
        <div style={{ fontSize: 14, lineHeight: 1.55 }}>
          <p style={{ margin: "0 0 0.5rem" }}>
            WebSocket: <strong>{wsStatus}</strong>
            {profileWsActive ? (
              <span
                title="Powiadomienie profilu (liga) jest widoczne przy avatarze."
                style={{
                  marginLeft: "0.4rem",
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minWidth: "1.1rem",
                  height: "1.1rem",
                  padding: "0 0.3rem",
                  borderRadius: 4,
                  fontSize: 10,
                  fontWeight: 700,
                  background: "#5c4a26",
                  color: "#ffe6a8",
                  verticalAlign: "middle",
                }}
              >
                Liga
              </span>
            ) : null}
          </p>
          <p style={{ margin: 0, color: "#b8afc8", wordBreak: "break-all" }}>
            <code style={{ fontSize: 12 }}>{wsDisplay}</code>
          </p>
          <p style={{ margin: "0.75rem 0 0", color: "#8a8198", fontSize: 12 }}>
            W Electron: <code>ASSYSTENT_WS_URL</code> lub <code>VITE_WS_URL</code> w preload.
          </p>

          <label htmlFor="api-base" style={{ display: "block", marginTop: "1rem", marginBottom: "0.35rem" }}>
            URL backendu (REST)
          </label>
          <input
            id="api-base"
            type="url"
            value={draftApi}
            onChange={(e) => setDraftApi(e.target.value)}
            placeholder="http://127.0.0.1:8000"
            style={inputStyle}
          />
          <button
            type="button"
            onClick={() => onApiBaseSave(draftApi.trim())}
            style={{ ...btnPrimary, marginTop: "0.5rem" }}
          >
            Zapisz URL API
          </button>
          <p style={{ margin: "0.5rem 0 0", fontSize: 12, color: "#8a8198" }}>
            <code>GET /api/v1/status</code>, <code>PUT /api/v1/config</code>. Klucz <code>assystent.apiBaseUrl</code>.
          </p>
        </div>
      )}

      {tab === "avatar" && (
        <div style={{ fontSize: 14 }}>
          <label htmlFor="vrm-url" style={{ display: "block", marginBottom: "0.35rem" }}>
            URL modelu VRM
          </label>
          <input
            id="vrm-url"
            type="url"
            value={draftVrm}
            onChange={(e) => setDraftVrm(e.target.value)}
            placeholder="https://…/model.vrm"
            style={inputStyle}
          />
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" onClick={() => onVrmSave(draftVrm.trim())} style={btnPrimary}>
              Zapisz
            </button>
            <span style={{ fontSize: 12, color: "#8a8198" }}>
              <code>assystent.vrmUrl</code>
            </span>
          </div>
        </div>
      )}

      {tab === "more" && (
        <div style={{ fontSize: 14, color: "#b8afc8", lineHeight: 1.55 }}>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" onClick={() => void onFetchStatus()} disabled={busyStatus} style={btnPrimary}>
              {busyStatus ? "Ładowanie…" : "Pobierz status"}
            </button>
            <code style={{ fontSize: 12, color: "#8a8198" }}>{apiBaseUrl}/api/v1/status</code>
          </div>
          {statusError && (
            <p style={{ color: "#f0a8a8", fontSize: 13, margin: "0.5rem 0 0" }}>{statusError}</p>
          )}
          {statusJson && (
            <pre
              style={{
                marginTop: "0.75rem",
                padding: "0.6rem",
                background: "#0d0b12",
                borderRadius: 8,
                fontSize: 11,
                maxHeight: 180,
                overflow: "auto",
                border: "1px solid #2a2438",
                color: "#c8c0dc",
              }}
            >
              {statusJson}
            </pre>
          )}

          <p style={{ margin: "1rem 0 0.35rem", color: "#e8e4f0" }}>TTS — prędkość głosu</p>
          <p style={{ margin: 0, fontSize: 12, color: "#8a8198" }}>
            Wymaga zapisanej <code>config/config.yaml</code> w <code>content_root</code>. Gdy backend ma{" "}
            <code>ASSYSTENT_CONFIG_PUT_TOKEN</code>, ustaw ten sam sekret w <code>VITE_CONFIG_PUT_TOKEN</code>, preloadzie
            lub <code>localStorage[&quot;assystent.configPutToken&quot;]</code>.
          </p>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem", alignItems: "center" }}>
            <input
              type="number"
              step="0.05"
              min="0.25"
              max="3"
              value={ttsVoiceSpeed}
              onChange={(e) => onTtsVoiceSpeedChange(e.target.value)}
              style={{ ...inputStyle, maxWidth: 120 }}
            />
            <button type="button" onClick={() => void onApplyTtsSpeed()} disabled={busyConfig} style={btnPrimary}>
              {busyConfig ? "Wysyłanie…" : "Zastosuj"}
            </button>
          </div>
          {configMessage && (
            <p style={{ margin: "0.5rem 0 0", fontSize: 13, color: "#a8e0c8" }}>{configMessage}</p>
          )}
        </div>
      )}
    </section>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "0.5rem 0.65rem",
  borderRadius: 6,
  border: "1px solid #3d3550",
  background: "#0d0b12",
  color: "#e8e4f0",
  fontSize: 13,
};

const btnPrimary: React.CSSProperties = {
  padding: "0.45rem 1rem",
  borderRadius: 6,
  border: "1px solid #6b5a9e",
  background: "#4a3d6e",
  color: "#fff",
  cursor: "pointer",
  fontSize: 13,
};
