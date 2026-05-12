"""Budowa promptów dla LLM — DOK-05 §1–3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Literal, Optional

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None


OutputMode = Literal["voice", "text"]


_FORMAT_SECTION_VOICE = """## FORMAT ODPOWIEDZI

Twoje odpowiedzi są czytane głosem przez syntezator mowy. Zasady:
- Odpowiadaj krótkimi zdaniami (styl mówiony, nie pisany).
- Gdy to jest rozmowa swobodna, staraj się zmieścić odpowiedź w ~80 słowach. Gdy temat wymaga więcej — możesz przekroczyć ten limit.
- Nie używaj markdown (gwiazdki, nagłówki, listy z myślnikami) — i tak nie zostanie odczytany poprawnie.
- Nie zaczynaj od "Oczywiście!", "Jasne!" ani podobnych wstępów. Przejdź od razu do meritum.
- Każdą odpowiedź zacznij od tagu emocji: [EMO:nazwa] — dokładnie jeden tag, na samym początku, bez spacji przed. Lista dozwolonych tagów: happy, amused, proud, sympathetic, sad, disappointed, angry, disgusted, excited, scared, surprised, nervous, thinking, confused, nostalgic, sarcastic."""


_FORMAT_SECTION_TEXT = """## FORMAT ODPOWIEDZI

Odpowiedź wyświetlana jest jako tekst w panelu czatu — bez TTS. Dlatego:
- **Dopasuj długość do tematu.** Krótkie pytanie (np. "która godzina?", "cześć") → 1 zdanie. Pytanie wymagające analizy (build, porównanie, poradnik, "jak grać X", "co lepsze A czy B", "doradź") → **3–8 akapitów konkretu** z listami punktowanymi, danymi, rekomendacją na końcu. Pytanie o fakt → 2–4 zdania.
- **Nie skracaj na siłę.** Lepiej dać kompletną odpowiedź z konkretami niż lakoniczne zdanie. Jeśli temat ma kilka aspektów — wymień każdy.
- **Markdown dozwolony i zalecany**: nagłówki `##`, listy `-`, **pogrubienia**, tabele dla porównań. Nie używaj kodu trzy-backtickowego dla zwykłego tekstu.
- Nie zaczynaj od "Oczywiście!", "Jasne!" ani podobnych wstępów. Przejdź od razu do meritum.
- Każdą odpowiedź zacznij od tagu emocji: [EMO:nazwa] — dokładnie jeden tag, na samym początku, bez spacji przed. Lista dozwolonych tagów: happy, amused, proud, sympathetic, sad, disappointed, angry, disgusted, excited, scared, surprised, nervous, thinking, confused, nostalgic, sarcastic."""


_SECTION_TOOLS_COMPACT = """## NARZĘDZIA

Masz funkcje (definicje w `tools`). Krótkie zasady:
- `web_search` — aktualne info (meta gry, ceny, patche). Nie szukaj faktów stałych.
- `web_scraper` — gdy masz konkretny URL.
- `get_current_time` — przy "teraz/dziś/godzina".
- `calculator` — liczby (DPS, %).
- `generate_document` — długie raporty/zestawienia zamiast czytać głosem.
- `screen_capture` — "co widzisz na ekranie". Czytaj `summary`/`description` z `ok:true`; przy `ok:false` przekaż `error`. Nie mów "nie mam dostępu" gdy JSON potwierdza sukces.

Nie wywołuj tego samego narzędzia dwukrotnie z identycznym argumentem w jednej turze. Po otrzymaniu wyniku narzędzia ZAWSZE syntezuj go w finalną odpowiedź po polsku — nie pozostawiaj surowego JSON-a, nie milcz."""


_SECTION_AGENTIC = """## PLANOWANIE AGENTOWE

Gdy zadanie wymaga wielu kroków: `plan_create` (2–6 kroków) → `task_start` → `task_done` per krok → `work_evaluate`. `task_revise` przy zmianie planu. `note_save`/`notes_get` na fakty. Nie planuj prostych pytań."""


_SECTION_THREADS = """## WĄTEK

