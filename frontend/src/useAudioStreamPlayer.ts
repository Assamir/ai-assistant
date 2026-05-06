import { useCallback, useEffect, useRef, useState } from "react";

const VOLUME_LS_KEY = "assystent.outputVolume";

function readStoredVolume(): number {
  if (typeof window === "undefined") {
    return 1;
  }
  const raw = localStorage.getItem(VOLUME_LS_KEY);
  if (raw == null) {
    return 1;
  }
  const n = Number(raw);
  if (!Number.isFinite(n)) {
    return 1;
  }
  return Math.max(0, Math.min(1, n));
}

type AudioCtxWithSink = AudioContext & { setSinkId?: (id: string) => Promise<void> };

/**
 * Składa kolejne `audio_stream.chunk_base64` z WS (jeden WAV w Base64, pocięty na struny),
 * odtwarza przez Web Audio API i udostępnia poziom RMS do lip-sync.
 * Domyślne urządzenie wyjściowe: `setSinkId("")` gdy przeglądarka/Electron to wspiera.
 */
export function useAudioStreamPlayer() {
  const bufferRef = useRef("");
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const genRef = useRef(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const liveGainRef = useRef<GainNode | null>(null);

  const [outputVolume, setOutputVolumeState] = useState(readStoredVolume);

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [mouthLevel, setMouthLevel] = useState(0);

  const [playbackError, setPlaybackError] = useState<string | null>(null);

  const setOutputVolume = useCallback((v: number) => {
    const clamped = Math.max(0, Math.min(1, v));
    setOutputVolumeState(clamped);
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(VOLUME_LS_KEY, String(clamped));
    }
    const g = liveGainRef.current;
    if (g) {
      g.gain.value = clamped;
    }
  }, []);

  const interruptPlayback = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    liveGainRef.current = null;
    const src = sourceRef.current;
    if (src) {
      try {
        src.stop();
      } catch {
        /* already ended */
      }
      sourceRef.current = null;
    }
    setMouthLevel(0);
    setIsSpeaking(false);
  }, []);

  const stop = useCallback(() => {
    bufferRef.current = "";
    genRef.current += 1;
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
    setPlaybackError(null);
    interruptPlayback();
  }, [interruptPlayback]);

  const prime = useCallback(async () => {
    const ctx = audioCtxRef.current ?? new AudioContext({ latencyHint: "playback" });
    audioCtxRef.current = ctx;
    try {
      const c = ctx as AudioCtxWithSink;
      if (typeof c.setSinkId === "function") {
        await c.setSinkId("");
      }
    } catch {
      /* starsze WebView / polityka — zostaw domyślne urządzenie systemowe */
    }
    try {
      await ctx.resume();
      setPlaybackError(null);
    } catch {
      /* ignore */
    }
  }, []);

  const playFromWavBytes = useCallback(
    async (bytes: Uint8Array, myGen: number) => {
      if (myGen !== genRef.current) {
        return;
      }

      interruptPlayback();

      const ctx = audioCtxRef.current ?? new AudioContext({ latencyHint: "playback" });
      audioCtxRef.current = ctx;

      try {
        await ctx.resume();
      } catch {
        /* ignore */
      }

      try {
        const c = ctx as AudioCtxWithSink;
        if (typeof c.setSinkId === "function") {
          await c.setSinkId("");
        }
      } catch {
        /* ignore */
      }

      let buf: AudioBuffer;
      try {
        const copy = new Uint8Array(bytes.byteLength);
        copy.set(bytes);
        buf = await ctx.decodeAudioData(copy.buffer.slice(copy.byteOffset, copy.byteOffset + copy.byteLength));
      } catch {
        setIsSpeaking(false);
        setPlaybackError(
          "Nie udało się zdekodować audio z TTS (WAV). Otwórz DevTools lub sprawdź, czy silnik TTS jest skonfigurowany w backendzie.",
        );
        return;
      }

      setPlaybackError(null);

      if (myGen !== genRef.current) {
        return;
      }

      try {
        await ctx.resume();
      } catch {
        /* ignore */
      }

      const source = ctx.createBufferSource();
      source.buffer = buf;
      const gain = ctx.createGain();
      gain.gain.value = outputVolume;
      liveGainRef.current = gain;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.72;
      source.connect(analyser);
      analyser.connect(gain);
      gain.connect(ctx.destination);
      sourceRef.current = source;

      const data = new Uint8Array(analyser.fftSize);

      const loop = () => {
        if (myGen !== genRef.current || sourceRef.current !== source) {
          return;
        }
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i += 1) {
          const x = (data[i] - 128) / 128;
          sum += x * x;
        }
        const rms = Math.sqrt(sum / data.length);
        const level = Math.min(1, rms * 5.5);
        setMouthLevel(level);
        rafRef.current = requestAnimationFrame(loop);
      };

      source.onended = () => {
        if (sourceRef.current === source) {
          sourceRef.current = null;
        }
        if (liveGainRef.current === gain) {
          liveGainRef.current = null;
        }
        if (rafRef.current !== null) {
          cancelAnimationFrame(rafRef.current);
          rafRef.current = null;
        }
        setMouthLevel(0);
        setIsSpeaking(false);
      };

      setIsSpeaking(true);
      source.start(0);
      rafRef.current = requestAnimationFrame(loop);
    },
    [interruptPlayback, outputVolume],
  );

  useEffect(() => {
    const g = liveGainRef.current;
    if (g) {
      g.gain.value = outputVolume;
    }
  }, [outputVolume]);

  const feedAudioChunk = useCallback(
    (chunk: string) => {
      if (!bufferRef.current) {
        if (flushTimerRef.current !== null) {
          clearTimeout(flushTimerRef.current);
          flushTimerRef.current = null;
        }
        genRef.current += 1;
        interruptPlayback();
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
          void playFromWavBytes(arr, myGen);
        } catch {
          setPlaybackError("Nieprawidłowe Base64 ze strumienia audio_stream — zerwano strumień?");
        }
      }, 260);
    },
    [playFromWavBytes, interruptPlayback],
  );

  useEffect(() => () => stop(), [stop]);

  return {
    feedAudioChunk,
    isSpeaking,
    mouthLevel,
    stop,
    prime,
    playbackError,
    outputVolume,
    setOutputVolume,
  };
}
