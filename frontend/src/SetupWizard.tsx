import React, { useCallback, useState } from "react";

export const SETUP_WIZARD_STORAGE_KEY = "assystent.setupWizardDone";

export function hasSetupWizardDismissed(): boolean {
  if (typeof window === "undefined") {
    return true;
  }
  return Boolean(localStorage.getItem(SETUP_WIZARD_STORAGE_KEY));
}

interface SetupWizardProps {
  apiBase: string;
  onFinish: () => void;
  onOpenConnectionSettings: () => void;
}

export function SetupWizard({ apiBase, onFinish, onOpenConnectionSettings }: SetupWizardProps) {
  const [step, setStep] = useState(0);
  const [checkError, setCheckError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [healthOk, setHealthOk] = useState<boolean | null>(null);

  const runCheck = useCallback(async () => {
    setChecking(true);
    setCheckError(null);
    setHealthOk(null);
    try {
      const res = await fetch(`${apiBase}/api/v1/health`);
      if (!res.ok) {
        setHealthOk(false);
        setCheckError(`HTTP ${res.status}`);
        return;
      }
      const j = (await res.json()) as { status?: string };
      setHealthOk(j.status === "healthy" || j.status === "degraded");
    } catch (e) {
      setHealthOk(false);
      setCheckError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  }, [apiBase]);

  const finish = useCallback(() => {
    localStorage.setItem(SETUP_WIZARD_STORAGE_KEY, "1");
    onFinish();
  }, [onFinish]);

  return (
    <div
      role="dialog"
      aria-labelledby="wizard-title"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(8, 6, 14, 0.82)",
        display: "grid",
        placeItems: "center",
        zIndex: 1000,
        padding: "1rem",
      }}
    >
      <div
        style={{
          maxWidth: 440,
          width: "100%",
          borderRadius: 12,
          border: "1px solid #3d3550",
          background: "#141018",
          color: "#e8e4f0",
          padding: "1.35rem 1.5rem",
          boxShadow: "0 20px 50px rgba(0,0,0,0.45)",
        }}
      >
        <h2 id="wizard-title" style={{ margin: "0 0 0.75rem", fontSize: "1.2rem" }}>
          Konfiguracja startowa
        </h2>

        {step === 0 && (
          <div style={{ fontSize: 14, lineHeight: 1.55, color: "#c8c0dc" }}>
            <p style={{ margin: "0 0 1rem" }}>
              Krótki kreator: sprawdzenie backendu i wskazówki do połączenia. Możesz pominąć i wrócić później w panelu po prawej.
            </p>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button type="button" onClick={() => setStep(1)} style={btnPrimary}>
                Dalej
              </button>
              <button type="button" onClick={finish} style={btnGhost}>
                Pomiń
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div style={{ fontSize: 14, lineHeight: 1.55, color: "#c8c0dc" }}>
            <p style={{ margin: "0 0 0.5rem" }}>
              Backend HTTP: <code style={{ fontSize: 12, color: "#d4ccec" }}>{apiBase}</code>
            </p>
            <button type="button" onClick={() => void runCheck()} disabled={checking} style={btnPrimary}>
              {checking ? "Sprawdzanie…" : "Sprawdź /api/v1/health"}
            </button>
            {healthOk === true && (
              <p style={{ margin: "0.75rem 0 0", color: "#a8e0c8" }}>Połączenie OK.</p>
            )}
            {healthOk === false && checkError && (
              <p style={{ margin: "0.75rem 0 0", color: "#f0a8a8" }}>{checkError}</p>
            )}
            {healthOk === false && !checkError && (
              <p style={{ margin: "0.75rem 0 0", color: "#f0c8a8" }}>Serwer nie odpowiada poprawnie.</p>
            )}
            <p style={{ margin: "1rem 0 0", fontSize: 12, color: "#8a8198" }}>
              Jeśli URL jest zły — <button type="button" onClick={onOpenConnectionSettings} style={linkBtn}>otwórz ustawienia połączenia</button>.
            </p>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", flexWrap: "wrap" }}>
              <button type="button" onClick={() => setStep(2)} style={btnPrimary}>
                Dalej
              </button>
              <button type="button" onClick={() => setStep(0)} style={btnGhost}>
                Wstecz
              </button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div style={{ fontSize: 14, lineHeight: 1.55, color: "#c8c0dc" }}>
            <p style={{ margin: "0 0 0.75rem" }}>
              W zakładce <strong>Avatar</strong> ustaw URL pliku VRM (HTTPS z nagłówkami CORS lub host lokalny). WebSocket domyślnie wskazuje na port <strong>8000</strong>.
            </p>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button type="button" onClick={finish} style={btnPrimary}>
                Zakończ
              </button>
              <button type="button" onClick={() => setStep(1)} style={btnGhost}>
                Wstecz
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const btnPrimary: React.CSSProperties = {
  padding: "0.45rem 1rem",
  borderRadius: 6,
  border: "1px solid #6b5a9e",
  background: "#4a3d6e",
  color: "#fff",
  cursor: "pointer",
  fontSize: 13,
};

const btnGhost: React.CSSProperties = {
  padding: "0.45rem 1rem",
  borderRadius: 6,
  border: "1px solid #3d3550",
  background: "#1a1525",
  color: "#e8e4f0",
  cursor: "pointer",
  fontSize: 13,
};

const linkBtn: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "#b8a8e8",
  cursor: "pointer",
  textDecoration: "underline",
  padding: 0,
  font: "inherit",
};
