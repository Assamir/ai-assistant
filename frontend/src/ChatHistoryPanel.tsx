import React, { useEffect, useRef } from "react";

export interface ChatMessage {
  role: "user" | "assistant" | "observer";
  content: string;
  timestamp: number;
}

export interface ThreadInfo {
  threadId: number | null;
  title: string | null;
  kind: "new" | "continuation" | "resumed" | null;
}

export interface AgentStep {
  index: number;
  description: string;
  status: "pending" | "in_progress" | "done" | "failed" | "skipped";
  result?: string | null;
}

export interface AgentPlan {
  goal: string;
  steps: AgentStep[];
}

interface ChatHistoryPanelProps {
  messages: ChatMessage[];
  thread: ThreadInfo;
  agentPlan: AgentPlan | null;
  assistantName: string;
  maxMessages?: number;
  opacity?: number;
  width?: number;
}

const STATUS_ICON: Record<string, string> = {
  pending: "○",
  in_progress: "▶",
  done: "✓",
  failed: "✗",
  skipped: "—",
};

const STATUS_COLOR: Record<string, string> = {
  pending: "#7a7390",
  in_progress: "#f59e0b",
  done: "#22c55e",
  failed: "#ef4444",
  skipped: "#6b7280",
};

function timeLabel(ts: number): string {
  const d = new Date(ts);
  return d.toISOString().slice(11, 16);
}

export function ChatHistoryPanel({
  messages,
  thread,
  agentPlan,
  assistantName,
  maxMessages = 6,
  opacity = 0.85,
  width = 280,
}: ChatHistoryPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const visible = messages.slice(-maxMessages);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const panelBg = `rgba(10,8,18,${opacity})`;

  return (
    <div
      style={{
        width,
        display: "flex",
        flexDirection: "column",
        background: panelBg,
        backdropFilter: "blur(6px)",
        borderRadius: 8,
        border: "1px solid rgba(74,63,98,0.6)",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Thread context bar */}
      {thread.title || thread.kind ? (
        <div
          style={{
            padding: "0.3rem 0.55rem",
            borderBottom: "1px solid rgba(74,63,98,0.4)",
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
            minHeight: 28,
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: thread.kind === "resumed" ? "#f59e0b" : thread.kind === "new" ? "#3b82f6" : "#22c55e",
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: 11,
              color: "#c8c0dc",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1,
            }}
            title={thread.title || undefined}
          >
            {thread.title ?? (thread.kind === "new" ? "Nowy wątek" : "Wątek")}
          </span>
          {thread.kind === "resumed" && (
            <span style={{ fontSize: 10, color: "#f59e0b", flexShrink: 0 }}>↺</span>
          )}
        </div>
      ) : null}

      {/* Chat messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "0.45rem 0.55rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.35rem",
          minHeight: 80,
          maxHeight: 260,
        }}
      >
        {visible.length === 0 ? (
          <div style={{ fontSize: 12, color: "#5a5278", fontStyle: "italic", textAlign: "center", marginTop: "0.5rem" }}>
            Brak wiadomości
          </div>
        ) : (
          visible.map((msg, i) => (
            <div key={`${msg.timestamp}-${i}`} style={{ display: "flex", flexDirection: "column", gap: 1 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.3rem" }}>
                <span
                  style={{
                    fontSize: 10,
                    color: msg.role === "user" ? "#7ab8d4" : msg.role === "observer" ? "#94a3b8" : "#b98cf4",
                    fontWeight: 600,
                    flexShrink: 0,
                  }}
                >
                  {msg.role === "user" ? "Ty" : msg.role === "observer" ? "Obs." : assistantName}
                </span>
                <span style={{ fontSize: 10, color: "#4a4468" }}>{timeLabel(msg.timestamp)}</span>
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: msg.role === "user" ? "#ddd8f0" : "#c8c0dc",
                  lineHeight: 1.4,
                  wordBreak: "break-word",
                  paddingLeft: "0.15rem",
                }}
              >
                {msg.content.length > 160 ? msg.content.slice(0, 160) + "…" : msg.content}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* Agent plan */}
      {agentPlan && agentPlan.steps.length > 0 ? (
        <div
          style={{
            borderTop: "1px solid rgba(74,63,98,0.4)",
            padding: "0.35rem 0.55rem",
            maxHeight: 140,
            overflowY: "auto",
          }}
        >
          <div style={{ fontSize: 10, color: "#9a8ab8", marginBottom: "0.25rem", fontWeight: 600 }}>
            PLAN · {agentPlan.steps.filter((s) => s.status === "done").length}/{agentPlan.steps.length}
          </div>
          {agentPlan.steps.map((step) => (
            <div
              key={step.index}
              style={{ display: "flex", alignItems: "flex-start", gap: "0.3rem", marginBottom: "0.2rem" }}
            >
              <span style={{ fontSize: 11, color: STATUS_COLOR[step.status] ?? "#7a7390", flexShrink: 0 }}>
                {STATUS_ICON[step.status] ?? "○"}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: step.status === "done" ? "#6b7280" : "#c8c0dc",
                  lineHeight: 1.35,
                  textDecoration: step.status === "done" ? "line-through" : "none",
                }}
              >
                {step.description.length > 60 ? step.description.slice(0, 60) + "…" : step.description}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