W kontekście może być sekcja AKTYWNY_WATEK — jesteś w trwającym wątku.
- Ważna decyzja użytkownika → `thread_add_decision`.
- Zmiana kierunku → `thread_add_direction`.
- 3+ wiadomości temu temu → `thread_summarize` (krótki tytuł).
- "Wróć do tematu X" → `thread_search` → `thread_resume`."""


_BASE_PROMPT_HEAD = """Jesteś lokalnym asystentem AI o imieniu {assistant_name}. Działasz na komputerze użytkownika — bez chmury. Masz awatar 3D i rozmawiasz głosowo.

## JĘZYK

**ZAWSZE odpowiadaj wyłącznie po polsku.** Nigdy nie używaj chińskiego, japońskiego ani innych znaków nie-łacińskich. Jeśli użytkownik prosi o angielski — odpowiedz po angielsku tylko na tę jedną wiadomość, potem wracaj do polskiego. Nazwy gier, filmów, książek, seriali — w oryginale (Path of Exile 2, Stellaris, Baldur's Gate 3 — nigdy "Ścieżka Wygnańca").

{format_section}

## ZERO HALUCYNACJI

Jeśli nie znasz odpowiedzi i narzędzia nie pomogły — powiedz wprost "nie wiem". Nigdy nie wymyślaj faktów, dat, statystyk, nazw ani szczegółów o grach.

{tools_section}{optional_sections}

## SANDBOX

Nie możesz otwierać aplikacji, zmieniać OS, usuwać plików poza `{content_root}`. Jeśli prośba wykracza poza twoje możliwości — powiedz to prosto, bez przepraszania.

## TOŻSAMOŚĆ

Jesteś asystentem AI — nie udawaj człowieka. Gdy zapytany — odpowiedz prawdziwie. Masz osobowość (Persona poniżej), ale jesteś asystentem.
"""


def _format_section_for_mode(mode: OutputMode) -> str:
    return _FORMAT_SECTION_TEXT if mode == "text" else _FORMAT_SECTION_VOICE


def _build_base_prompt(
    *,
    assistant_name: str,
    content_root: str,
    output_mode: OutputMode,
    include_agentic_section: bool = True,
    include_threads_section: bool = True,
) -> str:
    optional = ""
    if include_agentic_section:
        optional += "\n\n" + _SECTION_AGENTIC
    if include_threads_section:
        optional += "\n\n" + _SECTION_THREADS
    return _BASE_PROMPT_HEAD.format(
        assistant_name=assistant_name,
        content_root=content_root,
        format_section=_format_section_for_mode(output_mode),
        tools_section=_SECTION_TOOLS_COMPACT,
        optional_sections=optional,
    )


# Backwards-compat: voice-mode pełny prompt z placeholderami nadal eksponowany dla testów i zewn. importów.
BASE_PROMPT_TEMPLATE = _BASE_PROMPT_HEAD.format(
    format_section=_FORMAT_SECTION_VOICE,
    tools_section=_SECTION_TOOLS_COMPACT,
    optional_sections="\n\n" + _SECTION_AGENTIC + "\n\n" + _SECTION_THREADS,
    assistant_name="{assistant_name}",
    content_root="{content_root}",
)


def _build_language_instruction(language_override: Optional[str]) -> str:
    if language_override == "en":
        return (
            "\n\n[LANGUAGE: Respond in English for this single message only. "
            "Return to Polish afterwards.]"
        )
    return ""


def _tiktoken_encoding():
    if tiktoken is None:
        return None
    return tiktoken.get_encoding("cl100k_base")


@dataclass
class PromptBudget:
    count_fn: Callable[[str], int]
    max_tokens: int


class PromptBuilder:
    """Składa sekcje systemowe + przycina historię wg budżetu tokenów."""

    def __init__(self, max_context_tokens: int = 4096) -> None:
        self.max_context_tokens = max_context_tokens
        enc = _tiktoken_encoding()
        if enc:

            def _count(t: str) -> int:
                return len(enc.encode(t))

            self._count = _count
        else:

            def _count_fallback(t: str) -> int:
                return max(1, len(t) // 4)

            self._count = _count_fallback

    def estimate_tokens(self, text: str) -> int:
        return self._count(text)

    def build_messages(
        self,
        *,
        assistant_name: str,
        content_root: str,
        persona_body_markdown: str,
        history_messages: List[Dict[str, Any]],
        observer_context: Optional[str] = None,
        game_profile_context: Optional[str] = None,
        player_profile_summary: Optional[str] = None,
        memory_prefix: Optional[str] = None,
        language_override: Optional[str] = None,
        max_context_tokens: Optional[int] = None,
        thread_context_block: Optional[str] = None,
        agent_plan_block: Optional[str] = None,
        output_mode: OutputMode = "voice",
        include_agentic_section: bool = True,
        include_threads_section: bool = True,
    ) -> List[Dict[str, Any]]:
        budget_limit = max_context_tokens or self.max_context_tokens

        base = _build_base_prompt(
            assistant_name=assistant_name,
            content_root=content_root,
            output_mode=output_mode,
            include_agentic_section=include_agentic_section,
            include_threads_section=include_threads_section,
        )
        persona_section = "\n\n## PERSONA\n\n" + persona_body_markdown.strip()
        lang_instruction = _build_language_instruction(language_override)

        optional_blocks: List[str] = []
        labels = []

        def _labeled_block(label: str, content: Optional[str]) -> None:
            if content and content.strip():
                optional_blocks.append(f"\n\n## {label}\n\n{content.strip()}")
                labels.append(label)

        _labeled_block("OBSERVER_CONTEXT", observer_context)
        _labeled_block("GAME_PROFILE", game_profile_context)
        _labeled_block("PLAYER_PROFILE_SUMMARY", player_profile_summary)
        _labeled_block("AKTYWNY_WATEK", thread_context_block)
        _labeled_block("PLAN_AGENTOWY", agent_plan_block)

        optional_joined = "".join(optional_blocks)

        fixed_core = base + persona_section + optional_joined + lang_instruction
        fixed_tokens = self._count(fixed_core)

        avail_history = budget_limit - fixed_tokens
        if avail_history < 0:
            optional_joined, optional_tokens = self._shrink_optional(
                optional_joined,
                avail_needed=fixed_tokens - budget_limit,
            )
            fixed_core = base + persona_section + optional_joined + lang_instruction
            fixed_tokens = self._count(fixed_core)
            avail_history = budget_limit - fixed_tokens

        mem_block = ""
        mem_tokens = 0
        if memory_prefix and memory_prefix.strip():
            mem_block = memory_prefix.strip()
            mem_tokens = self._count(mem_block)
            avail_history -= mem_tokens
            while avail_history < 0 and mem_block:
                mem_block = self._truncate_chars(mem_block, len(mem_block) - 200)
                if not mem_block:
                    break
                mem_tokens = self._count(mem_block)
                avail_history = budget_limit - fixed_tokens - mem_tokens

        trimmed_history = _trim_history(history_messages, max(0, avail_history), self._count)

        messages: List[Dict[str, Any]] = []
        if mem_block:
            messages.append({"role": "system", "content": f"[MEMORY]\n{mem_block}"})
        messages.append({"role": "system", "content": fixed_core})
        messages.extend(trimmed_history)
        return messages

    def _shrink_optional(self, optional_joined: str, *, avail_needed: int) -> tuple[str, int]:
        """Przytnij od końca bloki opcjonalne, aż zaoszczędzimy ~avail_needed tokenów."""
        if not optional_joined or avail_needed <= 0:
            return optional_joined, self._count(optional_joined)
        trimmed = optional_joined
        saved = 0
        while saved < avail_needed and trimmed:
            before = self._count(trimmed)
            step = max(300, avail_needed // 2)
            trimmed = self._truncate_chars(trimmed, max(0, len(trimmed) - step))
            after = self._count(trimmed)
            saved += before - after
            if len(trimmed) == 0:
                break
        return trimmed, self._count(trimmed)

    @staticmethod
    def _truncate_chars(text: str, max_chars: int) -> str:
        max_chars = max(0, min(max_chars, len(text)))
        return text[:max_chars]


def _trim_history(
    messages: List[Dict[str, Any]],
    budget: int,
    count: Callable[[str], int],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    used = 0
    if budget <= 0:
        return result
    for msg in reversed(messages):
        raw = msg.get("content")
        if raw is None:
            continue
        content = raw if isinstance(raw, str) else str(raw)
        tokens = max(1, count(content))
        if used + tokens > budget:
            break
        item = dict(msg)
        item["content"] = content
        result.insert(0, item)
        used += tokens
    return result


__all__ = ["BASE_PROMPT_TEMPLATE", "PromptBuilder", "PromptBudget"]
