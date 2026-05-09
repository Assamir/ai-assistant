/**
 * Nagrywanie mikrofonu → WAV mono 16 kHz (PCM16) dla `ptt_end` / STT backendu.
 * ScriptProcessor przy geście użytkownika (PTT w Electron/Chromium).
 */

import { useCallback, useRef, useState } from "react";
import {
  STT_TARGET_SAMPLE_RATE_HZ,
  arrayBufferToStandardBase64,
  buildWavFromFloatMono,
  resampleLinear,
} from "./audioWav";

function concatFloatChunks(chunks: Float32Array[]): Float32Array {
  const n = chunks.reduce((acc, c) => acc + c.length, 0);
  const out = new Float32Array(n);
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
  }
  return out;
}

interface ActiveSession {
  stream: MediaStream;
  audioCtx: AudioContext;
  source: MediaStreamAudioSourceNode;
  processor: ScriptProcessorNode;
  gain: GainNode;
  chunks: Float32Array[];
}

export interface UsePttRecorderResult {
  pttBusy: boolean;
  pttError: string | null;
  setPttError: React.Dispatch<React.SetStateAction<string | null>>;
  pttArm: () => Promise<boolean>;
  pttFinalize: () => Promise<string | null>;
}

export interface UsePttRecorderOptions {
  deviceId?: string;
}

export function usePttRecorder(options?: UsePttRecorderOptions): UsePttRecorderResult {
  const [pttBusy, setPttBusy] = useState(false);
  const [pttError, setPttError] = useState<string | null>(null);
  const sessionRef = useRef<ActiveSession | null>(null);
  const capturingRef = useRef(false);

  const disposeSession = useCallback(async () => {
    const s = sessionRef.current;
    sessionRef.current = null;
    capturingRef.current = false;
    if (!s) {
      return;
    }
    try {
      s.processor.disconnect();
    } catch {
      /* ignore */
    }
    try {
      s.gain.disconnect();
    } catch {
      /* ignore */
    }
    try {
      s.source.disconnect();
    } catch {
      /* ignore */
    }
    try {
      await s.audioCtx.close();
    } catch {
      /* ignore */
    }
    for (const t of s.stream.getTracks()) {
      try {
        t.stop();
      } catch {
        /* ignore */
      }
    }
  }, []);

  const pttArm = useCallback(async (): Promise<boolean> => {
    setPttError(null);
    if (sessionRef.current) {
      await disposeSession();
    }
    setPttBusy(true);
    try {
      const audioConstraints: MediaTrackConstraints = {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      };
      const did = options?.deviceId?.trim();
      if (did && did !== "default") {
        audioConstraints.deviceId = { exact: did };
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
      const audioCtx = new AudioContext();
      await audioCtx.resume();
      const source = audioCtx.createMediaStreamSource(stream);
      const bufferSize = 4096;
      const processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
      const gain = audioCtx.createGain();
      gain.gain.value = 0;

      const chunks: Float32Array[] = [];
      processor.onaudioprocess = (ev: AudioProcessingEvent) => {
        if (!capturingRef.current) {
          return;
        }
        const ch = ev.inputBuffer.getChannelData(0);
        chunks.push(Float32Array.from(ch));
      };

      source.connect(processor);
      processor.connect(gain);
      gain.connect(audioCtx.destination);

      sessionRef.current = {
        stream,
        audioCtx,
        source,
        processor,
        gain,
        chunks,
      };
      capturingRef.current = true;
      return true;
    } catch (e) {
      setPttError(e instanceof Error ? e.message : String(e));
      await disposeSession();
      return false;
    } finally {
      setPttBusy(false);
    }
  }, [disposeSession]);

  const pttFinalize = useCallback(async (): Promise<string | null> => {
    capturingRef.current = false;
    const s = sessionRef.current;
    if (!s) {
      return null;
    }
    const { chunks, audioCtx } = s;
    const srIn = audioCtx.sampleRate;

    await disposeSession();

    const mono = concatFloatChunks(chunks);
    if (mono.length < srIn * 0.12) {
      setPttError("Za krótkie nagranie — przytrzymaj PTT przez co najmniej ~0.2 s.");
      return null;
    }

    const resampled = resampleLinear(mono, srIn, STT_TARGET_SAMPLE_RATE_HZ);
    const wav = buildWavFromFloatMono(resampled, STT_TARGET_SAMPLE_RATE_HZ);
    return arrayBufferToStandardBase64(wav);
  }, [disposeSession]);

  return {
    pttBusy,
    pttError,
    setPttError,
    pttArm,
    pttFinalize,
  };
}
