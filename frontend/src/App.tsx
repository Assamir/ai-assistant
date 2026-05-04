import React, { useCallback, useMemo, useState } from "react";
import { AvatarCanvas } from "./AvatarCanvas";
import { ConfigPanel, type ConfigTabId } from "./ConfigPanel";
import { useAudioStreamPlayer } from "./useAudioStreamPlayer";
import { useWebSocket, type WsFrame } from "./useWebSocket";

const VRM_STORAGE_KEY = "assystent.vrmUrl";

function readInitialVrmUrl(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const stored = localStorage.getItem(VRM_STORAGE_KEY)?.trim();
  if (stored) {
    return stored;
  }
  const bridged = window.assystent?.vrmUrl?.trim();
  if (bridged) {
    return bridged;
  }
  return import.meta.env.VITE_VRM_URL?.trim() || "";
}

export function App() {
  const [log, setLog] = useState<string[]>([]);
  const [emotion, setEmotion] = useState("neutral");
  const [configTab, setConfigTab] = useState<ConfigTabId>("connection");
  const [vrmUrl, setVrmUrl] = useState(readInitialVrmUrl);

  const { feedAudioChunk, isSpeaking, stop: stopAudio } = useAudioStreamPlayer();

  const onFrame = useCallback(
    (f: WsFrame) => {
      if (f.event === "emotion" && typeof f.payload.emotion === "string") {
        setEmotion(f.payload.emotion);
      }
      if (f.event === "audio_stream" && typeof f.payload.chunk_base64 === "string") {
        feedAudioChunk(f.payload.chunk_base64);
      }
      setLog((prev) => [
        ...prev.slice(-40),
        `${new Date().toISOString().slice(11, 19)} ← ${f.event}`,
      ]);
    },
    [feedAudioChunk],
  );

  const { status, sendFrame } = useWebSocket({
    connect: true,
    onFrame,
  });

  const push = (line: string) =>
    setLog((prev) => [...prev.slice(-40), `${new Date().toISOString().slice(11, 19)} ${line}`]);

  const saveVrmUrl = useCallback((next: string) => {
    const u = next.trim();
    setVrmUrl(u);
    localStorage.setItem(VRM_STORAGE_KEY, u);
  }, []);

  const layout = useMemo(
    () => ({
      fontFamily: "system-ui, Segoe UI, sans-serif",
      padding: "1.25rem",
      maxWidth: 960,
      margin: "0 auto",
      color: "#e8e4f0",
      minHeight: "100vh",
      boxSizing: "border-box" as const,
      background: "linear-gradient(165deg, #0f0c14 0%, #1a1525 45%, #0d0b12 100%)",
    }),
    [],
  );

  return (
    <main style={layout}>
      <h1 style={{ fontSize: "1.65rem", fontWeight: 600, margin: "0 0 0.25rem" }}>Assystent</h1>
      <p style={{ margin: "0 0 1.25rem", color: "#b8afc8", fontSize: 15 }}>
        T10–T14: VRM, emocje z WS, audio WAV z multiplexu, konfiguracja, pakiet <code>electron-builder</code>.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 340px)",
          gap: "1.25rem",
          alignItems: "start",
        }}
      >
        <div>
          <AvatarCanvas vrmUrl={vrmUrl} emotion={emotion} lipSync={isSpeaking} />
          <p style={{ margin: "0.5rem 0 0", fontSize: 12, color: "#8a8198" }}>
            Emocja (z WS): <strong style={{ color: "#d4ccec" }}>{emotion}</strong>
            {isSpeaking ? " · odtwarzanie TTS" : ""}
          </p>

          <section style={{ marginTop: "1.25rem" }}>
            <h2 style={{ fontSize: "0.95rem", margin: "0 0 0.65rem" }}>WebSocket</h2>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => {
                  const ok = sendFrame("ping", {});
                  push(ok ? "→ ping" : "→ ping (socket niegotowy)");
                }}
                style={btnSecondary}
              >
                Ping
              </button>
              <button
                type="button"
                onClick={() => {
                  const ok = sendFrame("frontend_ready", {});
                  push(ok ? "→ frontend_ready" : "→ frontend_ready (socket niegotowy)");
                }}
                style={btnSecondary}
              >
                Frontend ready
              </button>
              <button
                type="button"
                onClick={() => {
                  const ok = sendFrame("chat_text", { text: "Cześć z React." });
                  push(ok ? "→ chat_text" : "→ chat_text (socket niegotowy)");
                }}
                style={btnSecondary}
              >
                Chat (test)
              </button>
              <button type="button" onClick={() => stopAudio()} style={btnMuted}>
                Zatrzymaj audio
              </button>
            </div>
            <pre
              style={{
                marginTop: "0.85rem",
                padding: "0.75rem",
                background: "#0d0b12",
                color: "#c8c0dc",
                borderRadius: 8,
                fontSize: 11,
                maxHeight: 200,
                overflow: "auto",
                border: "1px solid #2a2438",
              }}
            >
              {log.length ? log.join("\n") : "Brak zdarzeń — uruchom backend na :8000."}
            </pre>
          </section>
        </div>

        <ConfigPanel
          tab={configTab}
          onTab={setConfigTab}
          wsStatus={status}
          vrmUrl={vrmUrl}
          onVrmSave={saveVrmUrl}
        />
      </div>

      <p style={{ marginTop: "1.5rem", fontSize: 12, color: "#6d6680" }}>
        <code>npm run dev</code> → Vite · <code>ASSYSTENT_DEV=1 npm run electron</code> → okno Electron.
      </p>
    </main>
  );
}

const btnSecondary: React.CSSProperties = {
  padding: "0.4rem 0.85rem",
  borderRadius: 6,
  border: "1px solid #4a3f62",
  background: "#231d2e",
  color: "#e8e4f0",
  cursor: "pointer",
  fontSize: 13,
};

const btnMuted: React.CSSProperties = {
  ...btnSecondary,
  borderColor: "#3d3550",
  color: "#b8afc8",
};
