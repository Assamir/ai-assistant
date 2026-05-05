/** Bazowy URL HTTP backendu (bez końcowego /). */
const DEFAULT_API_BASE = "http://127.0.0.1:8000";

/**
 * Naprawia m.in. `file://127.0.0.1:8000` (powstaje gdy `readApiBaseUrl` bierze
 * `window.location.protocol === "file:"` w Electronie) oraz dodaje `http://` gdy brak schematu.
 */
export function normalizeApiBaseUrl(raw: string): string {
  let u = raw.trim().replace(/\/$/, "");
  if (!u) {
    return DEFAULT_API_BASE;
  }
  const lower = u.toLowerCase();
  if (lower.startsWith("file://")) {
    let rest = u.slice("file://".length).replace(/^\/+/, "");
    if (/^[A-Za-z]:[\\/]/.test(rest)) {
      return DEFAULT_API_BASE;
    }
    rest = rest.replace(/^\/\//, "");
    if (/^[\w.]+(:\d+)?$/.test(rest)) {
      return `http://${rest}`;
    }
    return DEFAULT_API_BASE;
  }
  if (!/^https?:\/\//i.test(u)) {
    return `http://${u.replace(/^\/+/, "")}`;
  }
  return u;
}

export function readApiBaseUrl(): string {
  if (typeof window !== "undefined" && window.assystent?.apiUrl?.trim()) {
    return normalizeApiBaseUrl(window.assystent.apiUrl.trim());
  }
  const env = import.meta.env.VITE_API_BASE_URL?.trim();
  if (env) {
    return normalizeApiBaseUrl(env);
  }
  if (typeof window !== "undefined") {
    const proto = window.location.protocol;
    const host = window.location.hostname || "127.0.0.1";
    if (proto === "http:" || proto === "https:") {
      return normalizeApiBaseUrl(`${proto}//${host}:8000`);
    }
  }
  return DEFAULT_API_BASE;
}

/** Nagłówki dla `PUT /api/v1/config` gdy backend ma `ASSYSTENT_CONFIG_PUT_TOKEN`. */
export function configPutHeaders(): Record<string, string> {
  const fromEnv = import.meta.env.VITE_CONFIG_PUT_TOKEN?.trim();
  const fromBridge =
    typeof window !== "undefined" ? window.assystent?.configPutToken?.trim() : undefined;
  const fromStorage =
    typeof window !== "undefined"
      ? localStorage.getItem("assystent.configPutToken")?.trim()
      : undefined;
  const token = (fromEnv || fromBridge || fromStorage || "") as string;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["X-Config-Put-Token"] = token;
  }
  return headers;
}
