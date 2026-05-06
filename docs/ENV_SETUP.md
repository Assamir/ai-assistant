# ENV_SETUP.md — Środowisko Deweloperskie Assystent

> **Status:** v1.3
> **Data:** 2026-05-05
> **Cel:** Kompletny manual konfiguracji środowiska deweloperskiego. Osoba na świeżym Windows 11 powinna skończyć w < 2h.
> **Źródło decyzji:** DECISIONS_LOG.md (v1.1) — nie podważaj wartości z tego pliku.

---

## Spis treści

1. [Wymagania sprzętowe i systemowe](#1-wymagania-sprzętowe-i-systemowe)
2. [Software prerequisites](#2-software-prerequisites)
3. [Struktura katalogów](#3-struktura-katalogów)
4. [Python environment](#4-python-environment)
5. [Pobieranie modeli AI](#5-pobieranie-modeli-ai)
6. [LM Studio setup](#6-lm-studio-setup)
7. [Frontend setup](#7-frontend-setup)
8. [Pierwsze uruchomienie](#8-pierwsze-uruchomienie)
9. [Troubleshooting](#9-troubleshooting)
10. [Skrypty pomocnicze](#10-skrypty-pomocnicze)

---

## 1. Wymagania sprzętowe i systemowe

### 1.1 Sprzęt


| Komponent | Minimum                          | Zalecane (docelowe)          |
| --------- | -------------------------------- | ---------------------------- |
| GPU       | NVIDIA GTX 1080 Ti (11 GB VRAM)  | NVIDIA RTX 5090 (32 GB VRAM) |
| RAM       | 16 GB                            | 32 GB+                       |
| Dysk      | 50 GB wolnego miejsca (SSD)      | 200 GB NVMe                  |
| CPU       | 4 rdzenie, 3 GHz                 | 8+ rdzeni                    |
| OS        | Windows 10 64-bit (build 19041+) | Windows 11 64-bit            |


### 1.2 Budżet VRAM


| Komponent                        | VRAM (est.)   | Uwagi                                     |
| -------------------------------- | ------------- | ----------------------------------------- |
| LM Studio — Gemma 4 E4B (Q4_K_M) | ~5–6 GB       | Zależne od kwantyzacji                    |
| Faster-Whisper medium            | ~1.5 GB       | CTranslate2, int8                         |
| Moondream2                       | ~2 GB         | int8 quantized                            |
| EasyOCR (CUDA)                   | ~0.5 GB       | Tylko gdy OCR aktywny                     |
| Three.js / Electron GPU          | ~0.3 GB       | Frontend renderer                         |
| **Łącznie (wszystkie aktywne)**  | **~10–11 GB** | Bezpieczne na 11 GB+; na RTX 5090 trivial |


> **Uwaga Minimum:** Na GPU z 11 GB VRAM należy wyłączyć OCR i VLM gdy uruchomione inne procesy GPU (gry).
> Na RTX 5090 (32 GB) — wszystkie moduły jednocześnie bez żadnych ograniczeń.

### 1.3 Weryfikacja CUDA

```powershell
# Sprawdź sterownik i CUDA
nvidia-smi
# Oczekiwane: CUDA Version >= 12.1

# Jeśli nvidia-smi niedostępne — zainstaluj sterowniki NVIDIA (>=560.x)
# https://www.nvidia.com/Download/index.aspx
```

---

## 2. Software prerequisites

### 2.1 Tabela zależności


| Narzędzie                 | Wersja | Alternatywa             | Link oficjalny             | Uwagi                                  |
| ------------------------- | ------ | ----------------------- | -------------------------- | -------------------------------------- |
| Python                    | 3.11.x | 3.10.x, 3.12.x          | python.org/downloads       | **3.11 zalecane** — max kompatybilność |
| Node.js                   | 22 LTS | 20 LTS                  | nodejs.org                 | Frontend Electron                      |
| Git                       | 2.40+  | —                       | git-scm.com                |                                        |
| LM Studio                 | latest | Ollama (ograniczone FC) | lmstudio.ai                | Wymaga function calling                |
| NVIDIA Driver             | 560+   | —                       | nvidia.com/drivers         | CUDA 12.x included                     |
| Visual Studio Build Tools | 2022   | VS Community            | visualstudio.microsoft.com | Wymagane przez niektóre pip packages   |


### 2.2 Instalacja Python

```powershell
# Pobierz Python 3.11.x z python.org
# Podczas instalacji zaznacz: "Add Python to PATH" + "pip"

python --version
# Python 3.11.x

pip --version
# pip 24.x
```

### 2.3 Instalacja Node.js

```powershell
# Pobierz Node.js 22 LTS z nodejs.org (Windows Installer)

node --version
# v22.x.x

npm --version
# 10.x.x
```

### 2.4 Visual Studio Build Tools (wymagane przez dxcam, easyocr)

```powershell
# Pobierz "Build Tools for Visual Studio 2022"
# Zainstaluj komponent: "Desktop development with C++"
# Rozmiar: ~7 GB
```

---

## 3. Struktura katalogów

### 3.1 Dwa rooty


| Root             | Ścieżka                                 | Zawartość                                 |
| ---------------- | --------------------------------------- | ----------------------------------------- |
| **Code root**    | `c:\code\_repos\antigravity\assystent\` | Kod źródłowy, venv, testy                 |
| **Content root** | `c:\ai\asystent\`                       | Dane, modele, config, dokumenty — sandbox |


> **Reguła Sandbox (NF-S-04):** Backend nigdy nie pisze poza `c:\ai\asystent\`. Obie ścieżki są stałe i nienegocjowalne.

### 3.2 Tworzenie content root

```powershell
# Uruchom jako zwykły użytkownik (bez Administrator)
$root = "c:\ai\asystent"

$dirs = @(
    "$root\config\game_profiles",
    "$root\data\chroma",
    "$root\models\whisper",
    "$root\models\piper",
    "$root\models\wakeword",
    "$root\models\moondream",
    "$root\models\embeddings",
    "$root\models\avatar",
    "$root\personas",
    "$root\knowledge\poe2",
    "$root\knowledge\stellaris",
    "$root\documents",
    "$root\logs",
    "$root\backups",
    "$root\screenshots"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "OK: $dir"
}

Write-Host "`nContent root gotowy: $root"
```

### 3.3 Drzewo katalogów (docelowe)

```
c:\ai\asystent\
├── config\
│   ├── config.yaml               # główna konfiguracja
│   ├── commands.yaml             # custom komendy użytkownika
│   ├── auth.token                # opcjonalny token lokalny (auto-gen przy starcie)
│   └── game_profiles\
│       ├── poe2.yaml
│       └── stellaris.yaml
├── data\
│   ├── assystent.db              # SQLite główna baza
│   ├── player_profile.yaml       # profil gracza
│   └── chroma\                   # ChromaDB embeddings
├── models\
│   ├── whisper\                  # Faster-Whisper medium
│   ├── piper\                    # binary + voice model
│   ├── wakeword\                 # openWakeWord custom models
│   ├── moondream\                # Moondream2
│   ├── embeddings\               # sentence-transformers cache
│   └── avatar\
│       ├── primary.vrm           # główny model VRM
│       └── fallback.vrm          # zapasowy model VRM
├── personas\
│   └── default.md                # persona domyślna
├── knowledge\
│   ├── poe2\                     # pliki .md z wiedzą o grze
│   └── stellaris\
├── documents\                    # dokumenty generowane przez asystenta
├── logs\                         # logi rotowane
├── backups\                      # archiwa ZIP
├── screenshots\                  # debug screenshots (gdy enabled)
└── LICENSES.md                   # atrybucje CC-BY (wymagane prawnie)
```

---

## 4. Python environment

### 4.1 Tworzenie venv

```powershell
# Z katalogu code root
cd c:\code\_repos\antigravity\assystent

python -m venv .venv

# Aktywacja (PowerShell)
.\.venv\Scripts\Activate.ps1

# Jeśli błąd ExecutionPolicy:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1

# Weryfikacja
python -c "import sys; print(sys.prefix)"
# Powinno pokazać ścieżkę do .venv
```

### 4.2 requirements.txt

```
# =====================================================
# CORE API
# =====================================================
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.3
pydantic-settings==2.7.0
python-dotenv==1.0.1
websockets==14.1
python-multipart==0.0.20

# =====================================================
# LLM CLIENT (OpenAI-compatible — LM Studio)
# =====================================================
openai==1.59.3
httpx==0.28.1

# =====================================================
# SPEECH — STT
# =====================================================
faster-whisper==1.1.1

# =====================================================
# SPEECH — Wakeword
# =====================================================
openwakeword==0.6.0

# =====================================================
# SPEECH — TTS (Piper jako binary — patrz sekcja 5.3)
# =====================================================
# Piper nie jest pip package — instalacja przez binary

# =====================================================
# VLM + OCR
# =====================================================
easyocr==1.7.2
Pillow==11.0.0
# Moondream2 przez transformers/huggingface_hub (patrz sekcja 5.5)
transformers==4.48.0
accelerate==1.3.0
huggingface-hub==0.27.0

# =====================================================
# SCREEN CAPTURE
# =====================================================
dxcam==0.0.5
pygetwindow==0.0.9

# =====================================================
# MEMORY — ChromaDB + Embeddings
# =====================================================
chromadb==0.6.3
sentence-transformers==3.3.1

# =====================================================
# MCP TOOLS
# =====================================================
duckduckgo-search==7.1.1
trafilatura==2.0.0
playwright==1.50.0
asteval==1.0.5

# =====================================================
# SYSTEM
# =====================================================
pynput==1.7.7
psutil==6.1.1
pywin32==308
watchdog==6.0.0
py7zr==0.22.0
tqdm==4.67.1

# =====================================================
# DEV / TEST
# =====================================================
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-mock==3.14.0
httpx==0.28.1  # test client
```

### 4.3 Instalacja

```powershell
# Upewnij się że venv aktywny
pip install --upgrade pip setuptools wheel

pip install -r requirements.txt

# Playwright — dodatkowy krok po pip install
playwright install chromium
# Rozmiar: ~300 MB (Chromium binary)

# Weryfikacja kluczowych importów
python -c "import fastapi, faster_whisper, chromadb, easyocr, dxcam; print('OK')"
```

> **Rozmiar instalacji łączny:** ~4–5 GB (PyTorch + wszystkie zależności)

### 4.4 Torch, transformers, PATH i konflikty wersji (Windows)

**Ten sam interpreter co backend.** Uruchamiaj backend (`uvicorn`, testy) tym Pythonem, którym instalowałeś pakiety — najlepiej **venv z repo** (`python -m venv .venv`, potem `.\scripts\setup.ps1`). Instalacja „user” (`Defaulting to user installation`) też działa, byle `**python` w terminalu** to był ten sam plik wykonywalny (`where python`).

**PATH i skrypty CLI.** Pip ostrzega, że `torchrun.exe`, `accelerate.exe`, `transformers.exe` trafiły np. do:

`%LOCALAPPDATA%\Programs\Python\Python3xx\Scripts` lub `%APPDATA%\Roaming\Python\Python3xx\Scripts`.

Do codziennego backendu **nie musisz** dodawać tego do PATH (wystarczy `python -m uvicorn …`). Dodaj katalog `Scripts` do PATH użytkownika tylko wtedy, gdy chcesz wygodnie wywoływać te narzędzia z dowolnego folderu.

**CUDA vs CPU.** Po `pip install torch` sprawdź:

```powershell
python -c "import torch; print(torch.__version__); print('cuda', torch.cuda.is_available())"
```

Jeśli w wersji Torch widzisz sufiks `**+cpu**` lub `cuda False`, a masz GPU NVIDIA — zainstaluj build z CUDA według [Get Started (PyTorch)](https://pytorch.org/get-started/locally/) (osobna komenda z `--index-url`). Backendowy moduł `Moondream2VLM` (`backend/ai/moondream_vlm.py`) używa `device: auto|cuda|cpu|mps` z `config.yaml`.

**setuptools.** Pakiet **torch** często wymusza `**setuptools<82`** — pip może **obniżyć** wersję setuptools. To oczekiwane; przy konfliktach z innymi projektami na tej samej instalacji Pythona użyj **osobnego venv** wyłącznie pod Assystenta.

**tokenizers.** **transformers** pinuje kompatybilną wersję **tokenizers** — nie podnoś jej ręcznie „na sztywno”, dopóki upstream tego nie wymaga.

**Włączenie VLM w konfiguracji** (`c:\ai\asystent\config\config.yaml` lub content root z `general.content_root`):

```yaml
vlm:
  enabled: true
  model_name: vikhyatk/moondream2
  revision: "2025-06-21"
  device: auto
```

Pierwsza inferencja pobierze wagi z Hugging Face (duży transfer).

---

## 5. Pobieranie modeli AI

### 5.1 Faster-Whisper medium (STT)


| Parametr         | Wartość                                          |
| ---------------- | ------------------------------------------------ |
| Rozmiar          | ~1.5 GB                                          |
| VRAM             | ~1.5 GB (int8) / ~3 GB (float16)                 |
| Źródło           | Hugging Face: `Systran/faster-whisper-medium`    |
| Ścieżka docelowa | `c:\ai\asystent\models\whisper\`                 |
| Alternatywa      | `faster-whisper-small` (~240 MB, mniej dokładny) |


```python
# scripts/download_models.py — fragment
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="Systran/faster-whisper-medium",
    local_dir=r"c:\ai\asystent\models\whisper",
    ignore_patterns=["*.msgpack", "*.h5"]
)
print("Faster-Whisper medium: OK")
```

**Weryfikacja:**

```python
from faster_whisper import WhisperModel
model = WhisperModel(r"c:\ai\asystent\models\whisper", device="cuda", compute_type="int8")
segments, _ = model.transcribe("test.wav")
print("STT: OK")
```

### 5.2 openWakeWord (wakeword detector)


| Parametr               | Wartość                             |
| ---------------------- | ----------------------------------- |
| Rozmiar                | ~50–200 MB (zależnie od modeli)     |
| VRAM                   | CPU only                            |
| Źródło                 | pip + auto-download przy imporcie   |
| Imiona (lista finalna) | Aria, Mira, Zara, Nova, Stella, Eve |
| Alternatywa fallback   | prebuilt "Hey Jarvis" model         |


```python
# Auto-download gotowych modeli przy pierwszym uruchomieniu
import openwakeword
openwakeword.utils.download_models()  # pobiera dostępne prebuilt models

# Weryfikacja dostępnych modeli
from openwakeword.model import Model
m = Model(wakeword_models=["hey_jarvis"])  # test z prebuilt
print("openWakeWord: OK")
```

> **Custom training dla imion Aria/Mira/Zara/Nova/Stella/Eve:**
> Wymaga nagrania ~50-100 próbek głosowych per imię. Skrypt treningowy
> w `scripts/train_wakeword.py` (do implementacji w Fazie 1).
> Do czasu wytrenowania — fallback: "Hey Jarvis".

### 5.3 Piper TTS (binary + głos PL żeński)


| Parametr       | Wartość                                   |
| -------------- | ----------------------------------------- |
| Binary rozmiar | ~15 MB                                    |
| Model głosu    | ~30–100 MB (zależnie od jakości)          |
| VRAM           | CPU only                                  |
| Ścieżka        | `c:\ai\asystent\models\piper\`            |
| Alternatywa    | XTTSv2 (wyższa jakość, ~2 GB, ~3 GB VRAM) |


**Krok 1 — Pobierz Piper binary:**

```powershell
# Z https://github.com/rhasspy/piper/releases (latest release)
# Pobierz: piper_windows_amd64.zip (~15 MB)
Expand-Archive piper_windows_amd64.zip -DestinationPath "c:\ai\asystent\models\piper"

# Weryfikacja
& "c:\ai\asystent\models\piper\piper.exe" --version
```

**Krok 2 — Skopiuj głos `gosia` (żeński PL, medium):**

Dostępne głosy PL w repozytorium (`C:\code\_repos\antigravity\piper-voices\pl\pl_PL\`):


| Głos        | Plik                          | Płeć     | Jakość | Licencja   |
| ----------- | ----------------------------- | -------- | ------ | ---------- |
| **gosia** ✅ | `pl_PL-gosia-medium.onnx`     | Żeński   | medium | CC0        |
| bass        | `pl_PL-bass-high.onnx`        | Męski    | high   | Apache 2.0 |
| darkman     | `pl_PL-darkman-medium.onnx`   | Męski    | medium | CC0        |
| mc_speech   | `pl_PL-mc_speech-medium.onnx` | nieznana | medium | CC0        |
| mls_6892    | `pl_PL-mls_6892-low.onnx`     | nieznana | low    | CC BY 4.0  |


**Domyślny: `gosia/medium`** — jedyny potwierdzony żeński głos PL.

```powershell
# Skopiuj głos gosia do content root
$src = "C:\code\_repos\antigravity\piper-voices\pl\pl_PL\gosia\medium"
$dst = "C:\ai\asystent\models\piper\gosia"

New-Item -ItemType Directory -Force -Path $dst
Copy-Item "$src\pl_PL-gosia-medium.onnx" $dst
Copy-Item "$src\pl_PL-gosia-medium.onnx.json" $dst

# Weryfikacja
ls $dst
# pl_PL-gosia-medium.onnx
# pl_PL-gosia-medium.onnx.json
```

**Config entry (config.yaml):**

```yaml
models:
  piper_voice_path: "C:\\ai\\asystent\\models\\piper\\gosia\\pl_PL-gosia-medium.onnx"
```

**Weryfikacja:**

```powershell
echo "Witaj, jestem gotowa do pomocy." | `
    & "C:\ai\asystent\models\piper\piper.exe" `
    --model "C:\ai\asystent\models\piper\gosia\pl_PL-gosia-medium.onnx" `
    --output-file test_tts.wav

# Odtwórz test_tts.wav — oczekiwany głos żeński PL
```

### 5.4 sentence-transformers (pamięć semantyczna)


| Parametr    | Wartość                                 |
| ----------- | --------------------------------------- |
| Model       | `paraphrase-multilingual-MiniLM-L12-v2` |
| Rozmiar     | ~120 MB                                 |
| VRAM        | CPU / GPU (auto)                        |
| Alternatywa | `all-MiniLM-L6-v2` (tylko EN, szybszy)  |


```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2",
    cache_folder=r"c:\ai\asystent\models\embeddings"
)
vec = model.encode("test zdanie po polsku")
print(f"Embedding dim: {len(vec)}")  # 384
print("sentence-transformers: OK")
```

### 5.5 Moondream2 (VLM — analiza screenów)


| Parametr    | Wartość                           |
| ----------- | --------------------------------- |
| Model       | `vikhyatk/moondream2`             |
| Rozmiar     | ~1.9 GB                           |
| VRAM        | ~2 GB (int8)                      |
| Ścieżka     | `c:\ai\asystent\models\moondream` |
| Alternatywa | LLaVA 7B (~4 GB, wyższa jakość)   |


```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="vikhyatk/moondream2",
    local_dir=r"c:\ai\asystent\models\moondream",
    ignore_patterns=["*.msgpack"]
)
print("Moondream2: OK")
```

**Weryfikacja (HF lub katalog lokalny — ten sam wzorzec co backend):**

```python
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForCausalLM

local_dir = Path(r"c:\ai\asystent\models\moondream")
repo_id = str(local_dir) if (local_dir / "config.json").is_file() else "vikhyatk/moondream2"

device_kind = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device_kind == "cuda" else torch.float32

load_kw = dict(trust_remote_code=True, torch_dtype=dtype, device_map={"": device_kind})
if repo_id == "vikhyatk/moondream2":
    load_kw["revision"] = "2025-06-21"

model = AutoModelForCausalLM.from_pretrained(repo_id, **load_kw)
img = Image.new("RGB", (64, 64), color=(40, 120, 200))
cap = model.caption(img, length="short", stream=False)
print("Moondream2:", cap.get("caption", cap))
```

### 5.6 EasyOCR (auto-download)


| Parametr              | Wartość                  |
| --------------------- | ------------------------ |
| Rozmiar auto-download | ~150 MB (PL + EN modele) |
| VRAM                  | ~0.5 GB (CUDA)           |
| Języki                | `pl`, `en`               |


```python
import easyocr

# Pierwszy run pobiera modele automatycznie do ~/.EasyOCR/
reader = easyocr.Reader(["pl", "en"], gpu=True)
result = reader.readtext(r"c:\temp\test.png")
print("EasyOCR: OK —", result[:2])
```

> **Uwaga:** EasyOCR zapisuje modele w `%USERPROFILE%\.EasyOCR\`. Nie w content root — ale to tylko cache, nie dane użytkownika.

### 5.7 Modele VRM (awatar 3D)


| Slot     | Plik                         | Opis                                          |
| -------- | ---------------------------- | --------------------------------------------- |
| Primary  | `models/avatar/primary.vrm`  | Główny awatar (żeński, anime, CC0/CC-BY)      |
| Fallback | `models/avatar/fallback.vrm` | Zapasowy (inny kolor/fryzura, ten sam zestaw) |


**Procedura wyboru i pobierania:**

1. Wejdź na **hub.vroid.com**
2. Filtruj: Autor = `VRoid Team` (oficjalne sample avatary pixiv)
3. Wybierz model żeński z **pełnymi blendshapes** i licencją CC0/CC-BY
4. Pobierz plik `.vrm` (< 30 MB)
5. Sprawdź blendshapes w VRoid Hub przed pobraniem (zakładka "Expressions")
6. Skopiuj jako `c:\ai\asystent\models\avatar\primary.vrm`
7. Wybierz drugi model (inna fryzura/kolor) jako `fallback.vrm`
8. Uzupełnij `c:\ai\asystent\LICENSES.md`:

```markdown
# LICENSES.md — Atrybucje modeli i zasobów

## Avatar — Primary VRM
- Nazwa modelu: [UZUPEŁNIJ]
- Autor: VRoid Team / pixiv Inc.
- URL: [UZUPEŁNIJ — hub.vroid.com/...]
- Licencja: CC0 / CC-BY 4.0
- Pobrano: [DATA]

## Avatar — Fallback VRM
- Nazwa modelu: [UZUPEŁNIJ]
- Autor: VRoid Team / pixiv Inc.
- URL: [UZUPEŁNIJ]
- Licencja: CC0 / CC-BY 4.0
- Pobrano: [DATA]
```

---

## 6. LM Studio setup

### 6.1 Instalacja i konfiguracja

```
1. Pobierz LM Studio z lmstudio.ai (Windows installer, ~300 MB)
2. Zainstaluj i uruchom
3. W wyszukiwarce modeli: wyszukaj "Gemma 4 E4B" lub "gemma-4-e4b"
4. Pobierz wersję Q4_K_M (~4 GB)
5. Załaduj model
```

**Ustawienia serwera (zakładka "Local Server"):**


| Ustawienie                        | Wartość                               |
| --------------------------------- | ------------------------------------- |
| Host                              | `127.0.0.1`                           |
| Port                              | `1234`                                |
| Enable CORS                       | ✅                                     |
| Allow tool use / function calling | ✅                                     |
| Context length                    | `8192` (minimum) / `16384` (zalecane) |
| GPU layers                        | `all` (pełna VRAM offload)            |


### 6.2 Weryfikacja

```powershell
# Test połączenia
curl http://127.0.0.1:1234/v1/models
# Oczekiwane: {"data": [{"id": "gemma-4-e4b...", ...}]}

# Test function calling
curl -s http://127.0.0.1:1234/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"auto","messages":[{"role":"user","content":"2+2=?"}],"max_tokens":50}'
# Oczekiwane: odpowiedź z "4"
```

### 6.3 Alternatywne modele (gdy Gemma 4 E4B niedostępny lub za wolny)


| Model               | Rozmiar | VRAM    | Uwagi                   |
| ------------------- | ------- | ------- | ----------------------- |
| Gemma 2 2B Q4_K_M   | ~1.5 GB | ~2 GB   | Szybszy, mniej dokładny |
| Llama 3.2 3B Q4_K_M | ~2 GB   | ~2.5 GB | Dobra alternatywa       |
| Qwen 2.5 7B Q4_K_M  | ~4.5 GB | ~5 GB   | Dobry w PL              |
| Mistral 7B Q4_K_M   | ~4 GB   | ~5 GB   | Sprawdzony, EN-first    |


> Wymóg dla każdego modelu: **function calling / tool use musi działać w LM Studio**.
> Zweryfikuj przed wyborem — nie wszystkie modele mają poprawne FC templates.

---

## 7. Frontend setup

### 7.1 Struktura projektu frontend

```
c:\code\_repos\antigravity\assystent\
├── backend\          # Python/FastAPI
├── frontend\         # Electron + React + Three.js
│   ├── package.json
│   ├── electron\     # main process
│   └── src\          # React renderer
└── shared\           # typy współdzielone
```

### 7.2 Instalacja zależności

```powershell
cd c:\code\_repos\antigravity\assystent\frontend

npm install

# Weryfikacja kluczowych pakietów
npm list three @pixiv/three-vrm electron react
```

**Kluczowe zależności package.json (docelowe):**

```json
{
  "dependencies": {
    "electron": "^31.0.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "three": "^0.169.0",
    "@pixiv/three-vrm": "^3.3.1"
  },
  "devDependencies": {
    "electron-builder": "^26.8.1",
    "vite": "^5.4.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.0"
  }
}
```

### 7.3 Build weryfikacja

```powershell
npm run build
# Oczekiwane: brak błędów, dist/ wypełniony

# Test uruchomienia (bez backendu)
npm run electron:dev
# Avatar window powinien się otworzyć (nawet bez połączenia z backendem)
```

### 7.4 Pakiet Windows (`electron-builder`)

- Ikona aplikacji / instalatora: repo trzyma `**frontend/resources/icon.png**`; ścieżka jest ustawiona w `frontend/package.json` → `**build.icon**`. Nie umieszczaj ikony pod `frontend/build/`, ponieważ w korzeniu repozytorium `.gitignore` ignoruje dowolny katalog `**build/**`.
- Instalacja NSIS (Windows): po `npm install` w `frontend/` — **`npm run electron:dist:client`** (tylko klient) oraz **`npm run electron:dist:full`** (klient + bundlowany kod backendu w `extraResources`; patrz `electron-builder.full.yml`). Oba kolejno: **`npm run electron:dist:all`**. Artefakty trafiają do **`electron-release-out/client/`** oraz **`electron-release-out/full/`** w korzeniu repozytorium. Historia zmian: `**CHANGELOG.md**` w korzeniu repo.

---

## 8. Pierwsze uruchomienie

### 8.1 Kolejność startowania komponentów

```
Krok 1  →  LM Studio        (załaduj model, uruchom serwer)
Krok 2  →  Backend Python   (FastAPI)
Krok 3  →  Frontend         (Electron)
```

> **Nigdy nie odwracaj kolejności.** Frontend przy starcie odpytuje backend o status;
> backend przy starcie odpytuje LM Studio. Oba muszą być gotowe wcześniej.

### 8.2a Windows — jednym kliknięciem (`scripts\start-dev.bat`)

Po jednorazowym `.\scripts\setup.ps1` (venv w `.venv`) oraz uruchomieniu **LM Studio** możesz odpalić środowisko dev z Eksploratora lub `cmd`:

1. Uruchom `**scripts\start-dev.bat`** (działa z dowolnego katalogu — skrypt przechodzi do rootu repo).
2. Skrypt otwiera **trzy** okna konsoli: `uvicorn … --reload` (port 8000), `npm run dev` / Vite (5173), Electron z `ASSYSTENT_DEV=1` (DevTools, ładuje `http://localhost:5173`). Przy pierwszym uruchomieniu, jeśli brak `frontend\node_modules`, wykona `npm ci`.
3. Zamknięcie danego okna zatrzymuje tylko ten proces. Jeśli Electron pokazuje pusty ekran, odczekaj na Vite lub uruchom ponownie tylko okno Electron (Vite nadal działa).

### 8.2 Start backend

```powershell
cd c:\code\_repos\antigravity\assystent
.\.venv\Scripts\Activate.ps1

uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

**Oczekiwane logi przy starcie:**

```
INFO: LM Studio connection: OK (latency: 14ms)
INFO: SQLite database: c:\ai\asystent\data\assystent.db
INFO: ChromaDB initialized: c:\ai\asystent\data\chroma
INFO: Faster-Whisper loaded (medium, CUDA, int8)
INFO: Piper TTS ready: pl_PL-{nazwa}-high
INFO: openWakeWord loaded (fallback: hey_jarvis)
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
```

### 8.3 Sanity check backend

```powershell
# Health check
curl http://127.0.0.1:8000/api/v1/health
# {"status":"ok","uptime_seconds":3}

# Pełny status
curl http://127.0.0.1:8000/api/v1/status
# Sprawdź: health_state = "healthy", wszystkie komponenty "up"

# Test STT (wymaga pliku WAV)
curl -X POST http://127.0.0.1:8000/api/v1/voice/transcribe `
  -F "audio=@test.wav" -F "language=pl"

# Test TTS
curl -X POST http://127.0.0.1:8000/api/v1/voice/synthesize `
  -H "Content-Type: application/json" `
  -d '{"text":"Witaj! Jestem gotowa.","emotion":"happy"}' `
  --output test_response.wav
```

### 8.4 Start frontend (ręcznie, zamiast `start-dev.bat`)

Dwa terminale w `frontend\` (najpierw Vite, potem Electron):

```powershell
cd c:\code\_repos\antigravity\assystent\frontend
npm run dev
```

```powershell
cd c:\code\_repos\antigravity\assystent\frontend
$env:ASSYSTENT_DEV = "1"
npm run electron
```

W `**cmd.exe`:** `set ASSYSTENT_DEV=1` przed `npm run electron`.

**Weryfikacja:**

- Okno avatara otwiera się (transparent, frameless, zawsze na wierzchu)
- Awatar VRM ładuje się i animuje (idle breathing)
- Status w logu: `WebSocket: connected to ws://127.0.0.1:8000/ws`
- PTT przycisk reaguje (domyślnie `Ctrl+Spacja` lub konfigurowalny)

---

## 9. Troubleshooting

### 9.1 CUDA Out of Memory (OOM)

**Objawy:** `RuntimeError: CUDA out of memory` przy ładowaniu modelu

**Rozwiązania:**

```powershell
# 1. Sprawdź zajętość VRAM
nvidia-smi

# 2. Zamknij inne procesy GPU (gry, inne modele)

# 3. Zmień compute_type na int8 (mniej VRAM)
# W config.yaml: models.whisper_compute_type: "int8"

# 4. Wyłącz VLM/OCR jeśli niepotrzebne
# W config.yaml: models.vlm_enabled: false
```

### 9.2 Piper TTS — brak głosu / cisza

**Objawy:** TTS endpoint zwraca 200 ale plik WAV jest pusty lub cichy

**Rozwiązania:**

```powershell
# 1. Test bezpośredni binary
echo "test" | & "c:\ai\asystent\models\piper\piper.exe" `
    --model "c:\ai\asystent\models\piper\{model}.onnx" `
    --output-file debug.wav

# 2. Sprawdź czy oba pliki istnieją (.onnx i .onnx.json)
ls "c:\ai\asystent\models\piper\"

# 3. Sprawdź ścieżkę w config.yaml: models.piper_voice_path
```

### 9.3 Mikrofon nie wykryty

**Objawy:** `GET /api/v1/audio/devices` nie zwraca mikrofonu lub STT nie reaguje

**Rozwiązania:**

```powershell
# 1. Sprawdź urządzenia audio w systemie
python -c "
import sounddevice as sd
print(sd.query_devices())
"

# 2. W config.yaml ustaw konkretne urządzenie:
# audio.input_device_id: "wasapi:{id}"

# 3. Sprawdź uprawnienia aplikacji do mikrofonu:
# Windows Settings → Privacy → Microphone → dopuść Python
```

### 9.4 Port 1234 zajęty (LM Studio)

**Objawy:** Backend loguje `Connection refused: http://127.0.0.1:1234`

**Rozwiązania:**

```powershell
# Znajdź co zajmuje port
netstat -ano | findstr ":1234"

# Sprawdź PID i zamknij:
taskkill /PID {pid} /F

# Lub zmień port LM Studio na 1235 i zaktualizuj config:
# ai.lm_studio_url: "http://127.0.0.1:1235/v1"
```

### 9.5 Antywirus blokuje DXcam

**Objawy:** `ImportError: DLL load failed` lub `Access denied` przy capture ekranu

**Rozwiązania:**

```powershell
# 1. Dodaj wyjątek antywirusowy dla katalogu .venv:
# C:\code\_repos\antigravity\assystent\.venv\Lib\site-packages\dxcam\

# 2. Uruchom jako Administrator (jednorazowo do weryfikacji)
# Jeśli działa → problem z uprawnieniami, nie AV

# 3. Alternatywa: użyj pyautogui jako fallback capture
# W config.yaml: observer.capture_backend: "pyautogui"
```

---

## 10. Skrypty pomocnicze

### 10.1 `scripts/setup.ps1` — Jednorazowy setup

Tworzy content root, venv, instaluje requirements, pobiera modele.

```powershell
# Uruchomienie:
cd c:\code\_repos\antigravity\assystent
.\scripts\setup.ps1

# Zakres:
# - Tworzy c:\ai\asystent\ ze strukturą katalogów
# - Tworzy .venv i instaluje requirements.txt
# - Instaluje playwright chromium
# - Uruchamia scripts/download_models.py
# - Uruchamia scripts/verify_env.py na końcu
```

### 10.2 `scripts/download_models.py` — Pobieranie modeli AI

```python
# Uruchomienie:
python scripts/download_models.py
# lub selektywnie:
python scripts/download_models.py --only whisper,moondream

# Modele:
# --only whisper     → Faster-Whisper medium
# --only embeddings  → sentence-transformers multilingual
# --only moondream   → Moondream2
# --only wakeword    → openWakeWord prebuilt models
# (piper i VRM: instrukcja manualna — wymagają interaktywnego wyboru)
```

### 10.3 `scripts/verify_env.py` — Weryfikacja środowiska

Sprawdza każdy komponent i raportuje status. Uruchom przed pierwszym startem i po każdej zmianie modeli.

```python
# Uruchomienie:
python scripts/verify_env.py

# Output (przykład):
# [OK]  Python 3.11.9
# [OK]  CUDA 12.4 — GPU: NVIDIA GeForce RTX 5090 (32480 MB VRAM)
# [OK]  FastAPI 0.115.6, Uvicorn 0.34.0
# [OK]  Faster-Whisper medium — c:\ai\asystent\models\whisper
# [OK]  Piper binary — c:\ai\asystent\models\piper\piper.exe
# [OK]  Piper voice — c:\ai\asystent\models\piper\{model}.onnx
# [OK]  openWakeWord — hey_jarvis (fallback)
# [OK]  Moondream2 — c:\ai\asystent\models\moondream
# [OK]  EasyOCR — pl, en
# [OK]  sentence-transformers multilingual-MiniLM-L12-v2
# [OK]  ChromaDB 0.6.3
# [OK]  Avatar primary.vrm — 18.4 MB
# [OK]  Avatar fallback.vrm — 21.2 MB
# [OK]  LM Studio — http://127.0.0.1:1234 (sprawdź ręcznie przed startem)
# [--]  LM Studio niedostępny — uruchom ręcznie przed startem backendu
#
# Wynik: 13/14 komponentów OK. Backend może startować (LM Studio wymagany).
```

---

## Checklista gotowości (pre-start)

Przed pierwszym uruchomieniem backendu, upewnij się:

- `python scripts/verify_env.py` → ≥ 13/14 OK
- LM Studio uruchomiony, model załadowany, serwer na porcie 1234
- `c:\ai\asystent\models\avatar\primary.vrm` istnieje
- `c:\ai\asystent\models\piper\{model}.onnx` istnieje
- `c:\ai\asystent\LICENSES.md` uzupełniony (atrybucje VRM)
- `c:\ai\asystent\config\config.yaml` skopiowany z `backend/config/config.default.yaml`
- Mikrofon widoczny w systemie Windows (Settings → Sound)
- Antywirus nie blokuje `.venv\Lib\site-packages\dxcam\`

---

## Reguły naczelne uwzględnione w tym dokumencie


| Reguła                        | Zastosowanie                                                                                                                    |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Offline-first**             | Wszystkie modele AI lokalne; brak wymagania internetu do startu                                                                 |
| **Sandbox twardy**            | Content root `c:\ai\asystent\` izolowany od code root; EasyOCR cache poza content root jest akceptowalny (nie dane użytkownika) |
| **Lokalność danych**          | Żaden model nie wysyła danych do chmury; HF download jednorazowy                                                                |
| **Modularność**               | Każdy komponent AI weryfikowany osobno (verify_env.py per-komponent)                                                            |
| **Polski domyślny**           | Piper: głos PL żeński; EasyOCR: `["pl", "en"]`; Whisper: `language=auto`                                                        |
| **env > config**              | Ścieżki modeli można nadpisać przez zmienne środowiskowe (WHISPER_MODEL_PATH, etc.)                                             |
| **Komunikacja błędów głosem** | verify_env.py identyfikuje brakujące modele; backend przy starcie loguje problem i informuje głosowo gdy TTS dostępny           |


---

## 11. Suplement (2026-05) — CORS, REST z przeglądarki, skrót `ASSY_*`

### 11.1 CORS — `ASSYSTENT_CORS_ORIGINS`


| Wartość                                                               | Zachowanie                                                                                              |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| *(puste)* lub `*`                                                     | `Access-Control-Allow-Origin: *`, **bez** nagłówka credentiale (zgodnie z ograniczeniami przeglądarek). |
| Lista po przecinku, np. `http://localhost:5173,http://127.0.0.1:5173` | Tylko te originy; **włączone** `Access-Control-Allow-Credentials`.                                      |


### 11.2 Prefiks konfiguracji `ASSY_*`

Ładowanie: domyślne Pydantic → YAML w `content_root` (`config/config.yaml`) → nadpisania **ENV** `ASSY_<sekcja>__<pole>` (podwójne `__` dla zagnieżdżeń), np. `ASSY_LLM__API_BASE_URL`, `ASSY_MEMORY__ENABLED`. Szczegóły: `backend/config/loader.py`, model: `backend/config/schema.py`.

**Observer — auto sprawdzenie ligi przy wykryciu gry (T8):**


| ENV                                                | Wartość      | Skutek                                                                                                                                                                                                                                                                                                                                                                                                                                |
| -------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ASSY_OBSERVER__AUTO_LEAGUE_HINT_ON_GAME_DETECTED` | `1` / `true` | Po zdarzeniu `game_detected`, gdy backend zna `**game_id`** profilu (klucz w `player_profile.yaml`), uruchamiany jest `check-league-hint`; przy rozbieżności z wynikiem `web_search` nadawane jest WS `player_profile.league_hint`. W YAML: `observer.auto_league_hint_on_game_detected: true`. Wymaga włączonego MCP z narzędziem `web_search`; gdy MCP wyłączone lub brak dopasowania profilu, nic się nie dzieje (bez błędu w UI). |


### 11.3 Frontend / Electron (preload)


| Zmienna                                   | Zastosowanie                                  |
| ----------------------------------------- | --------------------------------------------- |
| `ASSYSTENT_WS_URL` / `VITE_WS_URL`        | Pełny URL WebSocket (`/ws`).                  |
| `ASSYSTENT_API_URL` / `VITE_API_BASE_URL` | Bazowy URL HTTP (`/api/v1/...`).              |
| `ASSYSTENT_VRM_URL` / `VITE_VRM_URL`      | Opcjonalny domyślny URL modelu VRM.           |
| `ASSYSTENT_DEV`                           | `1` — Electron ładuje serwer Vite i DevTools. |


### 11.4 `PUT /api/v1/config` (FastAPI)

Częściowy merge JSON do istniejącego pliku YAML w `content_root` (wymaga zapisanego `config/config.yaml`); po sukcesie **hot-reload** (`apply_reload_configuration`). Przykład z UI: panel **Więcej** → prędkość TTS (`tts.voice_speed`).

### 11.5 Ochrona zapisu konfiguracji — `ASSYSTENT_CONFIG_PUT_TOKEN`

Jeśli ustawione (niepusty string), każde `**PUT /api/v1/config`** musi przekazać ten sam sekret w nagłówku `**X-Config-Put-Token`** albo `**Authorization: Bearer <token>`** (stała długość porównania, `hmac.compare_digest`). Gdy zmienna nie jest ustawiona, endpoint zachowuje się jak wcześniej (tylko sieć lokalna / zaufana).

Frontend: opcjonalnie `VITE_CONFIG_PUT_TOKEN`, preload `ASSYSTENT_CONFIG_PUT_TOKEN` → `window.assystent.configPutToken`, albo ręcznie `localStorage.setItem('assystent.configPutToken', '…')`.