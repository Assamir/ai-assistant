/** Float32 mono → int16 WAV (16 kHz lub inna znana Fs) dla STT ws `ptt_end`. */

export function writeAscii(view: DataView, offset: number, str: string): void {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}

/** Liniowy resampler (wystarczający dla mowy przy 44.1→16 kHz). */
export function resampleLinear(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate || input.length === 0) {
    return input.slice();
  }
  const ratio = inputRate / outputRate;
  const outLen = Math.max(1, Math.floor(input.length / ratio));
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const src = i * ratio;
    const j = Math.floor(src);
    const frac = src - j;
    const a = input[j] ?? 0;
    const b = input[j + 1] ?? a;
    out[i] = a + frac * (b - a);
  }
  return out;
}

export function float32ToPCM16LittleEndian(samples: Float32Array): Uint8Array {
  const buf = new ArrayBuffer(samples.length * 2);
  const dv = new DataView(buf);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i] ?? 0));
    dv.setInt16(i * 2, s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff), true);
  }
  return new Uint8Array(buf);
}

export function buildWavPCM16Mono(pcmBody: Uint8Array, sampleRate: number): ArrayBuffer {
  const dataSize = pcmBody.byteLength;
  const wav = new ArrayBuffer(44 + dataSize);
  const view = new DataView(wav);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits/sample
  writeAscii(view, 36, "data");
  view.setUint32(40, dataSize, true);
  new Uint8Array(wav, 44).set(pcmBody);
  return wav;
}

export function buildWavFromFloatMono(f32Mono: Float32Array, sampleRate: number): ArrayBuffer {
  const pcm = float32ToPCM16LittleEndian(f32Mono);
  return buildWavPCM16Mono(pcm, sampleRate);
}

export function arrayBufferToStandardBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

export const STT_TARGET_SAMPLE_RATE_HZ = 16000;
