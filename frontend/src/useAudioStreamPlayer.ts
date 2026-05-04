import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Składa kolejne `audio_stream.chunk_base64` z WS (jeden WAV w Base64, pocięty na struny)
 * i odtwarza po krótkiej ciszy między kawałkami.
 */
export function useAudioStreamPlayer() {
  const bufferRef = useRef("");
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const genRef = useRef(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const stop = useCallback(() => {
    bufferRef.current = "";
    genRef.current += 1;
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    const a = audioRef.current;
    if (a) {
      try {
        a.pause();
      } catch {
        /* ignore */
      }
      const src = a.src;
      if (src?.startsWith("blob:")) {
        URL.revokeObjectURL(src);
      }
      audioRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  const playBlobUrl = useCallback(
    (uri: string) => {
      const prev = audioRef.current;
      if (prev) {
        try {
          prev.pause();
        } catch {
          /* ignore */
        }
        const ps = prev.src;
        if (ps?.startsWith("blob:")) {
          URL.revokeObjectURL(ps);
        }
      }
      const a = new Audio(uri);
      audioRef.current = a;
      setIsSpeaking(true);
      a.onended = () => {
        URL.revokeObjectURL(uri);
        if (audioRef.current === a) {
          audioRef.current = null;
        }
        setIsSpeaking(false);
      };
      void a.play().catch(() => {
        URL.revokeObjectURL(uri);
        setIsSpeaking(false);
      });
    },
    [],
  );

  const feedAudioChunk = useCallback(
    (chunk: string) => {
      if (!bufferRef.current) {
        if (flushTimerRef.current !== null) {
          clearTimeout(flushTimerRef.current);
          flushTimerRef.current = null;
        }
        genRef.current += 1;
        const prev = audioRef.current;
        if (prev) {
          try {
            prev.pause();
          } catch {
            /* ignore */
          }
          const ps = prev.src;
          if (ps?.startsWith("blob:")) {
            URL.revokeObjectURL(ps);
          }
          audioRef.current = null;
          setIsSpeaking(false);
        }
      }
      const myGen = genRef.current;
      bufferRef.current += chunk;
      if (flushTimerRef.current !== null) {
        clearTimeout(flushTimerRef.current);
      }
      flushTimerRef.current = setTimeout(() => {
        flushTimerRef.current = null;
        if (myGen !== genRef.current) {
          return;
        }
        const b64 = bufferRef.current;
        bufferRef.current = "";
        if (!b64.trim()) {
          return;
        }
        try {
          const bin = atob(b64.replace(/\s+/g, ""));
          const arr = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i += 1) {
            arr[i] = bin.charCodeAt(i);
          }
          const blob = new Blob([arr], { type: "audio/wav" });
          const url = URL.createObjectURL(blob);
          playBlobUrl(url);
        } catch {
          /* ignore bogus chunks */
        }
      }, 110);
    },
    [playBlobUrl],
  );

  useEffect(() => () => stop(), [stop]);

  return { feedAudioChunk, isSpeaking, stop };
}
