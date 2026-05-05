import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Składa kolejne `audio_stream.chunk_base64` z WS (jeden WAV w Base64, pocięty na struny),
 * odtwarza przez Web Audio API i udostępnia poziom RMS do lip-sync.
 */
export function useAudioStreamPlayer() {
  const bufferRef = useRef("");
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const genRef = useRef(0);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [mouthLevel, setMouthLevel] = useState(0);

  const interruptPlayback = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
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
    interruptPlayback();
  }, [interruptPlayback]);

  const playFromWavBytes = useCallback(
    async (bytes: Uint8Array, myGen: number) => {
      if (myGen !== genRef.current) {
        return;
      }

      interruptPlayback();

      const ctx = audioCtxRef.current ?? new AudioContext();
      audioCtxRef.current = ctx;

      try {
        await ctx.resume();
      } catch {
        /* ignore */
      }

      let buf: AudioBuffer;
      try {
        const sliced = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
        buf = await ctx.decodeAudioData(sliced as ArrayBuffer);
      } catch {
        setIsSpeaking(false);
        return;
      }

      if (myGen !== genRef.current) {
        return;
      }

      const source = ctx.createBufferSource();
      source.buffer = buf;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.72;
      source.connect(analyser);
      analyser.connect(ctx.destination);
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
    [interruptPlayback],
  );

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
          /* ignore */
        }
      }, 110);
    },
    [playFromWavBytes, interruptPlayback],
  );

  useEffect(() => () => stop(), [stop]);

  return { feedAudioChunk, isSpeaking, mouthLevel, stop };
}
