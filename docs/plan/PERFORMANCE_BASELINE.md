# Performance baseline (Assystent)

Procedura zgodna z [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) (Faza 1 §C — FPS i latencja PTT→audio): **metologia poza CI**, zapis tutaj przy pierwszym pomiarze lub dopisz „do zmierzenia”.

## FPS — wpływ < 5%

- **Środowisko:** (GPU, sterownik, rozdzielczość, gra, wersja buildu Asystenta).
- **Metoda:** benchmark wbudowany w grę lub PresentMon / RTSS; porównanie średniego FPS **bez** overlayu Asystenta vs **z** uruchomionym backendem + Electron overlay (idle).
- **Wynik:** _do zmierzenia_
- **Data / osoba:** _

## PTT → pierwsze audio < 3 s

- **Środowisko:** LM Studio (model), rozmiar kontekstu, urządzenie audio.
- **Metoda:** znacznik czasu po `ptt_end` (frontend lub log WS) vs pierwszy odebrany `audio_stream`; średnia z N prób (np. N=10).
- **Wynik:** _do zmierzenia_
- **Uwaga:** cel jest **end-to-end** (STT + LLM + TTS + sieć lokalna); backend-only można szacować osobno z mockami.

## Observer — cykl capture → komentarz

- Docelowo < 5 s (plan testów); **wynik:** _do zmierzenia_
