/** Modele z katalogu `frontend/resources/` (serwowane / kopiowane jako root statyczny przez Vite `publicDir: resources`). */

export const DEFAULT_BUNDLED_VRM_FILENAME = "kaguya_watanuki.vrm";

export const BUNDLED_VRM_SELECT_OTHER = "__other__";

/**
 * Lista musi pokrywać pliki *.vrm w `frontend/resources/` (dla listy UI i rozpoznawania `./nazwa.vrm`).
 */
const DISCOVERED_FILENAMES = ["AvatarSample_B.vrm", "kaguya_watanuki.vrm", "watanuki_kaguya_NR.vrm"] as const;

/** Domyślny model pierwszy, potem alfabetycznie. */
export const BUNDLED_VRM_FILENAMES: readonly string[] = [...new Set([DEFAULT_BUNDLED_VRM_FILENAME, ...DISCOVERED_FILENAMES])].sort(
  (a, b) => {
    if (a === DEFAULT_BUNDLED_VRM_FILENAME) return -1;
    if (b === DEFAULT_BUNDLED_VRM_FILENAME) return 1;
    return a.localeCompare(b);
  },
);

/** URL względny dla loadera — obok `index.html`. */
export function bundledVrmRelativeUrl(filename: string): string {
  const name = filename.trim().replace(/^\.\//, "");
  return `./${name}`;
}

export function bundledFilenameFromStoredUrl(url: string): string | null {
  const t = url.trim();
  const lower = t.toLowerCase();
  if (!lower.includes(".vrm")) {
    return null;
  }
  const slug = (t.split(/[/\\]/).pop() ?? t).replace(/^\.\//, "");
  const hit = BUNDLED_VRM_FILENAMES.find((x) => x.toLowerCase() === slug.toLowerCase());
  return hit ?? null;
}

export function bundledSelectValueForUrl(url: string): string {
  const fn = bundledFilenameFromStoredUrl(url);
  if (fn) {
    return fn;
  }
  return BUNDLED_VRM_SELECT_OTHER;
}
