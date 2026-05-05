import { useCallback, useEffect, useRef, useState } from "react";

export type WsConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

export interface WsFrame {
  event: string;
  payload: Record<string, unknown>;
}

function defaultWsUrl(): string {
  if (typeof window !== "undefined" && window.assystent?.wsUrl) {
    return window.assystent.wsUrl;
  }
  const env = import.meta.env.VITE_WS_URL?.trim();
  if (env) {
    return env;
  }
  if (typeof window !== "undefined" && window.location.protocol === "file:") {
    const host = window.location.hostname || "127.0.0.1";
    return `ws://${host}:8000/ws`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.hostname || "127.0.0.1";
  const port = window.location.port;
  const suffix = port ? `:${port}` : ":8000";
  return `${proto}//${host}${suffix}/ws`;
}

function parseFrame(raw: string): WsFrame | null {
  try {
    const o = JSON.parse(raw) as unknown;
    if (!o || typeof o !== "object") {
      return null;
    }
    const rec = o as Record<string, unknown>;
    const event = typeof rec.event === "string" ? rec.event : "";
    const payload =
      rec.payload && typeof rec.payload === "object" && rec.payload !== null
        ? (rec.payload as Record<string, unknown>)
        : {};
    if (!event) {
      return null;
    }
    return { event, payload };
  } catch {
    return null;
  }
}

function nextBackoffMs(attempt: number): number {
  const base = 800;
  const cap = 30_000;
  return Math.min(cap, base * Math.pow(2, Math.min(attempt, 8)));
}

export interface UseWebSocketOptions {
  url?: string;
  onFrame?: (frame: WsFrame) => void;
  /** Jeśli false — nie łącz automatycznie (np. test). */
  connect?: boolean;
}

export function useWebSocket(opts: UseWebSocketOptions = {}) {
  const url = opts.url ?? defaultWsUrl();
  const shouldConnect = opts.connect !== false;
  const onFrameRef = useRef(opts.onFrame);
  onFrameRef.current = opts.onFrame;

  const [status, setStatus] = useState<WsConnectionStatus>("idle");
  const [lastFrame, setLastFrame] = useState<WsFrame | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const manualClose = useRef(false);

  const clearTimer = () => {
    if (reconnectRef.current !== null) {
      clearTimeout(reconnectRef.current);
      reconnectRef.current = null;
    }
  };

  const scheduleReconnect = () => {
    clearTimer();
    if (!shouldConnect || manualClose.current) {
      return;
    }
    const delay = nextBackoffMs(attemptRef.current);
    reconnectRef.current = setTimeout(() => connect(), delay);
  };

  const connect = useCallback(() => {
    if (!shouldConnect || manualClose.current) {
      return;
    }
    clearTimer();
    wsRef.current?.close();
    setStatus("connecting");

    let socket: WebSocket;
    try {
      socket = new WebSocket(url);
    } catch {
      setStatus("error");
      attemptRef.current += 1;
      scheduleReconnect();
      return;
    }

    wsRef.current = socket;

    socket.onopen = () => {
      attemptRef.current = 0;
      setStatus("open");
    };

    socket.onmessage = (ev) => {
      const frame = parseFrame(String(ev.data));
      if (!frame) {
        return;
      }
      setLastFrame(frame);
      onFrameRef.current?.(frame);
    };

    socket.onerror = () => {
      setStatus("error");
    };

    socket.onclose = () => {
      wsRef.current = null;
      setStatus("closed");
      attemptRef.current += 1;
      scheduleReconnect();
    };
  }, [url, shouldConnect]);

  useEffect(() => {
    manualClose.current = false;
    if (shouldConnect) {
      connect();
    }
    return () => {
      manualClose.current = true;
      clearTimer();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect, shouldConnect]);

  const sendFrame = useCallback((event: string, payload: Record<string, unknown> = {}) => {
    const s = wsRef.current;
    if (!s || s.readyState !== WebSocket.OPEN) {
      return false;
    }
    s.send(JSON.stringify({ event, payload }));
    return true;
  }, []);

  const disconnect = useCallback(() => {
    manualClose.current = true;
    clearTimer();
    wsRef.current?.close();
    wsRef.current = null;
    setStatus("closed");
  }, []);

  return { status, lastFrame, sendFrame, disconnect, reconnect: connect };
}
