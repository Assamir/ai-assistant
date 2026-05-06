import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { configPutHeaders, normalizeApiBaseUrl, readApiBaseUrl } from "./apiBase";
import { AvatarCanvas } from "./AvatarCanvas";
import { ConfigPanel, type ConfigTabId } from "./ConfigPanel";
import { SetupWizard, SETUP_WIZARD_STORAGE_KEY, hasSetupWizardDismissed } from "./SetupWizard";
import { useAudioStreamPlayer } from "./useAudioStreamPlayer";
import { usePttRecorder } from "./usePttRecorder";
import { useWebSocket, type WsFrame } from "./useWebSocket";
import { bundledVrmRelativeUrl, DEFAULT_BUNDLED_VRM_FILENAME } from "./vrmBundledCatalog";
import {
  bundledPiperVoiceById,
  DEFAULT_PIPER_VOICE_ID,
  PIPER_EXECUTABLE_LS,
  PIPER_RESOURCES_ROOT_LS,
  PIPER_VOICE_ID_LS,
} from "./piperVoicesCatalog";
import { joinResourcesPath } from "./piperVoicesPaths";

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
  return import.meta.env.VITE_VRM_URL?.trim() || bundledVrmRelativeUrl(DEFAULT_BUNDLED_VRM_FILENAME);
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

function sttHintMessage(hint: string | null): string | null {
  if (!hint) {
    return null;
  }
  if (hint === "no_audio_payload") {
    return "Nie doszła próbka audio (ptt_end bez pola audio).";
  }
  if (hint === "stt_unconfigured") {
    return "Backend bez STT — ustaw silnik rozpoznawania mowy w konfiguracji.";
  }
  return hint;
}

