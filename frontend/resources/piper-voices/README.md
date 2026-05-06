# Głosy Piper (polski)

Szablony leżą tu względem katalogu `frontend/resources`:

- `pl/pl_PL/<nazwa>/<jakość>/*.onnx` (+ sąsiedni `.onnx.json` – generowany przy eksporcie głosu)

**Pierwszy raz lub po świeżym kluczu:** uruchom z korzenia repo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-piper-voices.ps1
```

Domyślne źródło: `..\piper-voices\pl\pl_PL` obok folderu repozytorium (`assystent`). Możesz podać własną ścieżkę:

```powershell
.\scripts\sync-piper-voices.ps1 -SourceRoot "D:\inne\piper-voices\pl\pl_PL"
```

W aplikacji: karta **Więcej** → ustaw ścieżkę do **`frontend/resources`** tego klona oraz wybór głosu; **Zastosuj głos** wysyła `tts.piper_voice_onnx_path` do backendu (wymaga zapisanej konfiguracji YAML + opcjonalnie tokenu jak przy innych PATCH).
