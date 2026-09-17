"""Reproduce the one-time v2/clean workbook comparison; never a model fallback."""
from hashlib import sha256
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from stress_model import load_dataset, PRODUCTS


def main():
    old_path = ROOT / "other/dataset_vtb_main_v2.xlsx"
    clean_path = ROOT / "other/dataset_vtb_main_clean.xlsx"
    old = load_dataset(old_path)
    clean = load_dataset(clean_path)
    same = old.equals(clean)
    lines = ["# Сравнение Excel: v2 и clean — 17.09.2026", "",
             "Сравнение воспроизводится: python scripts/compare_datasets.py.", "",
             "## Структура и содержимое", ""]
    for path, frame in [(old_path, old), (clean_path, clean)]:
        lines += [f"- {path.name}: листы {pd.ExcelFile(path).sheet_names}; "
                  f"DATA_MASTER: {len(frame)} строк, {len(frame.columns)} полей.",
                  f"  SHA-256: {sha256(path.read_bytes()).hexdigest()}"]
    lines += ["", f"Совпадение всех нормализованных строк DATA_MASTER: {same}.", ""]
    if same:
        lines += ["Экспозиции, резервы, переоценка ECL, кредитные ставки и фондирование совпадают "
                  "для всей истории, включая 2025YE и 2026H1. Clean содержит дополнительный MODEL_DATA "
                  "с предыдущей синтетической доходной спецификацией и расширенный список SOURCES. "
                  "Это расширенная версия того же набора компонент; её актуальность следует из выбора пользователя, "
                  "а не из различий в числах или независимого подтверждения источников.", ""]
    else:
        lines += ["Обнаружены различия; активный clean не подменяется старым файлом.", "",
                  old.set_index(["report_date", "product"]).compare(
                      clean.set_index(["report_date", "product"])).to_markdown(), ""]
    for date in ["2025-12-31", "2026-06-30"]:
        view = clean[clean.report_date.eq(pd.Timestamp(date))].set_index("product").reindex(PRODUCTS).reset_index()
        lines += [f"## Компоненты {date} из clean", "",
                  "Денежные значения — млрд руб., ставки — доли единицы. Pricing ипотеки здесь — "
                  "исходная ставка Excel; основной MARKET PROXY 17,8% задаётся отдельно в конфигурации.", "",
                  view.drop(columns="report_date").to_markdown(index=False, floatfmt=".6f"), ""]
    lines += ["Единственный активный input: other/dataset_vtb_main_clean.xlsx / DATA_MASTER. "
              "MODEL_DATA не используется: в новой постановке нужны прямые ECL-компоненты, pricing и funding. "
              "Файл Excel не редактировался; числа в модель не переписывались вручную.", "",
              "Ни равенство файловых данных, ни арифметическая сверка не заменяют постраничную проверку "
              "отчётности ВТБ. Её статус остаётся PENDING; см. SOURCE_QA_2026H1.md.", ""]
    destination = ROOT / "other/DATASET_COMPARISON_2026-09-17.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"DATA_MASTER equal={same}; comparison written to {destination.name}")


if __name__ == "__main__":
    main()
