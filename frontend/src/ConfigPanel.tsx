import React, { useState } from "react";
import {
  BUNDLED_VRM_FILENAMES,
  BUNDLED_VRM_SELECT_OTHER,
  bundledFilenameFromStoredUrl,
  bundledSelectValueForUrl,
  bundledVrmRelativeUrl,
} from "./vrmBundledCatalog";
import { BUNDLED_PIPER_VOICES } from "./piperVoicesCatalog";

export type ConfigTabId = "connection" | "avatar" | "observer" | "persona" | "more";

export interface PersonaInfo {
  id: string;
  display_name: string;
}

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
  piperResourcesRoot: string;
  onPiperResourcesRootChange: (v: string) => void;
  piperExecutable: string;
  onPiperExecutableChange: (v: string) => void;
  selectedPiperVoiceId: string;
  onSelectedPiperVoiceIdChange: (v: string) => void;
  onApplyPiperVoice: () => Promise<void>;
  ttsVoiceSpeed: string;
  onTtsVoiceSpeedChange: (v: string) => void;
  onApplyTtsSpeed: () => Promise<void>;
  busyConfig: boolean;
  configMessage: string | null;
  // Observer tab
  observerActive?: boolean;
  sleeping?: boolean;
  silentMode?: boolean;
  wsReady?: boolean;
  onSendCommand?: (text: string) => void;
  // Persona tab
  personas?: PersonaInfo[];
  activePersona?: string;
  onRefreshPersonas?: () => void;
}

