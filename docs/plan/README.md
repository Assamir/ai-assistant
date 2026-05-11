# Folder `docs/plan` — porządek i nawigacja

Materiały planistyczne i status wdrożenia produktu Assystent.

## Od czego zacząć

| Priorytet | Dokument | Po co |
|-----------|-----------|--------|
| **1** | [**STAN_IMPLEMENTACJI.md**](STAN_IMPLEMENTACJI.md) | Jedna tabela **aktualnego** stanu wdrożenia w kodzie |
| **2** | [DEFINITION_OF_DONE.md](DEFINITION_OF_DONE.md) | Kryteria akceptacji faz MVP (checkboxy `[x]` / `[~]` / `[ ]`) |
| **3** | [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) | Roadmapa tygodniowa (szacunki, kamienie milowe — kontekst historyczny) |

## Pozostałe pliki (rola)

| Plik | Rola |
|------|------|
| [implementation_plan.md](implementation_plan.md) | Szczegółowy plan implementacji (część 1) |
| [implementation_plan_part2.md](implementation_plan_part2.md) | Szczegółowy plan implementacji (część 2) |
| [TEST_PLAN.md](TEST_PLAN.md) | Identyfikatory testów i zakres |
| [RISK_REGISTER.md](RISK_REGISTER.md) | Rejestr ryzyk |
| [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md) | Backlog IMP-01 … IMP-04 (koszt, ROI) |
| [PERFORMANCE_BASELINE.md](PERFORMANCE_BASELINE.md) | Szablon pomiarów FPS / latencji (wypełnianie ręczne) |

## Zasady porządku

- **Stan „czy mamy to w repo?”** — aktualizuj w **STAN_IMPLEMENTACJI.md**, nie w wielu tabelach naraz.
- **Czy spełniliśmy Definition of Done** — tylko w **DEFINITION_OF_DONE.md**.
- Roadmapa tygodniowa **nie zastępuje** tabeli stanu — opisuje kolejność/historię pracy.

## Powiązania poza folderem

- Architektura i konwencje: [../DECISIONS_LOG.md](../DECISIONS_LOG.md), [../PRD_06_IMPLEMENTATION.md](../PRD_06_IMPLEMENTATION.md)
- Zmiany wydaniowe: [../../CHANGELOG.md](../../CHANGELOG.md)
