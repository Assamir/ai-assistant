Assystent — instalator KOMPLET (klient + kod backendu)
=======================================================

Ten pakiet zawiera aplikację Electron oraz katalog Pythona (backend FastAPI)
w plikach aplikacji — zwykle pod:
  …\Assystent Komplet\resources\bundled\python-app\


Wymagania
---------
1) Python 3.11+ dodany do PATH (polecenie „python” lub „py -3.11” w CMD).
2) LM Studio (lub inny endpoint OpenAI-compatible), jeśli korzystasz z LLM —
   patrz docs/ENV_SETUP.md w repozytorium projektu.
3) content_root / config — jak w dokumentacji (np. c:\ai\asystent).


Pierwszy raz — zależności pip
-----------------------------
Zainstaluj paczki dla bundlowanego backendu (jednorazowo):

  a) Otwórz Eksplorator: w katalogu instalacji wejdź do
     resources\bundled\docs
  b) Uruchom:  Pierwsze-zaleznosci-backend.bat

Albo ręcznie w CMD (dopasuj ścieżkę do instalacji):

  cd "C:\Program Files\Assystent Komplet\resources\bundled\python-app"
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt


Uruchamianie
------------
Dwukrotne kliknięcie „Assystent Komplet” uruchomi klienta.
Przy pierwszym starcie aplikacja próbuje odpalić backend
(uvicorn backend.main:app na 127.0.0.1:8000), jeśli wykryje
bundlowany katalog i nie ustawiono zmiennej ASSYSTENT_NO_AUTO_BACKEND=1.


Wyłączenie autostartu backendu
--------------------------------
Zmienna środowiskowa użytkownika lub systemu:
  ASSYSTENT_NO_AUTO_BACKEND=1
Wtedy backend musisz uruchomić samodzielnie (np. uvicorn jak w dokumentacji).


Wersja tylko klienta (mniejsza)
-------------------------------
Osobny instalator: „Assystent-Client-Setup-…exe” — bez Pythona w pakiecie.
