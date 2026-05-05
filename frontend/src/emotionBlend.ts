import emotionWeights from "./emotions.json";

export type EmotionWeightsMap = Record<string, Record<string, number>>;
export const emotionMap = emotionWeights as EmotionWeightsMap;

const NEUTRAL_KEY = "neutral";

export function normalizeEmotionKey(emotion: string): string {
  const k = emotion.toLowerCase();
  return emotionMap[k] !== undefined ? k : NEUTRAL_KEY;
}

export function resolveWeights(emotion: string): Record<string, number> {
  const key = normalizeEmotionKey(emotion);
  const row = emotionMap[key] ?? emotionMap[NEUTRAL_KEY];
  return { ...row };
}

export function blendRecords(
  from: Record<string, number>,
  to: Record<string, number>,
  u: number,
): Record<string, number> {
  const t = Math.min(1, Math.max(0, u));
  const keys = new Set([...Object.keys(from), ...Object.keys(to)]);
  const out: Record<string, number> = {};
  for (const k of keys) {
    out[k] = (from[k] ?? 0) * (1 - t) + (to[k] ?? 0) * t;
  }
  return out;
}

export function easeOutCubic(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return 1 - (1 - x) ** 3;
}

export function recordsNearlyEqual(
  a: Record<string, number>,
  b: Record<string, number>,
  eps = 0.002,
): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if (Math.abs((a[k] ?? 0) - (b[k] ?? 0)) > eps) {
      return false;
    }
  }
  return true;
}
