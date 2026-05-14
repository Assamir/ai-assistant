import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { configPutHeaders, normalizeApiBaseUrl, readApiBaseUrl } from "./apiBase";
import { AvatarCanvas } from "./AvatarCanvas";
import { ChatHistoryPanel, type ChatMessage, type ThreadInfo, type AgentPlan, type AgentStep } from "./ChatHistoryPanel";
import { ConfigPanel, type ConfigTabId, type PersonaInfo } from "./ConfigPanel";
import { SetupWizard, SETUP_WIZARD_STORAGE_KEY, hasSetupWizardDismissed } from "./SetupWizard";
import { useAudioDevices } from "./useAudioDevices";
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
const MIC_DEVICE_STORAGE_KEY = "assystent.micDeviceId";
const SPEAKER_DEVICE_STORAGE_KEY = "assystent.outputDeviceId";

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

function readInitialUiConfig(): UiAvatarConfig {
  const bridgedScale = window.assystent?.overlayScale;
  const scale = typeof bridgedScale === "number" && Number.isFinite(bridgedScale) ? bridgedScale : 0.333;
  return {
    overlayScale: Math.min(1.5, Math.max(0.2, scale)),
    avatarBreathingEnabled: true,
    avatarStatePosesEnabled: true,
    avatarLookAtEnabled: true,
    avatarEmotionIntensity: 1.25,
    avatarEmotionCrossfadeSec: 0.7,
  };
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

/** Teksty diagnostyczne pod pusty panel obserwatora — z `GET /api/v1/status`. */
function observerHintsFromStatusJson(data: unknown): string[] {
  const hints: string[] = [];
  const d = data as {
    health?: {
      components?: {
        screen_capture?: { backend?: string | null; capture_available?: boolean };
        vision_pipeline?: { available?: boolean };
        vlm?: { enabled_in_config?: boolean; engine_initialized?: boolean };
        ocr?: { enabled_in_config?: boolean; engine_initialized?: boolean };
      };
    };
  };
  const c = d.health?.components;
  if (c?.screen_capture?.capture_available === false) {
    const b = c.screen_capture.backend;
    hints.push(
      `Zrzut ekranu niedostępny (backend: ${b ?? "—"}). Sprawdź DXcam / mss / pyautogui i logi przy starcie.`,
    );
  }
  if (c?.vision_pipeline?.available === false) {
    hints.push("Potok wizji (VLM/OCR) niedostępny — `screen_capture` i obserwator nie mają analizy obrazu.");
    if (c?.ocr?.enabled_in_config !== true) {
      hints.push(
        "Żeby szybko włączyć sam OCR: w terminalu z aktywnym venv backendu (katalog główny repo) `pip install -r requirements-vision.txt`, potem w YAML `ocr.enabled: true` i restart backendu.",
      );
    }
  }
  if (c?.vlm?.enabled_in_config === true && c?.vlm?.engine_initialized === false) {
    hints.push("VLM włączony w konfiguracji, ale silnik nie został załadowany (torch / model HF).");
  }
  if (c?.ocr?.enabled_in_config === true && c?.ocr?.engine_initialized === false) {
    hints.push(
      "OCR włączony w konfiguracji, ale EasyOCR nie działa — brak pakietu lub błąd init (backend może ponowić na CPU po GPU).",
    );
  }
  return hints;
}

const isConfigView = typeof window !== "undefined" && window.location.hash === "#config";
const isElectron = typeof window !== "undefined" && !!window.assystent;

interface UiAvatarConfig {
  overlayScale: number;
  avatarBreathingEnabled: boolean;
  avatarStatePosesEnabled: boolean;
  avatarLookAtEnabled: boolean;
  avatarEmotionIntensity: number;
  avatarEmotionCrossfadeSec: number;
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
  const [clickThrough, setClickThrough] = useState(false);
  const [sleeping, setSleeping] = useState(false);
  const [silentMode, setSilentMode] = useState(false);
  const [observerActive, setObserverActive] = useState(false);
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [chatPanelVisible, setChatPanelVisible] = useState(true);
  const [threadInfo, setThreadInfo] = useState<ThreadInfo>({ threadId: null, title: null, kind: null });
  const [agentPlan, setAgentPlan] = useState<AgentPlan | null>(null);
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [activePersona, setActivePersona] = useState("aria");
  const [visualState, setVisualState] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [uiCfg, setUiCfg] = useState<UiAvatarConfig>(readInitialUiConfig);
  const [mouseNorm, setMouseNorm] = useState<{ x: number; y: number } | null>(null);
  const [lastMouseMoveAtMs, setLastMouseMoveAtMs] = useState<number>(() => Date.now());
  const [micDeviceId, setMicDeviceId] = useState<string>(() =>
    typeof window !== "undefined" ? localStorage.getItem(MIC_DEVICE_STORAGE_KEY) ?? "" : "",
  );
  const [outputDeviceId, setOutputDeviceId] = useState<string>(() =>
    typeof window !== "undefined" ? localStorage.getItem(SPEAKER_DEVICE_STORAGE_KEY) ?? "" : "",
  );
  const [overlayInputOpen, setOverlayInputOpen] = useState(false);
  const [overlayDraft, setOverlayDraft] = useState("");
  const [displays, setDisplays] = useState<Array<{ id: number; label: string; isPrimary: boolean }>>([]);
  const [selectedDisplayId, setSelectedDisplayId] = useState<number | null>(null);
  const [autoSessionReportPending, setAutoSessionReportPending] = useState(false);

  const dragHandleRef = useRef<HTMLDivElement>(null);
  const subtitleClearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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

  const {
    feedAudioChunk,
    duck,
    isSpeaking,
    mouthLevel,
    stop: stopAudio,
    prime: primeAudio,
    playbackError,
    outputVolume,
    setOutputVolume,
  } = useAudioStreamPlayer(outputDeviceId || undefined);
  const { micDevices, speakerDevices, refreshMicDevices } = useAudioDevices();
  const { pttBusy, pttError, setPttError, pttArm, pttFinalize } = usePttRecorder({ deviceId: micDeviceId || undefined });

  useEffect(() => {
    const unlock = () => {
      void primeAudio();
    };
    window.addEventListener("pointerdown", unlock, { once: true });
    return () => window.removeEventListener("pointerdown", unlock);
  }, [primeAudio]);

  const scheduleSubtitleClear = useCallback(() => {
    if (subtitleClearTimerRef.current !== null) {
      clearTimeout(subtitleClearTimerRef.current);
    }
    subtitleClearTimerRef.current = setTimeout(() => {
      subtitleClearTimerRef.current = null;
      setAssistantLine(null);
      setObserverLine(null);
    }, 8000);
  }, []);

  useEffect(() => () => {
    if (subtitleClearTimerRef.current !== null) {
      clearTimeout(subtitleClearTimerRef.current);
    }
  }, []);

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
        if (line) {
          scheduleSubtitleClear();
          setChatHistory((prev) => [...prev.slice(-99), { role: "assistant", content: line, timestamp: Date.now() }]);
        }
      }
      if (f.event === "audio_stream" && typeof f.payload.chunk_base64 === "string") {
        void primeAudio();
        feedAudioChunk(f.payload.chunk_base64);
      }
      if (f.event === "audio_duck" && typeof f.payload.target_volume === "number") {
        const rampMs = typeof f.payload.ramp_ms === "number" ? f.payload.ramp_ms : 160;
        duck(f.payload.target_volume, rampMs);
      }
      if (f.event === "visual_state" && typeof f.payload.state === "string") {
        const s = f.payload.state as "idle" | "listening" | "thinking" | "speaking";
        setVisualState(s);
      }
      if (f.event === "ui_config_changed") {
        setUiCfg((prev) => ({
          overlayScale:
            typeof f.payload.overlay_scale === "number"
              ? Math.min(1.5, Math.max(0.2, f.payload.overlay_scale))
              : prev.overlayScale,
          avatarBreathingEnabled:
            typeof f.payload.avatar_breathing_enabled === "boolean"
              ? f.payload.avatar_breathing_enabled
              : prev.avatarBreathingEnabled,
          avatarStatePosesEnabled:
            typeof f.payload.avatar_state_poses_enabled === "boolean"
              ? f.payload.avatar_state_poses_enabled
              : prev.avatarStatePosesEnabled,
          avatarLookAtEnabled:
            typeof f.payload.avatar_look_at_enabled === "boolean"
              ? f.payload.avatar_look_at_enabled
              : prev.avatarLookAtEnabled,
          avatarEmotionIntensity:
            typeof f.payload.avatar_emotion_intensity === "number"
              ? f.payload.avatar_emotion_intensity
              : prev.avatarEmotionIntensity,
          avatarEmotionCrossfadeSec:
            typeof f.payload.avatar_emotion_crossfade_sec === "number"
              ? f.payload.avatar_emotion_crossfade_sec
              : prev.avatarEmotionCrossfadeSec,
        }));
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
        setObserverActive(true);
        if (o) {
          scheduleSubtitleClear();
          setChatHistory((prev) => [...prev.slice(-99), { role: "observer", content: o, timestamp: Date.now() }]);
        }
      }
      if (f.event === "window_click_through_on") {
        window.assystent?.setClickThrough?.(true);
        setClickThrough(true);
      }
      if (f.event === "window_click_through_off") {
        window.assystent?.setClickThrough?.(false);
        setClickThrough(false);
      }
      if (f.event === "avatar_hide") {
        setSleeping(true);
      }
      if (f.event === "avatar_show") {
        setSleeping(false);
      }
      if (f.event === "silent_mode") {
        setSilentMode(!!f.payload.enabled);
      }
      if (f.event === "system_state" && typeof f.payload.health === "string") {
        window.assystent?.setTrayHealth?.(f.payload.health);
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
      if (f.event === "auto_session_report_start") {
        setAutoSessionReportPending(true);
      }

      if (f.event === "thread_new") {
        setThreadInfo({ threadId: typeof f.payload.thread_id === "number" ? f.payload.thread_id : null, title: null, kind: "new" });
      }
      if (f.event === "thread_continued") {
        setThreadInfo((prev) => ({
          ...prev,
          threadId: typeof f.payload.thread_id === "number" ? f.payload.thread_id : prev.threadId,
          title: typeof f.payload.title === "string" ? f.payload.title : prev.title,
          kind: "continuation",
        }));
      }
      if (f.event === "thread_resumed") {
        setThreadInfo({
          threadId: typeof f.payload.thread_id === "number" ? f.payload.thread_id : null,
          title: typeof f.payload.title === "string" ? f.payload.title : null,
          kind: "resumed",
        });
      }
      if (f.event === "thread_summary_updated") {
        setThreadInfo((prev) => ({
          ...prev,
          title: typeof f.payload.title === "string" ? f.payload.title : prev.title,
        }));
      }

      if (f.event === "agent_plan_created") {
        const steps = Array.isArray(f.payload.steps) ? (f.payload.steps as AgentStep[]) : [];
        setAgentPlan({ goal: typeof f.payload.goal === "string" ? f.payload.goal : "", steps });
      }
      if (f.event === "agent_step_started") {
        const idx = typeof f.payload.step_index === "number" ? f.payload.step_index : -1;
        setAgentPlan((prev) => {
          if (!prev) return prev;
          return { ...prev, steps: prev.steps.map((s) => s.index === idx ? { ...s, status: "in_progress" } : s) };
        });
      }
      if (f.event === "agent_step_done") {
        const idx = typeof f.payload.step_index === "number" ? f.payload.step_index : -1;
        const result = typeof f.payload.result_summary === "string" ? f.payload.result_summary : "";
        setAgentPlan((prev) => {
          if (!prev) return prev;
          return { ...prev, steps: prev.steps.map((s) => s.index === idx ? { ...s, status: "done", result } : s) };
        });
      }
      if (f.event === "agent_evaluation_done") {
        setTimeout(() => setAgentPlan(null), 8000);
      }

      setLog((prev) => [
        ...prev.slice(-40),
        `${new Date().toISOString().slice(11, 19)} ← ${f.event}`,
      ]);
    },
    [feedAudioChunk, duck, primeAudio, scheduleSubtitleClear],
  );

  const { status, sendFrame } = useWebSocket({
    connect: true,
    onFrame,
  });

  const push = useCallback((line: string) => {
    setLog((prev) => [...prev.slice(-40), `${new Date().toISOString().slice(11, 19)} ${line}`]);
  }, []);

  const fetchPersonas = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/personas`);
      if (!res.ok) return;
      const data = (await res.json()) as { personas: PersonaInfo[]; active: string };
      setPersonas(data.personas ?? []);
      setActivePersona(data.active ?? "aria");
    } catch {
      /* backend not yet available */
    }
  }, [apiBase]);

  const handleSendCommand = useCallback(
    (text: string) => {
      void primeAudio();
      stopAudio();
      sendFrame("chat_text", { text });
      // Optimistic observer state update
      if (/obserwuj|obserwator/i.test(text)) {
        setObserverActive(/zacznij|uruchom/i.test(text));
      }
      if (/persona/i.test(text)) {
        const m = /zmień personę na (\S+)/i.exec(text);
        if (m) {
          setActivePersona(m[1]);
          setTimeout(() => void fetchPersonas(), 500);
        }
      }
    },
    [sendFrame, stopAudio, primeAudio, fetchPersonas],
  );

  const wsReady = status === "open";

  useEffect(() => {
    if (!autoSessionReportPending || !wsReady) return;
    setAutoSessionReportPending(false);
    sendFrame("chat_text", { text: "podsumuj sesję" });
  }, [autoSessionReportPending, wsReady, sendFrame]);

  const [ttsDiag, setTtsDiag] = useState<{
    checked: boolean;
    available: boolean;
    resolvedYaml: string | null;
  }>({ checked: false, available: false, resolvedYaml: null });
  const [observerStatusHints, setObserverStatusHints] = useState<string[]>([]);

  useEffect(() => {
    window.assystent?.setTrayHealth?.(wsReady ? "ok" : "error");
  }, [wsReady]);

  useEffect(() => {
    if (dragHandleRef.current) {
      dragHandleRef.current.style.setProperty("-webkit-app-region", "drag");
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.key === "h") {
        setChatPanelVisible((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      const w = Math.max(window.innerWidth, 1);
      const h = Math.max(window.innerHeight, 1);
      const x = (e.clientX / w) * 2 - 1;
      const y = 1 - (e.clientY / h) * 2;
      setMouseNorm({ x: Math.max(-1, Math.min(1, x)), y: Math.max(-1, Math.min(1, y)) });
      setLastMouseMoveAtMs(Date.now());
    };
    const onLeave = () => setMouseNorm(null);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseleave", onLeave);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  useEffect(() => {
    window.assystent?.setOverlayScale?.(uiCfg.overlayScale);
  }, [uiCfg.overlayScale]);

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
          setObserverStatusHints(observerHintsFromStatusJson(data));
          window.assystent?.setTrayHealth?.("ok");
        }
      } catch {
        if (!cancelled) {
          setTtsDiag({ checked: false, available: false, resolvedYaml: null });
          setObserverStatusHints([]);
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
      setChatHistory((prev) => [...prev.slice(-99), { role: "user", content: t, timestamp: Date.now() }]);
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

  useEffect(() => {
    if (!wsReady) return undefined;
    void fetchPersonas();
    return undefined;
  }, [wsReady, fetchPersonas]);

  useEffect(() => {
    if (!wsReady) return;
    void (async () => {
      try {
        const res = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/threads?limit=1`);
        if (!res.ok) return;
        const data = (await res.json()) as { threads: Array<{ id: number; title: string | null; status: string; last_active_at: number }> };
        const latest = data.threads?.[0];
        if (!latest || latest.status !== "active") return;
        const nowSec = Math.floor(Date.now() / 1000);
        const ageMin = (nowSec - (latest.last_active_at ?? 0)) / 60;
        if (ageMin > 30) return;
        setThreadInfo({ threadId: latest.id, title: latest.title ?? null, kind: "continuation" });
      } catch {
        /* backend not yet ready */
      }
    })();
  }, [wsReady, apiBase]);

  useEffect(() => {
    if (!window.assystent?.getDisplays) return;
    void window.assystent.getDisplays().then((list) => {
      setDisplays(list);
      const primary = list.find((d) => d.isPrimary);
      if (primary && selectedDisplayId === null) setSelectedDisplayId(primary.id);
    }).catch(() => undefined);
  // run once on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
        setObserverStatusHints(observerHintsFromStatusJson(parsed));
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
        setObserverStatusHints(observerHintsFromStatusJson(payload));
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

  const handleSetDisplay = useCallback((id: number) => {
    setSelectedDisplayId(id);
    window.assystent?.setDisplay?.(id);
  }, []);

  const sharedConfigPanelProps = {
    wsStatus: status,
    profileWsActive: profileBanner !== null,
    vrmUrl,
    onVrmSave: saveVrmUrl,
    apiBaseUrl: apiBase,
    onApiBaseSave: saveApiBase,
    onFetchStatus: fetchStatus,
    statusJson,
    statusError,
    busyStatus,
    piperResourcesRoot: piperResourcesRootDraft,
    onPiperResourcesRootChange: setPiperResourcesRootDraft,
    piperExecutable: piperExecutableDraft,
    onPiperExecutableChange: setPiperExecutableDraft,
    selectedPiperVoiceId,
    onSelectedPiperVoiceIdChange: (id: string) => {
      setSelectedPiperVoiceId(id);
      if (typeof window !== "undefined") {
        localStorage.setItem(PIPER_VOICE_ID_LS, id);
      }
    },
    onApplyPiperVoice: applyPiperVoice,
    ttsVoiceSpeed,
    onTtsVoiceSpeedChange: setTtsVoiceSpeed,
    onApplyTtsSpeed: applyTtsSpeed,
    busyConfig,
    configMessage,
    observerActive,
    sleeping,
    silentMode,
    wsReady,
    onSendCommand: handleSendCommand,
    personas,
    activePersona,
    onRefreshPersonas: fetchPersonas,
    displays,
    selectedDisplayId,
    onSetDisplay: handleSetDisplay,
  };

  if (isConfigView) {
    return (
      <main style={{ ...layout, maxWidth: 680 }}>
        <h1 style={{ fontSize: "1.4rem", fontWeight: 600, margin: "0 0 1rem" }}>Konfiguracja Assystenta</h1>
        <ConfigPanel tab={configTab} onTab={setConfigTab} {...sharedConfigPanelProps} />
      </main>
    );
  }

  if (isElectron && !isConfigView) {
    const dotColor = sleeping
      ? "#eab308"
      : visualState === "speaking"
      ? "#22c55e"
      : visualState === "listening"
      ? "#3b82f6"
      : visualState === "thinking"
      ? "#f59e0b"
      : "#6b7280";
    const overlayBtnBase: React.CSSProperties = {
      padding: "0.3rem 0.65rem",
      borderRadius: 6,
      border: "1px solid #4a5568",
      background: "rgba(30,25,42,0.8)",
      color: "#b8afc8",
      fontSize: 12,
      cursor: "pointer",
      flexShrink: 0,
      userSelect: "none",
    };
    return (
      <div
        style={{
          position: "fixed",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          background: "transparent",
          userSelect: "none",
        }}
      >
        {/* Drag handle */}
        <div
          ref={dragHandleRef}
          title="Przeciągnij aby przesunąć okno"
          style={{
            height: 28,
            background: "rgba(10,8,18,0.45)",
            borderRadius: "10px 10px 0 0",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "grab",
            flexShrink: 0,
            color: "#5a5278",
            fontSize: 11,
            letterSpacing: "0.25rem",
          }}
        >
          ···
        </div>

        {/* Avatar + Chat panel row */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden", gap: 0 }}>

        {/* Avatar area */}
        <div style={{ position: "relative", flex: 1, overflow: "hidden" }}>
          <AvatarCanvas
            vrmUrl={vrmUrl}
            emotion={sleeping ? "neutral" : emotion}
            visualState={visualState}
            lipSyncLevel={isSpeaking ? mouthLevel : 0}
            breathingEnabled={uiCfg.avatarBreathingEnabled}
            statePosesEnabled={uiCfg.avatarStatePosesEnabled}
            lookAtEnabled={uiCfg.avatarLookAtEnabled}
            emotionIntensity={uiCfg.avatarEmotionIntensity}
            emotionCrossfadeSec={uiCfg.avatarEmotionCrossfadeSec}
            mouseNormalized={mouseNorm}
            lastMouseMoveAtMs={lastMouseMoveAtMs}
            containerStyle={{ width: "100%", height: "100%", background: "transparent", borderRadius: 0 }}
          />

          {/* Status dot */}
          <div
            style={{
              position: "absolute",
              top: 8,
              right: 10,
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: dotColor,
              boxShadow: `0 0 6px ${dotColor}`,
              pointerEvents: "none",
            }}
          />

          {/* Disconnection indicator */}
          {!wsReady ? (
            <div
              style={{
                position: "absolute",
                top: 8,
                left: "50%",
                transform: "translateX(-50%)",
                padding: "0.2rem 0.7rem",
                borderRadius: 6,
                background: "rgba(50,18,18,0.88)",
                border: "1px solid #7a3030",
                color: "#e898a8",
                fontSize: 11,
                pointerEvents: "none",
                whiteSpace: "nowrap",
              }}
            >
              Brak połączenia — łączenie…
            </div>
          ) : null}

          {/* Profile banner */}
          {profileBanner ? (
            <div
              style={{
                position: "absolute",
                top: 8,
                left: 8,
                right: 24,
                padding: "0.5rem 0.75rem",
                borderRadius: 8,
                border: "1px solid #6b5b3e",
                background: "rgba(212,168,90,0.14)",
                backdropFilter: "blur(4px)",
                color: "#f0e6d4",
                fontSize: 12,
                lineHeight: 1.4,
              }}
            >
              <strong style={{ color: "#f5d799" }}>{profileBanner.title}</strong>
              <div style={{ marginTop: "0.25rem" }}>{profileBanner.detail}</div>
              <button
                type="button"
                onClick={dismissProfileBanner}
                style={{
                  marginTop: "0.35rem",
                  padding: "0.2rem 0.5rem",
                  fontSize: 11,
                  borderRadius: 4,
                  border: "1px solid #6b5b3e",
                  background: "transparent",
                  color: "#c8a870",
                  cursor: "pointer",
                }}
              >
                Zamknij
              </button>
            </div>
          ) : null}

          {/* Text subtitle overlay */}
          {(assistantLine || observerLine) ? (
            <div
              style={{
                position: "absolute",
                bottom: 0,
                left: 0,
                right: 0,
                padding: "0.5rem 0.75rem",
                background: "rgba(10,8,18,0.68)",
                color: "#eae6f8",
                fontSize: 14,
                lineHeight: 1.5,
                textAlign: "center",
                pointerEvents: "none",
              }}
            >
              {assistantLine ?? observerLine}
            </div>
          ) : null}

          {/* PTT error toast */}
          {pttError ? (
            <div
              style={{
                position: "absolute",
                top: 36,
                left: 8,
                right: 8,
                padding: "0.4rem 0.65rem",
                borderRadius: 6,
                background: "rgba(50,18,18,0.88)",
                border: "1px solid #7a3030",
                color: "#e898a8",
                fontSize: 12,
                lineHeight: 1.4,
              }}
            >
              {pttError}
            </div>
          ) : null}
        </div>

        {/* Chat history panel */}
        {chatPanelVisible ? (
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "flex-end", padding: "0.3rem 0.3rem 0.3rem 0" }}>
            <ChatHistoryPanel
              messages={chatHistory}
              thread={threadInfo}
              agentPlan={agentPlan}
              assistantName="Aria"
              maxMessages={6}
              opacity={0.85}
              width={280}
            />
          </div>
        ) : null}

        </div>{/* end Avatar + Chat panel row */}

        {/* Bottom control bar */}
        <div
          style={{
            background: "rgba(10,8,18,0.78)",
            backdropFilter: "blur(8px)",
            display: "flex",
            flexDirection: "column",
            flexShrink: 0,
            borderRadius: "0 0 10px 10px",
          }}
        >
        {overlayInputOpen ? (
          <div
            style={{
              display: "flex",
              gap: "0.3rem",
              padding: "0.4rem 0.45rem 0",
            }}
          >
            <input
              // eslint-disable-next-line jsx-a11y/no-autofocus
              autoFocus
              type="text"
              value={overlayDraft}
              onChange={(e) => setOverlayDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  const t = overlayDraft.trim();
                  if (t && wsReady) {
                    void primeAudio();
                    stopAudio();
                    sendFrame("chat_text", { text: t });
                    setChatHistory((prev) => [...prev.slice(-99), { role: "user", content: t, timestamp: Date.now() }]);
                    setOverlayDraft("");
                    setOverlayInputOpen(false);
                  }
                }
                if (e.key === "Escape") {
                  setOverlayInputOpen(false);
                  setOverlayDraft("");
                }
              }}
              placeholder="Napisz… (Enter wyślij, Esc zamknij)"
              disabled={!wsReady}
              style={{
                flex: 1,
                padding: "0.35rem 0.55rem",
                borderRadius: 6,
                border: "1px solid #4a3f62",
                background: "rgba(15,12,22,0.92)",
                color: "#eae6f8",
                fontSize: 13,
                fontFamily: "inherit",
                outline: "none",
              }}
            />
            <button
              type="button"
              disabled={!wsReady || !overlayDraft.trim()}
              onClick={() => {
                const t = overlayDraft.trim();
                if (t && wsReady) {
                  void primeAudio();
                  stopAudio();
                  sendFrame("chat_text", { text: t });
                  setChatHistory((prev) => [...prev.slice(-99), { role: "user", content: t, timestamp: Date.now() }]);
                  setOverlayDraft("");
                  setOverlayInputOpen(false);
                }
              }}
              style={{
                ...overlayBtnBase,
                borderColor: "#5c4d8c",
                background: "#2c2440",
                color: "#e8e4f0",
              }}
            >
              Wyślij
            </button>
          </div>
        ) : null}
        <div
          style={{
            height: 50,
            display: "flex",
            alignItems: "center",
            paddingLeft: "0.45rem",
            paddingRight: "0.45rem",
            gap: "0.3rem",
          }}
        >
          {/* PTT */}
          <button
            type="button"
            disabled={!wsReady || pttBusy}
            onPointerDown={(e) => {
              if (!wsReady || pttBusy) return;
              if (e.pointerType === "mouse" && e.button !== 0) return;
              e.preventDefault();
              const el = e.currentTarget;
              if (el instanceof HTMLElement) { try { el.setPointerCapture(e.pointerId); } catch { /* ignore */ } }
              handlePttDown();
            }}
            onPointerUp={(e) => {
              if (e.pointerType === "mouse" && e.button !== 0) return;
              e.preventDefault();
              const el = e.currentTarget;
              if (el instanceof HTMLElement) { try { if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId); } catch { /* ignore */ } }
              handlePttUp();
            }}
            onPointerCancel={(e) => {
              const el = e.currentTarget;
              if (el instanceof HTMLElement) { try { if (el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId); } catch { /* ignore */ } }
              handlePttUp();
            }}
            style={{
              ...overlayBtnBase,
              borderColor: "#5c4d8c",
              background: pttBusy ? "rgba(44,36,64,0.9)" : "#2c2440",
              color: "#e8e4f0",
              padding: "0.3rem 0.8rem",
              touchAction: "manipulation",
            }}
          >
            {pttBusy ? "..." : "PTT"}
          </button>

          {/* Sleep/wake */}
          <button
            type="button"
            disabled={!wsReady}
            onClick={() => sendFrame("chat_text", { text: sleeping ? "obudź się" : "idź spać" })}
            style={{
              ...overlayBtnBase,
              borderColor: sleeping ? "#7a6b3e" : "#4a5568",
              background: sleeping ? "rgba(122,107,62,0.25)" : "rgba(30,25,42,0.8)",
              color: sleeping ? "#d4b86a" : "#b8afc8",
            }}
          >
            {sleeping ? "Obudź" : "Śpij"}
          </button>

          {/* Silent mode */}
          <button
            type="button"
            disabled={!wsReady}
            onClick={() => sendFrame("chat_text", { text: silentMode ? "możesz mówić" : "wycisz się" })}
            style={{
              ...overlayBtnBase,
              borderColor: silentMode ? "#4a7b9b" : "#4a5568",
              background: silentMode ? "rgba(74,123,155,0.25)" : "rgba(30,25,42,0.8)",
              color: silentMode ? "#7ab8d4" : "#b8afc8",
            }}
          >
            {silentMode ? "Cichy: WŁ" : "WYŁ"}
          </button>

          {/* Click-through */}
          <button
            type="button"
            onClick={() => {
              const next = !clickThrough;
              window.assystent?.setClickThrough?.(next);
              setClickThrough(next);
            }}
            style={{
              ...overlayBtnBase,
              borderColor: clickThrough ? "#4a9b6f" : "#4a5568",
              background: clickThrough ? "rgba(74,155,111,0.25)" : "rgba(30,25,42,0.8)",
              color: clickThrough ? "#7dd4a8" : "#b8afc8",
            }}
          >
            {clickThrough ? "Klik: WŁ" : "Klik: WYŁ"}
          </button>

          {/* Text input toggle */}
          <button
            type="button"
            onClick={() => { setOverlayInputOpen((v) => !v); setOverlayDraft(""); }}
            style={{
              ...overlayBtnBase,
              borderColor: overlayInputOpen ? "#6b4d9b" : "#4a5568",
              background: overlayInputOpen ? "rgba(74,36,120,0.28)" : "rgba(30,25,42,0.8)",
              color: overlayInputOpen ? "#c8a8f0" : "#b8afc8",
              padding: "0.3rem 0.55rem",
            }}
            title="Wpisz wiadomość tekstową"
          >
            ✎
          </button>

          <div style={{ flex: 1 }} />

          {/* Chat panel toggle */}
          <button
            type="button"
            onClick={() => setChatPanelVisible((v) => !v)}
            style={{
              ...overlayBtnBase,
              borderColor: chatPanelVisible ? "#5c4d8c" : "#4a5568",
              background: chatPanelVisible ? "rgba(44,36,64,0.7)" : "rgba(30,25,42,0.8)",
              color: chatPanelVisible ? "#c8a8f0" : "#b8afc8",
              padding: "0.3rem 0.55rem",
            }}
            title="Panel czatu (Alt+H)"
          >
            💬
          </button>

          {/* Config window */}
          <button
            type="button"
            onClick={() => window.assystent?.openConfigWindow?.()}
            style={{
              ...overlayBtnBase,
              padding: "0.3rem 0.6rem",
              color: "#9a93b0",
            }}
            title="Otwórz konfigurację"
          >
            ⚙
          </button>
        </div>
        </div>
      </div>
    );
  }

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
          <div
            ref={dragHandleRef}
            title="Przeciągnij aby przesunąć okno"
            style={{
              height: "1.25rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              userSelect: "none",
              color: "#3a3550",
              fontSize: 11,
              letterSpacing: "0.3rem",
              marginBottom: "0.25rem",
              borderRadius: 4,
              cursor: "grab",
            }}
          >
            ···
          </div>
          <AvatarCanvas
            vrmUrl={vrmUrl}
            emotion={emotion}
            visualState={visualState}
            lipSyncLevel={isSpeaking ? mouthLevel : 0}
            breathingEnabled={uiCfg.avatarBreathingEnabled}
            statePosesEnabled={uiCfg.avatarStatePosesEnabled}
            lookAtEnabled={uiCfg.avatarLookAtEnabled}
            emotionIntensity={uiCfg.avatarEmotionIntensity}
            emotionCrossfadeSec={uiCfg.avatarEmotionCrossfadeSec}
            mouseNormalized={mouseNorm}
            lastMouseMoveAtMs={lastMouseMoveAtMs}
          />
          <p style={{ margin: "0.5rem 0 0", fontSize: 12, color: "#8a8198" }}>
            Emocja (z WS): <strong style={{ color: "#d4ccec" }}>{emotion}</strong>
            {isSpeaking ? " · odtwarzanie TTS (lip-sync)" : ""}
          </p>
          <div
            style={{
              marginTop: "0.45rem",
              maxWidth: 560,
              padding: "0.5rem 0.65rem",
              borderRadius: 8,
              border: "1px solid #2f2840",
              background: "rgba(20, 17, 32, 0.55)",
            }}
          >
            <label htmlFor="assystent-tts-volume" style={{ fontSize: 12, color: "#9a93b0", display: "block", marginBottom: "0.35rem" }}>
              Głośność odpowiedzi (TTS)
              {outputDeviceId ? ` — ${speakerDevices.find((d) => d.deviceId === outputDeviceId)?.label ?? outputDeviceId}` : " — domyślne urządzenie audio systemu"}
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
              <input
                id="assystent-tts-volume"
                type="range"
                min={0}
                max={100}
                value={Math.round(outputVolume * 100)}
                onChange={(e) => setOutputVolume(Number(e.target.value) / 100)}
                style={{ flex: 1, accentColor: "#9b7fd6" }}
              />
              <span style={{ fontSize: 13, color: "#c8c0dc", minWidth: "2.75rem", textAlign: "right" }}>
                {Math.round(outputVolume * 100)}%
              </span>
            </div>
          </div>
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
              <div style={{ fontSize: 13, color: "#6d7a88", lineHeight: 1.45 }}>
                <div>Brak ostatniego komentarza — to nie błąd samego UI.</div>
                <div style={{ marginTop: "0.35rem" }}>
                  Tu pojawia się treść dopiero po zdarzeniu WebSocket <code style={{ fontSize: 11 }}>observer_comment</code>. Backend wysyła je
                  tylko gdy obserwator jest włączony (np. „zacznij obserwować”), gra jest wykryta, nie trwa nagrywanie PTT, a po analizie ekranu
                  model uzna zmianę za istotną — przy rutynie zwraca <code style={{ fontSize: 11 }}>[SKIP]</code> i nic nie leci do klienta.
                </div>
                {observerStatusHints.length ? (
                  <ul
                    style={{
                      margin: "0.4rem 0 0",
                      paddingLeft: "1.1rem",
                      fontSize: 12,
                      color: "#c89880",
                      lineHeight: 1.45,
                    }}
                  >
                    {observerStatusHints.map((h, i) => (
                      <li key={`${i}-${h.slice(0, 24)}`}>{h}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
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

            <div style={{ marginBottom: "0.75rem" }}>
              <label htmlFor="assystent-mic-select" style={{ display: "block", marginBottom: "0.3rem", fontSize: 12, color: "#9a93b0" }}>
                Mikrofon wejściowy (PTT)
              </label>
              <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                <select
                  id="assystent-mic-select"
                  value={micDeviceId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setMicDeviceId(id);
                    localStorage.setItem(MIC_DEVICE_STORAGE_KEY, id);
                  }}
                  style={{
                    flex: 1,
                    maxWidth: 320,
                    padding: "0.35rem 0.5rem",
                    borderRadius: 6,
                    border: "1px solid #3d3550",
                    background: "#120f18",
                    color: "#e8e4f0",
                    fontSize: 12,
                  }}
                >
                  <option value="">Domyślny mikrofon systemu</option>
                  {micDevices.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label}</option>
                  ))}
                </select>
                <button type="button" onClick={() => void refreshMicDevices()} style={btnMuted} title="Odśwież listę urządzeń">
                  ↺
                </button>
              </div>
            </div>

            {speakerDevices.length > 0 ? (
              <div style={{ marginBottom: "0.75rem" }}>
                <label htmlFor="assystent-speaker-select" style={{ display: "block", marginBottom: "0.3rem", fontSize: 12, color: "#9a93b0" }}>
                  Głośniki wyjściowe (TTS)
                </label>
                <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                  <select
                    id="assystent-speaker-select"
                    value={outputDeviceId}
                    onChange={(e) => {
                      const id = e.target.value;
                      setOutputDeviceId(id);
                      localStorage.setItem(SPEAKER_DEVICE_STORAGE_KEY, id);
                    }}
                    style={{
                      flex: 1,
                      maxWidth: 320,
                      padding: "0.35rem 0.5rem",
                      borderRadius: 6,
                      border: "1px solid #3d3550",
                      background: "#120f18",
                      color: "#e8e4f0",
                      fontSize: 12,
                    }}
                  >
                    <option value="">Domyślne głośniki systemu</option>
                    {speakerDevices.map((d) => (
                      <option key={d.deviceId} value={d.deviceId}>{d.label}</option>
                    ))}
                  </select>
                </div>
              </div>
            ) : null}

            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
              <button
                type="button"
                disabled={!wsReady}
                onClick={() => sendFrame("chat_text", { text: sleeping ? "obudź się" : "idź spać" })}
                title={sleeping ? "Asystent śpi — kliknij aby obudzić" : "Kliknij aby uśpić asystenta"}
                style={{
                  ...btnSecondary,
                  borderColor: sleeping ? "#7a6b3e" : "#4a5568",
                  background: sleeping ? "rgba(122,107,62,0.18)" : undefined,
                  color: sleeping ? "#d4b86a" : undefined,
                }}
              >
                {sleeping ? "Obudź" : "Śpij"}
              </button>
              <button
                type="button"
                disabled={!wsReady}
                onClick={() => sendFrame("chat_text", { text: silentMode ? "możesz mówić" : "wycisz się" })}
                title={silentMode ? "Tryb cichy — asystent pokazuje tekst zamiast mówić (kliknij aby wyłączyć)" : "Kliknij aby włączyć tryb cichy"}
                style={{
                  ...btnSecondary,
                  borderColor: silentMode ? "#4a7b9b" : "#4a5568",
                  background: silentMode ? "rgba(74,123,155,0.18)" : undefined,
                  color: silentMode ? "#7ab8d4" : undefined,
                }}
              >
                Cichy: {silentMode ? "WŁ" : "WYŁ"}
              </button>
              <button
                type="button"
                onClick={() => {
                  const next = !clickThrough;
                  window.assystent?.setClickThrough?.(next);
                  setClickThrough(next);
                }}
                title={clickThrough ? "Kliknięcia przechodzą przez awatar (kliknij aby wyłączyć)" : "Awatar blokuje kliknięcia (kliknij aby włączyć klik-przez)"}
                style={{
                  ...btnSecondary,
                  borderColor: clickThrough ? "#4a9b6f" : "#4a5568",
                  background: clickThrough ? "rgba(74,155,111,0.18)" : undefined,
                  color: clickThrough ? "#7dd4a8" : undefined,
                }}
              >
                Klik-przez: {clickThrough ? "WŁ" : "WYŁ"}
              </button>
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

        <ConfigPanel tab={configTab} onTab={setConfigTab} {...sharedConfigPanelProps} />
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
        {" · "}
        {window.assystent?.openConfigWindow ? (
          <button
            type="button"
            onClick={() => window.assystent?.openConfigWindow?.()}
            style={btnMuted}
          >
            ⚙ Konfiguracja
          </button>
        ) : null}
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
