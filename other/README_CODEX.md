# Готовый пакет для Codex

## Активная структура
Код, конфигурация, тесты и блокнот находятся в src/, config/, tests/ и notebooks/. Единственный активный Excel — other/dataset_vtb_main_clean.xlsx, лист DATA_MASTER. Старые реализации и данные внутри other/ являются архивом; их не нужно копировать поверх активного кода.

## Первый запуск в Codex
После того как файлы появились в репозитории:
1. Откройте репозиторий в Codex.
2. Отправьте Codex содержимое `other/CODEX_START_PROMPT.txt` одним сообщением.
3. Разрешите ему прочитать репозиторий и запустить терминальные команды.
4. Он должен сначала сделать source/data QA, затем тесты, затем полный расчет.

## Команды в терминале
```bash
python -m pip install -r other/requirements.txt
pytest -q
python src/stress_model.py --config config/model_config.json
```

Результаты появляются в `outputs/`.

## Как менять методологию дальше
Пишите Codex:

`UPDATE_CONTEXT: <что изменить>`

Пример:

`UPDATE_CONTEXT: Severe credit-cost shock для Auto увеличь, а portfolio-mix sensitivity пока оставь без изменений.`

Codex должен обновить контекст, config, затронутый код/тесты и `other/CONTEXT_CHANGELOG.md`, затем перезапустить QA.

## Главные файлы
- `AGENTS.md` — короткий указатель на канонический контекст.
- `other/AGENTS.md` — постоянные правила проекта.
- `other/DECISIONS_1_18.md` — история решений 1–18; приоритет у текущего MODEL_DECISIONS.md.
- `other/MODEL_DECISIONS.md` — математическая методология.
- `other/DATA_GAPS_AND_FALLBACKS.md` — что есть/чего не хватает и что делать при отсутствии данных.
- `other/DATA_ADEQUACY_2023_2026H1.md` — почему текущего ряда достаточно именно для scenario stress test.
- `config/model_config.json` — рабочие численные сценарные настройки.
- `src/stress_model.py` — модель.
- `tests/test_stress_model.py` — автоматические проверки.
- `other/TERMINOLOGY_RU.md` — переводы терминов и расшифровки сокращений; исследовательские материалы и ответы пользователю готовятся преимущественно на русском.
