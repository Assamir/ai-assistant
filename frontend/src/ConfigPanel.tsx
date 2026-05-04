import React, { useState } from "react";

export type ConfigTabId = "connection" | "avatar" | "more";

interface ConfigPanelProps {
  tab: ConfigTabId;
  onTab: (t: ConfigTabId) => void;
  wsStatus: string;
  vrmUrl: string;
  onVrmSave: (url: string) => void;
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
  vrmUrl,
  onVrmSave,
}: ConfigPanelProps) {
  const [draft, setDraft] = useState(vrmUrl);

  React.useEffect(() => {
    setDraft(vrmUrl);
  }, [vrmUrl]);

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
          </p>
          <p style={{ margin: 0, color: "#b8afc8", wordBreak: "break-all" }}>
            <code style={{ fontSize: 12 }}>{wsDisplay}</code>
          </p>
          <p style={{ margin: "0.75rem 0 0", color: "#8a8198", fontSize: 12 }}>
            W Electron: <code>ASSYSTENT_WS_URL</code> lub <code>VITE_WS_URL</code> w preload.
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
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="https://…/model.vrm"
            style={{
              width: "100%",
              boxSizing: "border-box",
              padding: "0.5rem 0.65rem",
              borderRadius: 6,
              border: "1px solid #3d3550",
              background: "#0d0b12",
              color: "#e8e4f0",
              fontSize: 13,
            }}
          />
          <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={() => onVrmSave(draft.trim())}
              style={{
                padding: "0.45rem 1rem",
                borderRadius: 6,
                border: "1px solid #6b5a9e",
                background: "#4a3d6e",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              Zapisz
            </button>
            <span style={{ fontSize: 12, color: "#8a8198", alignSelf: "center" }}>
              Zapamiętane w <code>localStorage</code> (<code>assystent.vrmUrl</code>).
            </span>
          </div>
        </div>
      )}

      {tab === "more" && (
        <div style={{ fontSize: 14, color: "#b8afc8", lineHeight: 1.55 }}>
          <p style={{ margin: "0 0 0.5rem" }}>Audio TTS, persona i obserwator — wkrótce (REST / konfiguracja backendu).</p>
          <p style={{ margin: 0, fontSize: 12, color: "#8a8198" }}>
            Docelowo: <code>PUT /api/v1/config</code> oraz przełączniki w tej zakładce.
          </p>
        </div>
      )}
    </section>
  );
}
