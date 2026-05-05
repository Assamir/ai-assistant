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
