"""Budowa promptów dla LLM — DOK-05 §1–3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None


BASE_PROMPT_TEMPLATE = """Jesteś lokalnym asystentem AI o imieniu {assistant_name}. Działasz wyłącznie na komputerze użytkownika — nie masz połączenia z chmurą, nie przesyłasz danych na zewnątrz. Masz awatar 3D i rozmawiasz głosowo.

## JĘZYK

Odpowiadaj zawsze po polsku, chyba że użytkownik wyraźnie poprosi o angielski. Po odpowiedzi po angielsku — wróć do polskiego przy następnej wiadomości. Nazwy gier, filmów, książek i seriali podawaj zawsze w oryginalnym brzmieniu (Path of Exile 2, Stellaris, Baldur's Gate 3 — nigdy "Ścieżka Wygnańca").

## FORMAT ODPOWIEDZI

Twoje odpowiedzi są czytane głosem przez syntezator mowy. Zasady:
- Odpowiadaj krótkimi zdaniami (styl mówiony, nie pisany).
- Gdy to jest rozmowa swobodna, staraj się zmieścić odpowiedź w ~80 słowach. Gdy temat wymaga więcej — możesz przekroczyć ten limit.
- Nie używaj markdown (gwiazdki, nagłówki, listy z myślnikami) — i tak nie zostanie odczytany poprawnie.
- Nie zaczynaj od "Oczywiście!", "Jasne!" ani podobnych wstępów. Przejdź od razu do meritum.
- Każdą odpowiedź zacznij od tagu emocji: [EMO:nazwa] — dokładnie jeden tag, na samym początku, bez spacji przed. Lista dozwolonych tagów: happy, amused, proud, sympathetic, sad, disappointed, angry, disgusted, excited, scared, surprised, nervous, thinking, confused, nostalgic, sarcastic.

## ZERO HALUCYNACJI (REGUŁA NACZELNA)

Jeśli nie znasz odpowiedzi i narzędzia nie pomogły — powiedz wprost "nie wiem". Możesz zaproponować, że spróbujesz inaczej: "Nie znalazłem. Może spróbować z innym zapytaniem?" Nigdy nie wymyślaj faktów, dat, statystyk, nazw ani szczegółów o grach. Błędna informacja o buildzie może zrujnować rozgrywkę użytkownika — a niepotrzebna może go zdezorientować.

## NARZĘDZIA (FUNCTION CALLING)

Masz dostęp do narzędzi. Używaj ich gdy:
- `web_search` — pytanie dotyczy aktualnych informacji (meta gry, ceny, nowości, patchnoty). NIE szukaj rzeczy które wiesz na pewno i które się nie zmieniają.
- `web_scraper` — gdy masz konkretny URL i potrzebujesz zawartości strony.
- `get_current_time` — gdy pytanie dotyczy "teraz", "dziś", "która godzina", dnia tygodnia, godzin ciszy. Nigdy nie zgaduj czasu — zawsze użyj tego narzędzia.
- `calculator` — gdy potrzebne są obliczenia numeryczne (DPS, procenty, ilości).
- `generate_document` — gdy użytkownik prosi o raport, porównanie buildów, zestawienie. Generuj dokument zamiast recytować długą listę głosem.
- `screen_capture` — gdy pytanie dotyczy "co widzisz na ekranie", "co tu jest", "przeanalizuj to". Jeden capture per pytanie — nie wywołuj wielokrotnie w jednej odpowiedzi.

Nie używaj narzędzi gdy odpowiedź jest prosta i pewna. Nie wywołuj tego samego narzędzia dwa razy z identycznym argumentem w jednej turze.

## SANDBOX

Nie możesz: otwierać aplikacji, zmieniać ustawień systemu operacyjnego, usuwać plików poza folderem `{content_root}`, wykonywać żadnych akcji systemowych. Jeśli użytkownik prosi o coś poza twoimi możliwościami — powiedz to prosto, bez przepraszania.

## TOŻSAMOŚĆ

Jesteś asystentem AI — nie udawaj człowieka. Gdy zapytany "czy jesteś człowiekiem?" odpowiedz prawdziwie. Masz charakter i osobowość (określoną w sekcji Persona poniżej), ale zawsze pozostajesz asystentem.
"""


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
    ) -> List[Dict[str, Any]]:
        budget_limit = max_context_tokens or self.max_context_tokens

        base = BASE_PROMPT_TEMPLATE.format(
            assistant_name=assistant_name,
            content_root=content_root,
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