const tabs: { id: ConfigTabId; label: string }[] = [
  { id: "connection", label: "Połączenie" },
  { id: "avatar", label: "Avatar" },
  { id: "observer", label: "Obserwator" },
  { id: "persona", label: "Persona" },
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
  piperResourcesRoot,
  onPiperResourcesRootChange,
  piperExecutable,
  onPiperExecutableChange,
  selectedPiperVoiceId,
  onSelectedPiperVoiceIdChange,
  onApplyPiperVoice,
  ttsVoiceSpeed,
  onTtsVoiceSpeedChange,
  onApplyTtsSpeed,
  busyConfig,
  configMessage,
  observerActive = false,
  sleeping = false,
  silentMode = false,
  wsReady = false,
  onSendCommand,
  personas = [],
  activePersona = "aria",
  onRefreshPersonas,
}: ConfigPanelProps) {
  const [draftVrm, setDraftVrm] = useState(vrmUrl);
  const [draftApi, setDraftApi] = useState(apiBaseUrl);
  const [intervalDraft, setIntervalDraft] = useState("30");

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
          <label htmlFor="vrm-bundled" style={{ display: "block", marginBottom: "0.35rem" }}>
            Model z <code style={{ fontSize: 12 }}>resources/</code>
          </label>
          <select
            id="vrm-bundled"
            value={bundledSelectValueForUrl(draftVrm)}
            onChange={(e) => {
              const v = e.target.value;
              if (v === BUNDLED_VRM_SELECT_OTHER) {
                setDraftVrm((prev) => (bundledFilenameFromStoredUrl(prev) ? "" : prev));
              } else {
                setDraftVrm(bundledVrmRelativeUrl(v));
              }
            }}
            style={{ ...inputStyle, cursor: "pointer", marginBottom: "0.75rem" }}
          >
            {BUNDLED_VRM_FILENAMES.map((fn) => (
              <option key={fn} value={fn}>
                {fn.replace(/\.vrm$/i, "")}
              </option>
            ))}
            <option value={BUNDLED_VRM_SELECT_OTHER}>Inny adres URL…</option>
          </select>
          {bundledSelectValueForUrl(draftVrm) === BUNDLED_VRM_SELECT_OTHER && (
            <>
              <label htmlFor="vrm-url" style={{ display: "block", marginBottom: "0.35rem" }}>
                Własny URL modelu VRM
              </label>
              <input
                id="vrm-url"
                type="url"
                value={draftVrm}
                onChange={(e) => setDraftVrm(e.target.value)}
                placeholder="https://…/model.vrm"
                style={inputStyle}
              />
            </>
          )}
          <p style={{ margin: "0.6rem 0 0", fontSize: 12, color: "#8a8198" }}>
            Modele z aplikacji: <code>./nazwa.vrm</code> (katalog <code>frontend/resources</code>).
          </p>
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

      {tab === "observer" && (
        <div style={{ fontSize: 14, lineHeight: 1.6 }}>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span
                style={{
                  display: "inline-block",
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: observerActive ? "#22c55e" : "#6b7280",
                  boxShadow: observerActive ? "0 0 5px #22c55e" : "none",
                }}
              />
              <span style={{ color: "#b8afc8", fontSize: 13 }}>
                {observerActive ? "Obserwator aktywny" : "Obserwator zatrzymany"}
              </span>
            </div>
            {sleeping ? (
              <span style={{ fontSize: 12, color: "#d4b86a", padding: "0.1rem 0.45rem", borderRadius: 4, border: "1px solid #7a6b3e", background: "rgba(122,107,62,0.18)" }}>
                Asystent śpi
              </span>
            ) : null}
            {silentMode ? (
              <span style={{ fontSize: 12, color: "#7ab8d4", padding: "0.1rem 0.45rem", borderRadius: 4, border: "1px solid #4a7b9b", background: "rgba(74,123,155,0.18)" }}>
                Tryb cichy
              </span>
            ) : null}
          </div>

          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", marginBottom: "1rem" }}>
            <button
              type="button"
              disabled={!wsReady}
              onClick={() => onSendCommand?.(observerActive ? "przestań obserwować" : "zacznij obserwować")}
              style={observerActive ? { ...btnPrimary, background: "#3d2a2a", borderColor: "#7a3a3a" } : btnPrimary}
            >
              {observerActive ? "Zatrzymaj obserwatora" : "Uruchom obserwatora"}
            </button>
            <button
              type="button"
              disabled={!wsReady}
              onClick={() => onSendCommand?.(sleeping ? "obudź się" : "idź spać")}
              style={{ ...btnPrimary, background: sleeping ? "#2a2a1e" : "#1e2a2a", borderColor: sleeping ? "#7a7a3a" : "#3a5a5a" }}
            >
              {sleeping ? "Obudź" : "Śpij"}
            </button>
            <button
              type="button"
              disabled={!wsReady}
              onClick={() => onSendCommand?.(silentMode ? "możesz mówić" : "wycisz się")}
              style={{ ...btnPrimary, background: silentMode ? "#1e2a34" : "#1e2a2a", borderColor: silentMode ? "#4a7b9b" : "#3a5a5a" }}
            >
              {silentMode ? "Wyłącz tryb cichy" : "Włącz tryb cichy"}
            </button>
          </div>

          <div style={{ marginBottom: "0.75rem" }}>
            <label style={{ display: "block", marginBottom: "0.3rem", fontSize: 13, color: "#b8afc8" }}>
              Interwał obserwatora (sekundy)
            </label>
            <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
              <input
                type="number"
                min={5}
                max={600}
                value={intervalDraft}
                onChange={(e) => setIntervalDraft(e.target.value)}
                style={{ ...inputStyle, maxWidth: 100 }}
              />
              <button
                type="button"
                disabled={!wsReady}
                onClick={() => {
                  const n = parseInt(intervalDraft, 10);
                  if (!Number.isNaN(n) && n >= 5) {
                    onSendCommand?.(`ustaw interwał na ${n} sekund`);
                  }
                }}
                style={btnPrimary}
              >
                Ustaw
              </button>
            </div>
            <p style={{ margin: "0.3rem 0 0", fontSize: 12, color: "#6d6680" }}>
              Komenda: <code style={{ fontSize: 11 }}>ustaw interwał na N sekund</code>. Minimum 5s.
            </p>
          </div>
        </div>
      )}

      {tab === "persona" && (
        <div style={{ fontSize: 14, lineHeight: 1.6 }}>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.75rem" }}>
            <span style={{ fontSize: 13, color: "#b8afc8" }}>
              Aktywna: <strong style={{ color: "#d4ccec" }}>{activePersona}</strong>
            </span>
            <button type="button" onClick={() => onRefreshPersonas?.()} style={{ ...btnPrimary, padding: "0.25rem 0.6rem", fontSize: 12 }}>
              ↺ Odśwież
            </button>
          </div>

          {personas.length === 0 ? (
            <p style={{ color: "#7a7390", fontSize: 13 }}>
              Brak plików person w <code style={{ fontSize: 11 }}>personas/</code>. Dodaj plik <code style={{ fontSize: 11 }}>aria.md</code> z frontmatter YAML.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              {personas.map((p) => (
                <div
                  key={p.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "0.45rem 0.7rem",
                    borderRadius: 7,
                    border: `1px solid ${p.id === activePersona ? "#8b7bb8" : "#2a2438"}`,
                    background: p.id === activePersona ? "#2a2438" : "#100d18",
                  }}
                >
                  <div>
                    <span style={{ color: "#e8e4f0", fontWeight: p.id === activePersona ? 600 : 400 }}>{p.display_name}</span>
                    <span style={{ marginLeft: "0.5rem", fontSize: 12, color: "#6d6680" }}>{p.id}</span>
                    {p.id === activePersona ? (
                      <span style={{ marginLeft: "0.4rem", fontSize: 11, color: "#9b7fd6" }}>● aktywna</span>
                    ) : null}
                  </div>
                  {p.id !== activePersona ? (
                    <button
                      type="button"
                      disabled={!wsReady}
                      onClick={() => onSendCommand?.(`zmień personę na ${p.id}`)}
                      style={{ ...btnPrimary, padding: "0.25rem 0.65rem", fontSize: 12 }}
                    >
                      Aktywuj
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          )}
          <p style={{ margin: "0.75rem 0 0", fontSize: 12, color: "#6d6680" }}>
            Pliki person: <code style={{ fontSize: 11 }}>{"{content_root}"}/personas/*.md</code>. Zmiany pliku wczytają się bez restartu.
          </p>
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

          <p style={{ margin: "1rem 0 0.35rem", color: "#e8e4f0" }}>TTS — głos Piper (model ONNX)</p>
          <p style={{ margin: 0, fontSize: 12, color: "#8a8198", lineHeight: 1.5 }}>
            Wpisz <strong>absolutną</strong> ścieżkę do katalogu <code style={{ fontSize: 11 }}>frontend/resources</code>{" "}
            w tym klone (tam są <code style={{ fontSize: 11 }}>piper-voices/…</code>). Wybierz głosu i wyślij do
            backendu — zapis jak przy prędkości TTS (<code style={{ fontSize: 11 }}>config.yaml</code> +
            token). Modele ONNX nie są commitowane w gicie — przy braku plików:{" "}
            <code style={{ fontSize: 11 }}>scripts/sync-piper-voices.ps1</code>.
          </p>
          <label htmlFor="piper-resources-root" style={{ display: "block", marginTop: "0.5rem", marginBottom: "0.25rem", fontSize: 13 }}>
            Katalog resources (abs.)
          </label>
          <input
            id="piper-resources-root"
            type="text"
            value={piperResourcesRoot}
            onChange={(e) => onPiperResourcesRootChange(e.target.value)}
            placeholder="np. C:\code\_repos\antigravity\assystent\frontend\resources"
            autoCorrect="off"
            spellCheck={false}
            style={inputStyle}
          />
          <label htmlFor="piper-exe" style={{ display: "block", marginTop: "0.5rem", marginBottom: "0.25rem", fontSize: 13 }}>
            Piper — opcjonalnie pełna ścieżka do <code style={{ fontSize: 11 }}>piper.exe</code>
          </label>
          <input
            id="piper-exe"
            type="text"
            value={piperExecutable}
            onChange={(e) => onPiperExecutableChange(e.target.value)}
            placeholder="Jeśli puste — używana jest nazwa piper z PATH"
            autoCorrect="off"
            spellCheck={false}
            style={inputStyle}
          />
          <label htmlFor="piper-voice" style={{ display: "block", marginTop: "0.5rem", marginBottom: "0.25rem", fontSize: 13 }}>
            Głos
          </label>
          <select
            id="piper-voice"
            value={selectedPiperVoiceId}
            onChange={(e) => onSelectedPiperVoiceIdChange(e.target.value)}
            style={{ ...inputStyle, cursor: "pointer", marginBottom: "0.5rem" }}
          >
            {BUNDLED_PIPER_VOICES.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
          </select>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              onClick={() => void onApplyPiperVoice()}
              disabled={busyConfig}
              style={btnPrimary}
            >
              {busyConfig ? "Wysyłanie…" : "Zastosuj głos TTS"}
            </button>
          </div>

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
