/** Bazowy URL HTTP backendu (bez końcowego /). */
export function readApiBaseUrl(): string {
  if (typeof window !== "undefined" && window.assystent?.apiUrl?.trim()) {
    return window.assystent.apiUrl.trim().replace(/\/$/, "");
  }
  const env = import.meta.env.VITE_API_BASE_URL?.trim();
  if (env) {
    return env.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    const proto = window.location.protocol;
    const host = window.location.hostname || "127.0.0.1";
    return `${proto}//${host}:8000`;
  }
  return "http://127.0.0.1:8000";
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
