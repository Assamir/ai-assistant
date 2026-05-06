/**
 * Skleja ścieżkę absolutną do modelu ONNX: katalog resources (bez końcowego separatora)
 * + fragment w konwencji POSIX z katalogu `piperVoicesCatalog.ts`.
 */

export function joinResourcesPath(resourcesRootAbsolute: string, onnxRelativePosix: string): string {
  const root = resourcesRootAbsolute.trim().replace(/[/\\]+$/, "");
  if (!root) {
    return "";
  }
  const segments = onnxRelativePosix.split("/").filter(Boolean);
  const looksWinAbs = /^[a-z]:/i.test(root);
  const looksWinMixed = looksWinAbs || root.includes("\\");
  const sep = looksWinMixed ? "\\" : "/";
  return root + sep + segments.join(sep);
}
