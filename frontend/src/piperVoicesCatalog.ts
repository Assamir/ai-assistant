/** Głosy skopiowane do `frontend/resources/piper-voices/pl/pl_PL/` — ścieżki względem `resources/`. */

export interface BundledPiperVoice {
  /** Id dla localStorage */
  id: string;
  /** Krótki opis dla listy rozwijalnej */
  label: string;
  /** Ścieżka względem katalogu `frontend/resources` (separator `/`). */
  onnxRelativeToResources: string;
}

/** localStorage: absolutna ścieżka do folderu `frontend/resources` (bez końcowego \). */
export const PIPER_RESOURCES_ROOT_LS = "assystent.piperResourcesRoot";
/** localStorage: id z BUNDLED_PIPER_VOICES */
export const PIPER_VOICE_ID_LS = "assystent.selectedPiperVoiceId";
export const PIPER_EXECUTABLE_LS = "assystent.piperExecutable";

export const DEFAULT_PIPER_VOICE_ID = "gosia-medium";

export const BUNDLED_PIPER_VOICES: BundledPiperVoice[] = [
  {
    id: "gosia-medium",
    label: "Gosia — medium (PL, żeński)",
    onnxRelativeToResources: "piper-voices/pl/pl_PL/gosia/medium/pl_PL-gosia-medium.onnx",
  },
  {
    id: "darkman-medium",
    label: "Darkman — medium (PL, męski)",
    onnxRelativeToResources: "piper-voices/pl/pl_PL/darkman/medium/pl_PL-darkman-medium.onnx",
  },
  {
    id: "mc_speech-medium",
    label: "MC Speech — medium (PL)",
    onnxRelativeToResources: "piper-voices/pl/pl_PL/mc_speech/medium/pl_PL-mc_speech-medium.onnx",
  },
  {
    id: "bass-high",
    label: "Bass — high (PL, wyższa jakość · większy plik)",
    onnxRelativeToResources: "piper-voices/pl/pl_PL/bass/high/pl_PL-bass-high.onnx",
  },
  {
    id: "mls_6892-low",
    label: "MLS 6892 — low (PL, mniejszy model)",
    onnxRelativeToResources: "piper-voices/pl/pl_PL/mls_6892/low/pl_PL-mls_6892-low.onnx",
  },
];

export function bundledPiperVoiceById(id: string): BundledPiperVoice | undefined {
  return BUNDLED_PIPER_VOICES.find((v) => v.id === id);
}
