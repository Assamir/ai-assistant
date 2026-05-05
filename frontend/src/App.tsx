import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { configPutHeaders, normalizeApiBaseUrl, readApiBaseUrl } from "./apiBase";
import { AvatarCanvas } from "./AvatarCanvas";
import { ConfigPanel, type ConfigTabId } from "./ConfigPanel";
import { SetupWizard, SETUP_WIZARD_STORAGE_KEY, hasSetupWizardDismissed } from "./SetupWizard";
import { useAudioStreamPlayer } from "./useAudioStreamPlayer";
import { useWebSocket, type WsFrame } from "./useWebSocket";

const VRM_STORAGE_KEY = "assystent.vrmUrl";
const API_BASE_STORAGE_KEY = "assystent.apiBaseUrl";

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

function readInitialApiBase(): string {
  if (typeof window === "undefined") {
    return "http://127.0.0.1:8000";
  }
  const stored = localStorage.getItem(API_BASE_STORAGE_KEY)?.trim();
  if (stored) {
    return normalizeApiBaseUrl(stored);
  }
  return readApiBaseUrl();
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

interface ProfileBannerState {
  title: string;
  detail: string;
}

function strPayload(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() ? v : undefined;
}

function bannerFromProfileWsFrame(f: WsFrame): ProfileBannerState | null {
  if (f.event === "player_profile.league_hint") {
    const game = strPayload(f.payload.game) ?? "gra";
    const league = strPayload(f.payload.profile_league);
    const detail =
      league !== undefined
        ? `Zapisana liga w profilu (${league}) może nie zgadzać się z bieżącym sezonem (${game}). Sprawdź PATCH profilu lub archiwum sezonu.`
        : `Możliwa rozbieżność ligi — gra: ${game}. Sprawdź profil lub archiwum sezonu.`;
    return { title: "Sugestia: weryfikacja ligi", detail };
  }
  if (f.event === "player_profile.league_changed") {
    const game = strPayload(f.payload.game) ?? "gra";
    const prev = strPayload(f.payload.previous_league);
    const next = strPayload(f.payload.league);
    const detail =
      prev !== undefined && next !== undefined
        ? `Zmieniono ligę dla ${game}: ${prev} → ${next}. Rozważ archiwum poprzedniego sezonu (POST .../archive).`
        : `Zaktualizowano ligę w profilu (${game}). Rozważ archiwum sezonu, jeśli to reset.`;
    return { title: "Profil: zmiana ligi", detail };
  }
  return null;
}

export function App() {
  const [log, setLog] = useState<string[]>([]);
  const [emotion, setEmotion] = useState("neutral");
  const [configTab, setConfigTab] = useState<ConfigTabId>("connection");
  const [vrmUrl, setVrmUrl] = useState(readInitialVrmUrl);
  const [apiBase, setApiBase] = useState(readInitialApiBase);
  const [statusJson, setStatusJson] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [busyStatus, setBusyStatus] = useState(false);
  const [ttsVoiceSpeed, setTtsVoiceSpeed] = useState("1");
  const [busyConfig, setBusyConfig] = useState(false);
  const [configMessage, setConfigMessage] = useState<string | null>(null);
  const [showWizard, setShowWizard] = useState(
    () => typeof window !== "undefined" && !hasSetupWizardDismissed(),
  );
  const [profileBanner, setProfileBanner] = useState<ProfileBannerState | null>(null);
  const profileBannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const dismissProfileBanner = useCallback(() => {
    if (profileBannerTimer.current !== null) {
      clearTimeout(profileBannerTimer.current);
      profileBannerTimer.current = null;
    }
    setProfileBanner(null);
  }, []);

  useEffect(() => {
    return () => {
      if (profileBannerTimer.current !== null) {
        clearTimeout(profileBannerTimer.current);
      }
    };
  }, []);

  const { feedAudioChunk, isSpeaking, mouthLevel, stop: stopAudio } = useAudioStreamPlayer();

  const onFrame = useCallback(
    (f: WsFrame) => {
      if (f.event === "emotion" && typeof f.payload.emotion === "string") {
        setEmotion(f.payload.emotion);
      }
      if (f.event === "audio_stream" && typeof f.payload.chunk_base64 === "string") {
        feedAudioChunk(f.payload.chunk_base64);
      }
      if (
        (f.event === "player_profile.league_hint" && f.payload.mismatch_hint === true) ||
        f.event === "player_profile.league_changed"
      ) {
        const b = bannerFromProfileWsFrame(f);
        if (b) {
          setProfileBanner(b);
          if (profileBannerTimer.current !== null) {
            clearTimeout(profileBannerTimer.current);
          }
          profileBannerTimer.current = setTimeout(() => setProfileBanner(null), 16_000);
        }
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

  const saveApiBase = useCallback((next: string) => {
    const t = next.trim();
    const u = t ? normalizeApiBaseUrl(t) : readApiBaseUrl();
    setApiBase(u);
    localStorage.setItem(API_BASE_STORAGE_KEY, u);
  }, []);

  /** Jednorazowa naprawa złego `localStorage` (np. file://…) po aktualizacji klienta. */
  useEffect(() => {
    const raw = localStorage.getItem(API_BASE_STORAGE_KEY)?.trim();
    if (!raw) {
      return;
    }
    const fixed = normalizeApiBaseUrl(raw);
    if (fixed !== raw) {
      localStorage.setItem(API_BASE_STORAGE_KEY, fixed);
      setApiBase(fixed);
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    setBusyStatus(true);
    setStatusError(null);
    setConfigMessage(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/status`);
      const text = await res.text();
      if (!res.ok) {
        setStatusJson(null);
        setStatusError(`HTTP ${res.status}: ${text.slice(0, 400)}`);
        return;
      }
      try {
        setStatusJson(JSON.stringify(JSON.parse(text), null, 2));
      } catch {
        setStatusJson(text);
      }
    } catch (e) {
      setStatusJson(null);
      setStatusError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyStatus(false);
    }
  }, [apiBase]);

  const applyTtsSpeed = useCallback(async () => {
    const spd = Number(ttsVoiceSpeed);
    if (!Number.isFinite(spd) || spd < 0.25 || spd > 3) {
      setConfigMessage("Prędkość musi być liczbą 0.25–3.");
      return;
    }
    setBusyConfig(true);
    setConfigMessage(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/config`, {
        method: "PUT",
        headers: configPutHeaders(),
        body: JSON.stringify({ patch: { tts: { voice_speed: spd } } }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail =
          typeof data === "object" && data && "detail" in data
            ? JSON.stringify((data as { detail: unknown }).detail)
            : res.statusText;
        setConfigMessage(`Błąd ${res.status}: ${detail}`);
        return;
      }
      setConfigMessage("Zapisano — backend przeładowany (hot-reload).");
    } catch (e) {
      setConfigMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyConfig(false);
    }
  }, [apiBase, ttsVoiceSpeed]);

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
        Avatar VRM, lip-sync z audio, idle; REST <code>PUT /api/v1/config</code> + panel statusu.
      </p>

      {profileBanner ? (
        <aside
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            border: "1px solid #6b5b3e",
            background: "rgba(212, 168, 90, 0.12)",
            color: "#f0e6d4",
            fontSize: 14,
            lineHeight: 1.45,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", alignItems: "start" }}>
            <div>
              <strong style={{ color: "#f5d799" }}>{profileBanner.title}</strong>
              <div style={{ marginTop: "0.35rem" }}>{profileBanner.detail}</div>
            </div>
            <button type="button" onClick={dismissProfileBanner} style={btnMuted}>
              Zamknij
            </button>
          </div>
        </aside>
      ) : null}

      <div
        className="assystent-grid"
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(280px, 340px)",
          gap: "1.25rem",
          alignItems: "start",
        }}
      >
        <div>
          <AvatarCanvas vrmUrl={vrmUrl} emotion={emotion} lipSyncLevel={isSpeaking ? mouthLevel : 0} />
          <p style={{ margin: "0.5rem 0 0", fontSize: 12, color: "#8a8198" }}>
            Emocja (z WS): <strong style={{ color: "#d4ccec" }}>{emotion}</strong>
            {isSpeaking ? " · TTS (lip-sync)" : ""}
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
          profileWsActive={profileBanner !== null}
          vrmUrl={vrmUrl}
          onVrmSave={saveVrmUrl}
          apiBaseUrl={apiBase}
          onApiBaseSave={saveApiBase}
          onFetchStatus={fetchStatus}
          statusJson={statusJson}
          statusError={statusError}
          busyStatus={busyStatus}
          ttsVoiceSpeed={ttsVoiceSpeed}
          onTtsVoiceSpeedChange={setTtsVoiceSpeed}
          onApplyTtsSpeed={applyTtsSpeed}
          busyConfig={busyConfig}
          configMessage={configMessage}
        />
      </div>

      <p style={{ marginTop: "1.5rem", fontSize: 12, color: "#6d6680" }}>
        <code>npm run dev</code> → Vite · <code>ASSYSTENT_DEV=1 npm run electron</code> → okno Electron.{" "}
        <button
          type="button"
          onClick={() => {
            localStorage.removeItem(SETUP_WIZARD_STORAGE_KEY);
            setShowWizard(true);
          }}
          style={btnMuted}
        >
          Kreator startowy
        </button>
        {" · "}Zmienne: <code>docs/ENV_SETUP.md</code>
      </p>

      {showWizard ? (
        <SetupWizard
          apiBase={apiBase}
          onFinish={() => setShowWizard(false)}
          onOpenConnectionSettings={() => setConfigTab("connection")}
        />
      ) : null}
    </main>
  );
}
