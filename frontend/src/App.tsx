import React from "react";

export function App() {
  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem", maxWidth: 640 }}>
      <h1>Assystent</h1>
      <p>Szkielet T9 — Electron + Vite + React. Backend: WebSocket multiplex.</p>
      <p>
        <code>npm run dev</code> → Vite · <code>ASSYSTENT_DEV=1 npm run electron</code> → okno
        (po starcie Vite).
      </p>
    </main>
  );
}