function ttsDiagFromStatusJson(data: unknown): {
  checked: boolean;
  available: boolean;
  resolvedYaml: string | null;
} {
  const d = data as {
    health?: {
      components?: { tts?: { available?: boolean } };
      config?: { resolved_yaml?: string | null };
    };
  };
  const ok = d.health?.components?.tts?.available === true;
  const ry = d.health?.config?.resolved_yaml;
  return {
    checked: true,
    available: ok,
    resolvedYaml: typeof ry === "string" ? ry : null,
  };
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
  const [piperResourcesRootDraft, setPiperResourcesRootDraft] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem(PIPER_RESOURCES_ROOT_LS) ?? "" : "",
  );
  const [piperExecutableDraft, setPiperExecutableDraft] = useState(() =>
    typeof window !== "undefined" ? localStorage.getItem(PIPER_EXECUTABLE_LS) ?? "" : "",
  );
  const [selectedPiperVoiceId, setSelectedPiperVoiceId] = useState(() =>
    typeof window !== "undefined"
      ? localStorage.getItem(PIPER_VOICE_ID_LS) || DEFAULT_PIPER_VOICE_ID
      : DEFAULT_PIPER_VOICE_ID,
  );
  const [showWizard, setShowWizard] = useState(
    () => typeof window !== "undefined" && !hasSetupWizardDismissed(),
  );
  const [profileBanner, setProfileBanner] = useState<ProfileBannerState | null>(null);
  const profileBannerTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [chatDraft, setChatDraft] = useState("");
  const [assistantLine, setAssistantLine] = useState<string | null>(null);
  const [sttBlock, setSttBlock] = useState<{ text: string; hint: string | null } | null>(null);
  const [observerLine, setObserverLine] = useState<string | null>(null);
  const [activityFeed, setActivityFeed] = useState<string[]>([]);
  const pttCycleRunningRef = useRef(false);
  const pttReleasedEarlyRef = useRef(false);
  const pttReleaseRef = useRef<(() => void) | null>(null);

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

  const { feedAudioChunk, isSpeaking, mouthLevel, stop: stopAudio, prime: primeAudio, playbackError } =
    useAudioStreamPlayer();
  const { pttBusy, pttError, setPttError, pttArm, pttFinalize } = usePttRecorder();

  useEffect(() => {
    const unlock = () => {
      void primeAudio();
    };
    window.addEventListener("pointerdown", unlock, { once: true });
    return () => window.removeEventListener("pointerdown", unlock);
  }, [primeAudio]);

  const onFrame = useCallback(
    (f: WsFrame) => {
      if (f.event === "emotion" && typeof f.payload.emotion === "string") {
        setEmotion(f.payload.emotion);
      }
      if (
        (f.event === "assistant_reply_text" || f.event === "text_overlay") &&
        typeof f.payload.text === "string"
      ) {
        const line = f.payload.text.trim();
        setAssistantLine(line || null);
      }
      if (f.event === "audio_stream" && typeof f.payload.chunk_base64 === "string") {
        void primeAudio();
        feedAudioChunk(f.payload.chunk_base64);
      }
      if (f.event === "stt_result") {
        setSttBlock({
          text: typeof f.payload.text === "string" ? f.payload.text : "",
          hint: typeof f.payload.hint === "string" ? f.payload.hint : null,
        });
      }
      if (f.event === "observer_comment" && typeof f.payload.text === "string") {
        const o = f.payload.text.trim();
        setObserverLine(o || null);
      }
      if (f.event === "agent_activity") {
        const tool = typeof f.payload.tool === "string" ? f.payload.tool : "(?)";
        const phase = typeof f.payload.phase === "string" ? f.payload.phase : "";
        const preview = typeof f.payload.arguments_preview === "string" ? f.payload.arguments_preview : "";
        const short = preview.length > 160 ? `${preview.slice(0, 160)}…` : preview;
        const stamp = new Date().toISOString().slice(11, 19);
        const line = `${stamp} · ${tool} (${phase})${short ? `: ${short}` : ""}`;
        setActivityFeed((prev) => [...prev.slice(-14), line]);
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
    [feedAudioChunk, primeAudio],
  );

  const { status, sendFrame } = useWebSocket({
    connect: true,
    onFrame,
  });

  const push = useCallback((line: string) => {
    setLog((prev) => [...prev.slice(-40), `${new Date().toISOString().slice(11, 19)} ${line}`]);
  }, []);

  const wsReady = status === "open";

  const [ttsDiag, setTtsDiag] = useState<{
    checked: boolean;
    available: boolean;
    resolvedYaml: string | null;
  }>({ checked: false, available: false, resolvedYaml: null });

  useEffect(() => {
    if (!wsReady) {
      return undefined;
    }
    let cancelled = false;
    const url = `${apiBase.replace(/\/$/, "")}/api/v1/status`;
    void (async () => {
      try {
        const res = await fetch(url);
        const data = (await res.json()) as Record<string, unknown>;
        if (!cancelled) {
          setTtsDiag(ttsDiagFromStatusJson(data));
        }
      } catch {
        if (!cancelled) {
          setTtsDiag({ checked: false, available: false, resolvedYaml: null });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [wsReady, apiBase]);

  const handleSendText = useCallback(() => {
    const t = chatDraft.trim();
    if (!t) {
      return;
    }
    void primeAudio();
    stopAudio();
    const ok = sendFrame("chat_text", { text: t });
    const preview = t.length > 80 ? `${t.slice(0, 80)}…` : t;
    push(ok ? `→ chat_text (${preview})` : "→ chat_text (socket niegotowy)");
    if (ok) {
      setChatDraft("");
    }
  }, [chatDraft, sendFrame, stopAudio, push, primeAudio]);

  const handlePttDown = useCallback(() => {
    if (pttCycleRunningRef.current) {
      return;
    }
    pttCycleRunningRef.current = true;
    void (async () => {
      try {
        void primeAudio();
        stopAudio();
        setPttError(null);
        pttReleasedEarlyRef.current = false;
        pttReleaseRef.current = null;

        const wsOk = sendFrame("ptt_start", {});
        if (!wsOk) {
          push("→ ptt_start (socket niegotowy)");
          return;
        }
        push("→ ptt_start");

        const armed = await pttArm();
        if (!armed) {
          sendFrame("ptt_end", {});
          push("→ ptt_end (błąd mikrofonu / nagrywania)");
          return;
        }

        await new Promise<void>((resolve) => {
          pttReleaseRef.current = resolve;
          if (pttReleasedEarlyRef.current) {
            resolve();
          }
        });

        const audioB64 = await pttFinalize();
        const payload: Record<string, unknown> = audioB64 ? { audio: audioB64 } : {};
        const endOk = sendFrame("ptt_end", payload);
        if (endOk) {
          push(audioB64 ? "→ ptt_end (wav)" : "→ ptt_end");
        } else {
          push("→ ptt_end (socket niegotowy)");
        }
      } finally {
        pttCycleRunningRef.current = false;
        pttReleaseRef.current = null;
      }
    })();
  }, [stopAudio, sendFrame, push, pttArm, pttFinalize, setPttError, primeAudio]);

  const handlePttUp = useCallback(() => {
    pttReleasedEarlyRef.current = true;
    const r = pttReleaseRef.current;
    if (r) {
      r();
      pttReleaseRef.current = null;
    }
  }, []);

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
        const parsed = JSON.parse(text);
        setStatusJson(JSON.stringify(parsed, null, 2));
        setTtsDiag(ttsDiagFromStatusJson(parsed));
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

  const applyPiperVoice = useCallback(async () => {
    const root = piperResourcesRootDraft.trim();
    if (!root) {
      setConfigMessage("Ustaw absolutną ścieżkę do katalogu frontend/resources tego repozytorium.");
      return;
    }
    const voice = bundledPiperVoiceById(selectedPiperVoiceId);
    if (!voice) {
      setConfigMessage("Nieznany wybór głosu.");
      return;
    }
    const onnxAbs = joinResourcesPath(root, voice.onnxRelativeToResources);
    if (!onnxAbs) {
      setConfigMessage("Nie można złożyć ścieżki do pliku ONNX.");
      return;
    }
    setBusyConfig(true);
    setConfigMessage(null);
    try {
      const ttsPatch: Record<string, unknown> = { piper_voice_onnx_path: onnxAbs };
      const exe = piperExecutableDraft.trim();
      if (exe) {
        ttsPatch.piper_executable = exe;
      }
      const res = await fetch(`${apiBase}/api/v1/config`, {
        method: "PUT",
        headers: configPutHeaders(),
        body: JSON.stringify({ patch: { tts: ttsPatch } }),
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
      localStorage.setItem(PIPER_RESOURCES_ROOT_LS, root);
      localStorage.setItem(PIPER_VOICE_ID_LS, selectedPiperVoiceId);
      if (exe) {
        localStorage.setItem(PIPER_EXECUTABLE_LS, exe);
      } else {
        localStorage.removeItem(PIPER_EXECUTABLE_LS);
      }
      setConfigMessage("Zapisano głos Piper — backend przeładowany (hot-reload).");
      const st = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/status`);
      if (st.ok) {
        const payload = (await st.json()) as Record<string, unknown>;
        setTtsDiag(ttsDiagFromStatusJson(payload));
      }
    } catch (e) {
      setConfigMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyConfig(false);
    }
  }, [apiBase, piperResourcesRootDraft, piperExecutableDraft, selectedPiperVoiceId]);

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
        Avatar VRM, lip-sync z audio (<code>audio_stream</code> przez WebSocket); czat tekstowy, push‑to‑talk; REST{" "}
        <code>PUT /api/v1/config</code> + panel statusu.
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
            {isSpeaking ? " · odtwarzanie TTS (lip-sync)" : ""}
          </p>
          {playbackError ? (
            <p style={{ margin: "0.35rem 0 0", fontSize: 13, color: "#f0b0b8", lineHeight: 1.45 }}>{playbackError}</p>
          ) : null}
          {ttsDiag.checked && !ttsDiag.available ? (
            <div
              style={{
                margin: "0.4rem 0 0",
                padding: "0.65rem 0.85rem",
                borderRadius: 8,
                border: "1px solid #6b5338",
                background: "rgba(90, 70, 40, 0.15)",
                maxWidth: 560,
              }}
            >
              <div style={{ fontSize: 13, color: "#e8d4b0", lineHeight: 1.5 }}>
                Silnik Piper nie jest aktywny — backend bez <code style={{ fontSize: 12 }}>audio_stream</code>. Kod
                włącza TTS dopiero gdy ustawisz <strong>niepustą</strong> wartość{" "}
                <code style={{ fontSize: 12 }}>tts.piper_voice_onnx_path</code> (plik <code>.onnx</code> +
                towarzyszący jeśli trzeba). Opcjonalnie pełna ścieżka do binary:{" "}
                <code style={{ fontSize: 12 }}>tts.piper_executable</code> (domyślnie szuka komendy{" "}
                <code style={{ fontSize: 12 }}>piper</code> na <code style={{ fontSize: 12 }}>PATH</code>).
              </div>
              {ttsDiag.resolvedYaml ? (
                <div style={{ fontSize: 12, color: "#a89880", marginTop: "0.45rem", wordBreak: "break-all" }}>
                  Aktualnie wczytywany YAML: <code style={{ fontSize: 11 }}>{ttsDiag.resolvedYaml}</code>
                </div>
              ) : (
                <div style={{ fontSize: 12, color: "#a89880", marginTop: "0.45rem" }}>
                  Nie znaleziono pliku YAML w content root — możesz ustawić ścieżkę przez zmienną{" "}
                  <code style={{ fontSize: 11 }}>ASSY_TTS__PIPER_VOICE_ONNX_PATH</code> (i opcjonalnie{" "}
                  <code style={{ fontSize: 11 }}>ASSY_TTS__PIPER_EXECUTABLE</code>).
                </div>
              )}
              <pre
                style={{
                  marginTop: "0.55rem",
                  padding: "0.5rem 0.6rem",
                  borderRadius: 6,
                  background: "#0d0b12",
                  border: "1px solid #2a2438",
                  fontSize: 11,
                  color: "#d4cce8",
                  overflowX: "auto",
                  whiteSpace: "pre-wrap",
                }}
              >
{`tts:
  piper_executable: "C:/sciezka/do/piper.exe"
  piper_voice_onnx_path: "C:/sciezka/do/glos/pl_PL-xxxx-medium.onnx"`}
              </pre>
              <div style={{ fontSize: 12, color: "#8a8175", marginTop: "0.35rem" }}>
                Po zapisie zrestartuj backend albo przeładuj konfigurację (PUT /api/v1/config). Pełny opis pobrania Pipera:{" "}
                <code style={{ fontSize: 11 }}>docs/ENV_SETUP.md</code>, sekcja 5.3.
              </div>
            </div>
          ) : null}

          <div
            style={{
              marginTop: "0.65rem",
              padding: "0.65rem 0.85rem",
              borderRadius: 8,
              border: "1px solid #362e48",
              background: "rgba(18, 15, 28, 0.65)",
              maxWidth: 560,
            }}
          >
            <div style={{ fontSize: 12, color: "#9a93b0", marginBottom: "0.25rem" }}>Co usłyszał backend (STT)</div>
            {sttBlock ? (
              <>
                <div style={{ fontSize: 14, color: "#eae6f8", lineHeight: 1.45, wordBreak: "break-word" }}>
                  {sttBlock.text.trim() ? sttBlock.text : "— (pusty wynik albo cisza)"}
                </div>
                {sttHintMessage(sttBlock.hint) ? (
                  <div style={{ fontSize: 12, color: "#c89880", marginTop: "0.35rem" }}>{sttHintMessage(sttBlock.hint)}</div>
                ) : null}
              </>
            ) : (
              <div style={{ fontSize: 13, color: "#7a7390", fontStyle: "italic" }}>Użyj PTT lub wyślij wiadomość — tu pojawi się transkrypt.</div>
            )}
          </div>

          <div
            style={{
              marginTop: "0.65rem",
              padding: "0.65rem 0.85rem",
              borderRadius: 8,
              border: "1px solid #2f3d4f",
              background: "rgba(14, 20, 28, 0.55)",
              maxWidth: 560,
            }}
          >
            <div style={{ fontSize: 12, color: "#9a93b0", marginBottom: "0.25rem" }}>Obserwator ekranu / wizja</div>
            {observerLine ? (
              <div style={{ fontSize: 14, color: "#c8dce8", lineHeight: 1.45 }}>{observerLine}</div>
            ) : (
              <div style={{ fontSize: 13, color: "#6d7a88" }}>Brak ostatniego komentarza z obserwatora.</div>
            )}
          </div>

          {activityFeed.length ? (
            <div
              style={{
                marginTop: "0.65rem",
                padding: "0.65rem 0.85rem",
                borderRadius: 8,
                border: "1px solid #3a3248",
                background: "rgba(22, 18, 32, 0.55)",
                maxWidth: 560,
              }}
            >
              <div style={{ fontSize: 12, color: "#9a93b0", marginBottom: "0.35rem" }}>Działania agenta (narzędzia)</div>
              <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: 12, color: "#c8c0dc", lineHeight: 1.5 }}>
                {activityFeed.map((line, i) => (
                  <li key={`${i}-${line.slice(0, 24)}`} style={{ marginBottom: "0.2rem" }}>
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {assistantLine ? (
            <p style={{ margin: "0.65rem 0 0", fontSize: 14, color: "#c8c0dc", lineHeight: 1.45 }}>
              <span style={{ color: "#8a8198", fontSize: 12 }}>Odpowiedź agenta (tekst): </span>
              <span style={{ color: "#eae6f8" }}>{assistantLine}</span>
            </p>
          ) : null}

          <section style={{ marginTop: "1.25rem" }}>
            <h2 style={{ fontSize: "0.95rem", margin: "0 0 0.65rem" }}>WebSocket</h2>

            <div style={{ marginBottom: "1rem" }}>
              <label
                htmlFor="assystent-chat-draft"
                style={{ display: "block", marginBottom: "0.35rem", fontSize: 13, color: "#c8c0dc" }}
              >
                Wiadomość do agenta
              </label>
              <textarea
                id="assystent-chat-draft"
                aria-label="Wiadomość do agenta"
                value={chatDraft}
                disabled={!wsReady}
                onChange={(e) => setChatDraft(e.target.value)}
                placeholder={wsReady ? "Napisz i wyślij (Enter). Shift+Enter — nowa linia." : "Poczekaj na połączenie WS…"}
                rows={3}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendText();
                  }
                }}
                style={{
                  width: "100%",
                  maxWidth: 520,
                  boxSizing: "border-box",
                  resize: "vertical",
                  padding: "0.55rem 0.65rem",
                  borderRadius: 8,
                  border: "1px solid #3d3550",
                  background: "#120f18",
                  color: "#eae6f8",
                  fontSize: 14,
                  fontFamily: "inherit",
                  lineHeight: 1.4,
                  minHeight: 72,
                }}
              />
              <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", marginTop: "0.5rem", alignItems: "center" }}>
                <button type="button" onClick={() => handleSendText()} disabled={!wsReady} style={btnSecondary}>
                  Wyślij
                </button>
                <span style={{ fontSize: 12, color: "#7a7390" }}>Enter wyślij · Shift+Enter nowa linia</span>
              </div>
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <span style={{ display: "block", marginBottom: "0.35rem", fontSize: 13, color: "#c8c0dc" }}>
                Mikrofon (push-to-talk)
              </span>
              <button
                type="button"
                disabled={!wsReady || pttBusy}
                onPointerDown={(e) => {
                  if (!wsReady || pttBusy) {
                    return;
                  }
                  if (e.pointerType === "mouse" && e.button !== 0) {
                    return;
                  }
                  e.preventDefault();
                  const el = e.currentTarget;
                  if (el instanceof HTMLElement) {
                    try {
                      el.setPointerCapture(e.pointerId);
                    } catch {
                      /* starsze silniki / nietypowe wskaźniki */
                    }
                  }
                  handlePttDown();
                }}
                onPointerUp={(e) => {
                  if (e.pointerType === "mouse" && e.button !== 0) {
                    return;
                  }
                  e.preventDefault();
                  const el = e.currentTarget;
                  if (el instanceof HTMLElement) {
                    try {
                      if (el.hasPointerCapture(e.pointerId)) {
                        el.releasePointerCapture(e.pointerId);
                      }
                    } catch {
                      /* ignore */
                    }
                  }
                  handlePttUp();
                }}
                onPointerCancel={(e) => {
                  const el = e.currentTarget;
                  if (el instanceof HTMLElement) {
                    try {
                      if (el.hasPointerCapture(e.pointerId)) {
                        el.releasePointerCapture(e.pointerId);
                      }
                    } catch {
                      /* ignore */
                    }
                  }
                  handlePttUp();
                }}
                style={{
                  ...btnSecondary,
                  borderColor: "#5c4d8c",
                  background: "#2c2440",
                  userSelect: "none",
                  touchAction: "manipulation",
                  minWidth: "11rem",
                }}
              >
                Trzymaj — mów
              </button>
              {pttBusy ? (
                <span style={{ marginLeft: "0.5rem", fontSize: 12, color: "#9a93b0" }}>Przygotowanie mikrofonu…</span>
              ) : null}
              {pttError ? (
                <div style={{ marginTop: "0.35rem", fontSize: 12, color: "#e898a8" }}>{pttError}</div>
              ) : null}
              {!wsReady ? (
                <div style={{ marginTop: "0.35rem", fontSize: 12, color: "#7a7390" }}>PTT dostępne po zestawieniu WS.</div>
              ) : null}
            </div>

            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
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
          piperResourcesRoot={piperResourcesRootDraft}
          onPiperResourcesRootChange={setPiperResourcesRootDraft}
          piperExecutable={piperExecutableDraft}
          onPiperExecutableChange={setPiperExecutableDraft}
          selectedPiperVoiceId={selectedPiperVoiceId}
          onSelectedPiperVoiceIdChange={(id) => {
            setSelectedPiperVoiceId(id);
            if (typeof window !== "undefined") {
              localStorage.setItem(PIPER_VOICE_ID_LS, id);
            }
          }}
          onApplyPiperVoice={applyPiperVoice}
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
