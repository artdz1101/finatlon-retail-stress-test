#!/usr/bin/env python3
"""Reproducible four-product retail credit portfolio stress test.

The model is designed for a scientific article and uses the public-source
repository dataset plus transparent external rate proxies and configurable
scenario assumptions. It does not reconstruct VTB internal profitability,
FTP, RWA, limits or management metrics.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRODUCTS = ["Mortgage", "Consumer", "Auto", "Cards"]
RISKIER_PRODUCTS = ["Consumer", "Auto", "Cards"]
SCENARIO_ORDER = ["Base", "Moderate", "Severe", "PortfolioMix", "SevereMix"]
SCENARIO_ALIASES = {"Structural": "PortfolioMix", "Combined": "SevereMix"}
SCENARIO_LABELS = {"Base": "Базовый", "Moderate": "Умеренный", "Severe": "Тяжёлый", "PortfolioMix": "Изменение состава", "SevereMix": "Тяжёлый + изменение состава"}
SCENARIO_TYPES = {"Base": "baseline", "Moderate": "financial_stress", "Severe": "financial_stress", "PortfolioMix": "portfolio_mix", "SevereMix": "combined"}
PRODUCT_LABELS = {"Mortgage": "Ипотека", "Consumer": "Потребительские кредиты", "Auto": "Автокредиты", "Cards": "Кредитные карты", "ALL": "Весь портфель"}
STATUS_LABELS = {
    "FEASIBLE": "Допустимое решение",
    "ALREADY_AT_OR_BELOW_BOUNDARY": "Исходный результат уже на критической границе или ниже",
    "THRESHOLD_BELOW_CURRENT_1X": "Граница требует снижения текущей стоимости кредитного риска",
    "NO_NONNEGATIVE_SOLUTION": "Неотрицательное решение отсутствует",
    "NO_CREDIT_LOSS_BASE": "В исходном варианте нет кредитных потерь",
    "NO_NONNEGATIVE_BREAK_EVEN": "Неотрицательная стоимость риска для безубыточности отсутствует",
    "NEGATIVE_BREAK_EVEN": "Расчётная стоимость риска для безубыточности отрицательна",
    "NO_ADVERSE_CROSSING_WHEN_SHARE_INCREASES": "Увеличение доли не пересекает границу в сторону ухудшения",
    "NO_FEASIBLE_CROSSING": "Пересечение отсутствует в допустимом диапазоне долей",
    "PASS": "Пройдено", "FAIL": "Ошибка", "INFO": "Справочно",
}
REVERSE_LABELS = {
    "portfolio_credit_cost_multiplier": "Множитель стоимости кредитного риска портфеля",
    "critical_product_share_vs_mortgage": "Критическая доля при замещении ипотеки",
}
FACTOR_LABELS = {
    "pricing_plus_100bp": "Ставка по кредиту +1 п.п.",
    "funding_plus_100bp": "Стоимость фондирования +1 п.п.",
    "credit_cost_plus_100bp": "Стоимость кредитного риска +1 п.п.",
    "share_plus_1pp_vs_mortgage": "Доля продукта +1 п.п. за счёт ипотеки",
}
TERMINOLOGY_NOTE = """| Термин | Расшифровка и смысл |
|---|---|
| CRAS | Credit-risk-adjusted spread — спред с учётом кредитного риска: ставка по кредиту минус фондирование и стоимость кредитного риска, в годовом выражении. |
| RAFR | Risk-adjusted financial result — финансовый результат с учётом кредитного риска; в модели рассчитывается за шесть месяцев. |
| ECL | Expected credit losses — ожидаемые кредитные убытки; резерв отражает запас на дату, переоценка — компонент расчёта стоимости риска за период. |
| CoR | Cost of risk — стоимость риска; официальный показатель группы отличается по охвату и определению от продуктового исследовательского показателя. |
| NIM | Net interest margin — чистая процентная маржа. |
| FTP | Funds transfer pricing — внутреннее трансфертное ценообразование на фондирование. |
| RAROC | Risk-adjusted return on capital — доходность капитала с учётом риска. |
| RWA | Risk-weighted assets — активы, взвешенные по риску. |
| Opex | Operating expenses — операционные расходы. |
| LGD | Loss given default — доля потерь при дефолте. |
| NA | Not available — порог не представлен; причину указывает статус расчёта. |
| H1 / H2 / 6M | First half / second half / six months — первое полугодие / второе полугодие / шесть месяцев. |
| Exposure | Кредитная экспозиция: объём требований по продукту, используемый в модели. |
| Pricing / funding | Ставка по кредиту / стоимость фондирования. |
| Market proxy | Рыночный показатель-заменитель: внешняя ставка вместо ненаблюдаемой внутренней ставки банка. |
| Baseline / Base Mix | Базовый вариант / исходный продуктовый состав. |
| Base / Moderate / Severe | Базовый / умеренный / тяжёлый финансовый сценарий. |
| Portfolio-mix sensitivity (PortfolioMix) | Чувствительность к продуктовому составу при неизменной общей экспозиции. |
| Severe + Portfolio Mix (SevereMix) | Тяжёлые финансовые предпосылки в сочетании с изменением продуктового состава. |
| Reverse stress / adverse crossing | Обратное стресс-тестирование / пересечение критической границы в сторону ухудшения результата. |
| Break-even | Безубыточность: значение параметра, при котором соответствующий результат равен нулю. |
| QA / ML | Quality assurance / machine learning — проверка качества / машинное обучение. |
| п.п. / bp | Процентный пункт / basis point (базисный пункт); 100 базисных пунктов равны одному процентному пункту. |"""


def scenario_label(scenario: str) -> str:
    name = SCENARIO_ALIASES.get(scenario, scenario)
    return SCENARIO_LABELS.get(name, name)


def russian_text(text: str) -> str:
    """Translate presentation text while preserving machine-readable outputs."""
    translations = {
        "Synthetic four-product retail credit portfolio calibrated on public VTB and Bank of Russia data": "Синтетический четырёхпродуктовый розничный кредитный портфель, откалиброванный на публичных данных ВТБ и Банка России",
        "Synthetic four-product retail credit portfolio calibrated on public data": "Синтетический четырёхпродуктовый розничный кредитный портфель, откалиброванный на публичных данных",
        "At what share of higher-risk products does additional modeled income cease to compensate for higher credit losses and reduced stress resilience?": "При какой доле более рискованных продуктов дополнительный модельный доход перестаёт компенсировать кредитные потери и снижение устойчивости к стрессу?",
        "When does additional modeled income cease to compensate for higher credit losses?": "Когда дополнительный модельный доход перестаёт компенсировать рост кредитных потерь?",
        "adequate for transparent scenario, sensitivity and reverse stress; inadequate for robust econometric estimation": "достаточно для прозрачного сценарного анализа, анализа чувствительности и обратного стресс-тестирования; недостаточно для устойчивого эконометрического оценивания",
        "credit-cost calibration sample is short; scenario coefficients remain working assumptions": "выборка для калибровки стоимости риска короткая; сценарные коэффициенты остаются рабочими предпосылками",
        "excluded from primary CC sigma calibration unless later source verification upgrades the rows": "исключены из основной калибровки стандартного отклонения стоимости риска до возможной проверки первоисточника",
        "30.06.2024 exposure reconstruction; 31.12.2024 CC depends on that prior exposure": "реконструкция экспозиции на 30.06.2024; стоимость риска на 31.12.2024 зависит от этой предыдущей экспозиции",
        "Pochta Bank integration affects changes into the baseline date": "интеграция Почта Банка влияет на изменения к базовой дате",
        "30.06.2026 remains a usable snapshot; changes into it are not interpreted as purely organic dynamics": "срез на 30.06.2026 пригоден для базового портфеля; изменения к этой дате не трактуются как исключительно органическая динамика",
        "Suitable for scenario/sensitivity/reverse stress; not sufficient for robust regression/ML/tail inference": "подходит для сценарного анализа, чувствительности и обратного стресс-тестирования; недостаточно для устойчивой регрессии, машинного обучения или оценки хвостов распределения",
        "Changes automatically with the current dataset; it is not a 7 tn or fixed 6,573 bn constraint.": "Сумма меняется вместе с текущими данными; ограничение в 7 трлн или фиксированные 6,573 млрд руб. не задаётся.",
        "CRAS and six-month RAFR follow the configured annual-rate and 0.5-year identities.": "CRAS и шестимесячный RAFR соответствуют формулам с годовыми ставками и горизонтом 0.5 года.",
        "Stable arithmetic conditional on the input exposures, pricing, funding and direct credit-cost components.": "Арифметика устойчива при заданных экспозициях, кредитных ставках, фондировании и прямых компонентах стоимости риска.",
        "The sign and magnitude are not robust to the mortgage pricing proxy; the sensitivity endpoint is not a VTB yield estimate.": "Знак и величина результата чувствительны к ипотечной ставке-заменителю; крайняя точка анализа чувствительности не является оценкой доходности ВТБ.",
        "Depends on provisional sigma multipliers and a primary credit-cost calibration sample of only three observations per product.": "Зависит от рабочих множителей стандартного отклонения и основной выборки стоимости риска из трёх наблюдений на продукт.",
        "Depends on explicit portfolio-mix percentage-point shifts; only the fixed-total identity is mechanically stable.": "Зависит от заданных сдвигов продуктовых долей в процентных пунктах; механически устойчиво только сохранение общей экспозиции.",
        "Replacing Mortgage with Consumer, Auto or Cards improves RAFR in every configured scenario.": "Замещение ипотеки потребительскими кредитами, автокредитами или кредитными картами улучшает RAFR во всех настроенных сценариях.",
        "Product-share direction is not uniform across configured scenarios.": "Направление эффекта изменения доли различается между настроенными сценариями.",
        "This direction holds under current pricing/funding/credit-cost proxies and can change under alternative product-pricing assumptions.": "Такое направление сохраняется при текущих кредитных ставках, фондировании и стоимости риска; альтернативные предпосылки о ставках могут его изменить.",
        "Threshold existence and interpretation change if the critical boundary or input proxies change; infeasible thresholds are reported as NA.": "Наличие и интерпретация порога зависят от критической границы и исходных показателей-заменителей; недопустимые пороги представлены как NA.",
        "Baseline total is RUB ": "Базовая сумма равна ",
        " bn and is recomputed from four exposures.": " млрд руб. и рассчитана из четырёх экспозиций.",
        "Base RAFR is RUB ": "Базовый RAFR равен ",
        " bn at the dataset mortgage proxy; it is RUB ": " млрд руб. при ипотечной ставке из набора данных; результат равен ",
        " bn at the ": " млрд руб. при ипотечной ставке ",
        " mortgage sensitivity endpoint.": " на крайней точке анализа чувствительности.",
        "Moderate RAFR is RUB ": "RAFR в умеренном сценарии равен ",
        " bn and Severe RAFR is RUB ": " млрд руб., а в тяжёлом — ",
        "Portfolio-mix sensitivity RAFR is RUB ": "RAFR при изменении состава равен ",
        " bn and Severe + Portfolio Mix RAFR is RUB ": " млрд руб., а при сочетании тяжёлого сценария и изменения состава — ",
        "Reverse-stress statuses are evaluated against RAFR_6M = RUB ": "Статусы обратного стресс-тестирования оцениваются относительно RAFR_6M = ",
        "mechanically_stable": "Механически устойчиво", "proxy_sensitive": "Чувствительно к показателю-заменителю",
        "working_assumption_dependent": "Зависит от рабочих предпосылок", "conditional_direction": "Условное направление эффекта", "boundary_sensitive": "Зависит от критической границы",
        "duplicate report_date/product": "Дубликаты пары отчётная дата / продукт",
        "complete numeric inputs": "Полнота числовых входов", "finite numeric inputs": "Конечность числовых входов",
        "baseline products present": "Наличие всех базовых продуктов", "positive exposure": "Положительная экспозиция",
        "ecl_rate formula": "Формула доли резерва ECL", "annualized credit_cost formula": "Формула годовой стоимости кредитного риска",
        "baseline direct credit_cost components": "Наличие прямых компонентов базовой стоимости риска",
        "baseline four-product total": "Базовая сумма четырёх продуктов",
        "complete four-product history panel": "Полнота истории четырёх продуктов", "configured history bounds present": "Наличие настроенных границ истории",
        "history reporting dates": "Отчётные даты истории", "history design suitability": "Пригодность истории для выбранного анализа",
        "overall": "Общая оценка", "numeric completeness": "Полнота числовых данных", "known auxiliary history": "Вспомогательная история",
        "2026H1 structural break": "Изменение периметра в первом полугодии 2026 года",
        "complete for the configured window": "данные полны в настроенном периоде", "missing inputs require reconciliation": "пропущенные значения требуют сверки",
        " reporting dates / ": " отчётных дат / ", " product rows": " продуктовых строк",
        "primary_cc_n=": "основных наблюдений стоимости риска=", "primary_cc_range=": "диапазон основной стоимости риска=",
        "pricing_range=": "диапазон кредитных ставок=", "funding_range=": "диапазон фондирования=",
        "missing_recomputed_rows=": "строк без прямого расчёта=", "missing_cells=": "пропущенных ячеек=",
        "max_abs_diff=": "максимальное абсолютное расхождение=", "all_finite=": "все значения конечны=", "bad_rows=": "некорректных строк=",
        "n_dates=": "число дат=", "RUB_bn=": "млрд руб.=", "missing=": "отсутствуют=", "rows=": "строк=", "dates=": "дат=", "start=": "начало=", "end=": "конец=", "n=": "наблюдений=",
        "no comparable rows": "нет сопоставимых строк", "True": "да", "False": "нет",
        **PRODUCT_LABELS, " bn": " млрд руб.",
    }
    for original, translation in sorted(translations.items(), key=lambda pair: len(pair[0]), reverse=True):
        text = text.replace(original, translation)
    return text.replace("млрд руб..", "млрд руб.").replace("фиксированные 6,573", "фиксированные 6 573")

ALIASES = {
    "Отчетная дата": "report_date", "Report date": "report_date", "report_date": "report_date",
    "Продукт": "product", "Product": "product", "product": "product",
    "Экспозиция, млрд руб.": "exposure", "Exposure, RUB bn": "exposure", "exposure": "exposure",
    "Резерв ECL, млрд руб.": "ecl_reserve", "ECL reserve, RUB bn": "ecl_reserve", "ecl_reserve": "ecl_reserve",
    "Переоценка ECL, млрд руб.": "ecl_remeasurement", "ECL remeasurement, RUB bn": "ecl_remeasurement", "ecl_remeasurement": "ecl_remeasurement",
    "Уровень ECL, %": "ecl_rate", "ECL rate, %": "ecl_rate", "ecl_rate": "ecl_rate",
    "Стоимость кредитного риска, %": "credit_cost", "Credit cost, %": "credit_cost", "credit_cost": "credit_cost",
    "Ставка по продукту, %": "product_rate", "Product rate, %": "product_rate", "product_rate": "product_rate",
    "Стоимость фондирования, %": "funding_rate", "Funding rate, %": "funding_rate", "funding_rate": "funding_rate",
}
REQUIRED = ["report_date", "product", "exposure", "ecl_reserve", "ecl_remeasurement", "ecl_rate", "credit_cost", "product_rate", "funding_rate"]


@dataclass(frozen=True)
class ModelConfig:
    input_file: str
    data_sheet: str
    baseline_date: pd.Timestamp
    history_start_date: pd.Timestamp
    history_end_date: pd.Timestamp
    horizon_years: float
    products: List[str]
    critical_result_bn: float
    scenario_calibration: Mapping[str, object]
    credit_cost_calibration_exclude_dates: List[pd.Timestamp]
    structural_shift_pp: Mapping[str, object]  # Legacy constructor name, retained for compatibility.
    mortgage_pricing_sensitivity: Mapping[str, object]
    reverse_stress: Mapping[str, float]
    qa_tolerance: float
    output_dir: str
    research_title: str = "Retail portfolio risk-return stress testing"
    portfolio_nature: str = "Synthetic four-product retail credit portfolio calibrated on public data"
    primary_research_question: str = "When does additional modeled income cease to compensate for higher credit losses?"

    @property
    def portfolio_mix_shift_pp(self) -> Mapping[str, object]:
        return self.structural_shift_pp


def load_config(path: Path) -> ModelConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "portfolio_mix_shift_pp" in raw:
        mix_shift = raw["portfolio_mix_shift_pp"]
        if "structural_shift_pp" in raw and raw["structural_shift_pp"] != mix_shift:
            raise ValueError("Conflicting portfolio-mix shift settings")
    else:
        mix_shift = raw["structural_shift_pp"]  # Legacy JSON alias.
    return ModelConfig(
        input_file=raw["input_file"],
        data_sheet=raw.get("data_sheet", "DATA_MASTER"),
        baseline_date=pd.Timestamp(raw["baseline_date"]),
        history_start_date=pd.Timestamp(raw.get("history_start_date", "2023-12-31")),
        history_end_date=pd.Timestamp(raw.get("history_end_date", raw["baseline_date"])),
        horizon_years=float(raw.get("horizon_years", 0.5)),
        products=list(raw.get("products", PRODUCTS)),
        critical_result_bn=float(raw.get("critical_result_bn", 0.0)),
        scenario_calibration=raw["scenario_calibration"],
        credit_cost_calibration_exclude_dates=[pd.Timestamp(x) for x in raw.get("credit_cost_calibration_exclude_dates", [])],
        structural_shift_pp=mix_shift,
        mortgage_pricing_sensitivity=raw.get("mortgage_pricing_sensitivity", {}),
        reverse_stress=raw.get("reverse_stress", {}),
        qa_tolerance=float(raw.get("qa_tolerance", 1e-8)),
        output_dir=raw.get("output_dir", "outputs"),
        research_title=raw.get("research_title", "Retail portfolio risk-return stress testing"),
        portfolio_nature=raw.get("portfolio_nature", "Synthetic four-product retail credit portfolio calibrated on public data"),
        primary_research_question=raw.get("primary_research_question", "When does additional modeled income cease to compensate for higher credit losses?"),
    )


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    renamed = {c: ALIASES[str(c).strip()] for c in raw.columns if str(c).strip() in ALIASES}
    df = raw.rename(columns=renamed).copy()
    for c in list(df.columns):
        if str(c).strip().lower() in {"index", "unnamed: 0"}:
            df = df.drop(columns=[c])
    if "product" in df.columns:
        df["product"] = df["product"].astype(str).str.strip()
        df = df[df["product"].isin(PRODUCTS)].copy()
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce", format="mixed", dayfirst=True)
    for c in [x for x in REQUIRED if x not in {"report_date", "product"}]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["report_date", "product"])
    return df[REQUIRED].sort_values(["report_date", "product"]).reset_index(drop=True)


def load_dataset(path: Path, sheet_name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        raw = pd.read_excel(path, sheet_name=sheet_name)
    elif path.suffix.lower() == ".csv":
        raw = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported input format: {path.suffix}")
    return normalize_columns(raw)


def add_recomputed_credit_cost(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values(["product", "report_date"])
    out["previous_exposure"] = out.groupby("product")["exposure"].shift(1)
    out["average_exposure"] = (out["previous_exposure"] + out["exposure"]) / 2.0
    out["credit_cost_recomputed"] = 2.0 * out["ecl_remeasurement"] / out["average_exposure"]
    return out.sort_values(["report_date", "product"]).reset_index(drop=True)


def validate_data(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    x = add_recomputed_credit_cost(df)
    rows: List[dict] = []
    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    dup = int(x.duplicated(["report_date", "product"]).sum())
    add("duplicate report_date/product", "PASS" if dup == 0 else "FAIL", str(dup))
    numeric_columns = [c for c in REQUIRED if c not in {"report_date", "product"}]
    missing_numeric = int(x[numeric_columns].isna().sum().sum())
    add("complete numeric inputs", "PASS" if missing_numeric == 0 else "FAIL", f"missing_cells={missing_numeric}")
    finite_numeric = bool(np.isfinite(x[numeric_columns].to_numpy(dtype=float)).all())
    add("finite numeric inputs", "PASS" if finite_numeric else "FAIL", f"all_finite={finite_numeric}")
    base = x[x.report_date == cfg.baseline_date]
    missing = sorted(set(cfg.products) - set(base["product"]))
    add("baseline products present", "PASS" if not missing else "FAIL", f"missing={missing}")
    add("positive exposure", "PASS" if (x.exposure > 0).all() else "FAIL", f"bad_rows={int((x.exposure <= 0).sum())}")

    calc_ecl = x.ecl_reserve / x.exposure
    diff_ecl = float((calc_ecl - x.ecl_rate).abs().max())
    add("ecl_rate formula", "PASS" if diff_ecl <= max(cfg.qa_tolerance, 1e-10) else "FAIL", f"max_abs_diff={diff_ecl:.3e}")

    mask = x.credit_cost_recomputed.notna() & x.credit_cost.notna()
    diff_cc = float((x.loc[mask, "credit_cost_recomputed"] - x.loc[mask, "credit_cost"]).abs().max()) if mask.any() else math.nan
    add("annualized credit_cost formula", "PASS" if mask.any() and diff_cc <= max(cfg.qa_tolerance, 1e-9) else "FAIL", f"max_abs_diff={diff_cc:.3e}" if mask.any() else "no comparable rows")

    base_cc_missing = base["credit_cost_recomputed"].isna().sum()
    add("baseline direct credit_cost components", "PASS" if base_cc_missing == 0 else "FAIL", f"missing_recomputed_rows={int(base_cc_missing)}")
    add("baseline four-product total", "INFO", f"RUB_bn={base.exposure.sum():.1f}")

    history = x[(x.report_date >= cfg.history_start_date) & (x.report_date <= cfg.history_end_date)]
    panel_ok = all(set(g["product"]) == set(cfg.products) and len(g) == len(cfg.products) for _, g in history.groupby("report_date"))
    add("complete four-product history panel", "PASS" if panel_ok else "FAIL", f"rows={len(history)}, dates={history.report_date.nunique()}")
    bounds_ok = bool(
        not history.empty
        and history.report_date.min() == cfg.history_start_date
        and history.report_date.max() == cfg.history_end_date
    )
    add(
        "configured history bounds present",
        "PASS" if bounds_ok else "FAIL",
        f"start={history.report_date.min().date() if not history.empty else 'NA'}, end={history.report_date.max().date() if not history.empty else 'NA'}",
    )
    add("history reporting dates", "INFO", f"n_dates={history.report_date.nunique()}, start={history.report_date.min().date()}, end={history.report_date.max().date()}")
    add("history design suitability", "INFO", "Suitable for scenario/sensitivity/reverse stress; not sufficient for robust regression/ML/tail inference")

    report = pd.DataFrame(rows)
    fail = report[report.status == "FAIL"]
    if not fail.empty:
        raise ValueError("QA failed:\n" + fail.to_string(index=False))
    return report


def data_adequacy_report(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    x = add_recomputed_credit_cost(df)
    h = x[(x.report_date >= cfg.history_start_date) & (x.report_date <= cfg.history_end_date)].copy()
    excluded = set(cfg.credit_cost_calibration_exclude_dates)
    h["cc_primary_calibration"] = h.credit_cost_recomputed.notna() & ~h.report_date.isin(excluded)
    rows = [{
        "item": "overall",
        "value": f"{h.report_date.nunique()} reporting dates / {len(h)} product rows",
        "assessment": "adequate for transparent scenario, sensitivity and reverse stress; inadequate for robust econometric estimation"
    }]
    numeric_columns = [c for c in REQUIRED if c not in {"report_date", "product"}]
    rows.append({
        "item": "numeric completeness",
        "value": f"missing_cells={int(h[numeric_columns].isna().sum().sum())}",
        "assessment": "complete for the configured window" if not h[numeric_columns].isna().any().any() else "missing inputs require reconciliation",
    })
    for p in cfg.products:
        g = h[h["product"] == p]
        primary_cc = g.loc[g.cc_primary_calibration, "credit_cost_recomputed"]
        rows.append({
            "item": p,
            "value": (
                f"n={len(g)}, primary_cc_n={int(g.cc_primary_calibration.sum())}, "
                f"primary_cc_range={primary_cc.min():.4%}..{primary_cc.max():.4%}, "
                f"pricing_range={g.product_rate.min():.2%}..{g.product_rate.max():.2%}, "
                f"funding_range={g.funding_rate.min():.2%}..{g.funding_rate.max():.2%}"
            ),
            "assessment": "credit-cost calibration sample is short; scenario coefficients remain working assumptions"
        })
    rows.append({
        "item": "known auxiliary history",
        "value": "30.06.2024 exposure reconstruction; 31.12.2024 CC depends on that prior exposure",
        "assessment": "excluded from primary CC sigma calibration unless later source verification upgrades the rows"
    })
    rows.append({
        "item": "2026H1 structural break",
        "value": "Pochta Bank integration affects changes into the baseline date",
        "assessment": "30.06.2026 remains a usable snapshot; changes into it are not interpreted as purely organic dynamics",
    })
    return pd.DataFrame(rows)


def baseline_table(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    x = add_recomputed_credit_cost(df)
    b = x[(x.report_date == cfg.baseline_date) & x["product"].isin(cfg.products)].copy()
    if set(b["product"]) != set(cfg.products):
        raise ValueError("Baseline does not contain the configured products")
    if b.credit_cost_recomputed.isna().any():
        raise ValueError("Baseline direct credit cost cannot be recomputed")
    b["credit_cost"] = b["credit_cost_recomputed"]
    total = float(b.exposure.sum())
    b["weight"] = b.exposure / total
    return b.sort_values("product").reset_index(drop=True)


def calibration_sigmas(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    x = add_recomputed_credit_cost(df)
    h = x[(x.report_date >= cfg.history_start_date) & (x.report_date <= cfg.history_end_date)].copy()
    excluded = set(cfg.credit_cost_calibration_exclude_dates)
    rows = []
    for p in cfg.products:
        g = h[h["product"] == p].sort_values("report_date")
        cc = g.loc[g.credit_cost_recomputed.notna() & ~g.report_date.isin(excluded), "credit_cost_recomputed"]
        pr = g["product_rate"].dropna()
        fr = g["funding_rate"].dropna()
        if len(cc) < 2 or len(pr) < 2 or len(fr) < 2:
            raise ValueError(f"Insufficient calibration observations for {p}: cc={len(cc)}, pricing={len(pr)}, funding={len(fr)}")
        rows.append({
            "product": p,
            "credit_cost_sigma": float(cc.std(ddof=1)),
            "product_rate_sigma": float(pr.std(ddof=1)),
            "funding_rate_sigma": float(fr.std(ddof=1)),
            "credit_cost_n": int(len(cc)),
            "product_rate_n": int(len(pr)),
            "funding_rate_n": int(len(fr)),
        })
    return pd.DataFrame(rows)


def apply_financial_stress(base: pd.DataFrame, sigmas: pd.DataFrame, calibration: Mapping[str, float]) -> pd.DataFrame:
    out = base.merge(sigmas[["product", "credit_cost_sigma", "product_rate_sigma", "funding_rate_sigma"]], on="product", how="left")
    out["credit_cost"] = np.maximum(0.0, out.credit_cost + float(calibration["credit_cost_sigma"]) * out.credit_cost_sigma)
    out["product_rate"] = np.maximum(0.0, out.product_rate - float(calibration["pricing_sigma"]) * out.product_rate_sigma)
    out["funding_rate"] = np.maximum(0.0, out.funding_rate + float(calibration["funding_sigma"]) * out.funding_rate_sigma)
    return out.drop(columns=["credit_cost_sigma", "product_rate_sigma", "funding_rate_sigma"])


def apply_portfolio_mix_shift(base: pd.DataFrame, shift_pp: Mapping[str, float]) -> pd.DataFrame:
    out = base.copy()
    total = float(out.exposure.sum())
    weights = out.set_index("product")["weight"].to_dict()
    increase = 0.0
    for p in RISKIER_PRODUCTS:
        d = float(shift_pp.get(p, 0.0)) / 100.0
        weights[p] += d
        increase += d
    weights["Mortgage"] -= increase
    raw = np.array([weights[p] for p in cfg_products(out)], dtype=float)
    if np.any(raw < -1e-12) or np.any(raw > 1 + 1e-12):
        raise ValueError("Portfolio-mix shift creates infeasible weights")
    out["weight"] = out["product"].map(weights)
    out["exposure"] = out.weight * total
    if not np.isclose(out.exposure.sum(), total):
        raise ValueError("Portfolio-mix shift changed total exposure")
    return out


# Legacy callable alias; active calculations use the portfolio-mix name.
apply_structural_shift = apply_portfolio_mix_shift


def cfg_products(df: pd.DataFrame) -> List[str]:
    present = set(df["product"])
    return [p for p in PRODUCTS if p in present]


def calculate_product_results(params: pd.DataFrame, horizon_years: float, scenario: str) -> pd.DataFrame:
    out = params.copy()
    out["credit_risk_adjusted_spread"] = out.product_rate - out.funding_rate - out.credit_cost
    out["pricing_income_bn"] = out.exposure * out.product_rate * horizon_years
    out["funding_cost_bn"] = out.exposure * out.funding_rate * horizon_years
    out["credit_loss_bn"] = out.exposure * out.credit_cost * horizon_years
    out["risk_adjusted_financial_result_bn"] = out.exposure * out.credit_risk_adjusted_spread * horizon_years
    scenario = SCENARIO_ALIASES.get(scenario, scenario)
    out["scenario"] = scenario
    out["scenario_type"] = SCENARIO_TYPES.get(scenario, "baseline")
    return out


def build_scenarios(df: pd.DataFrame, cfg: ModelConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base = baseline_table(df, cfg)
    sig = calibration_sigmas(df, cfg)
    results = [calculate_product_results(base, cfg.horizon_years, "Base")]

    moderate = apply_financial_stress(base, sig, cfg.scenario_calibration["moderate"])
    results.append(calculate_product_results(moderate, cfg.horizon_years, "Moderate"))

    severe = apply_financial_stress(base, sig, cfg.scenario_calibration["severe"])
    results.append(calculate_product_results(severe, cfg.horizon_years, "Severe"))

    portfolio_mix = apply_portfolio_mix_shift(base, cfg.portfolio_mix_shift_pp["moderate"])
    results.append(calculate_product_results(portfolio_mix, cfg.horizon_years, "PortfolioMix"))

    severe_mix = apply_portfolio_mix_shift(severe, cfg.portfolio_mix_shift_pp["severe"])
    results.append(calculate_product_results(severe_mix, cfg.horizon_years, "SevereMix"))
    return pd.concat(results, ignore_index=True), sig


def scenario_summary(product_results: pd.DataFrame, horizon_years: float) -> pd.DataFrame:
    product_results = product_results.assign(scenario=product_results.scenario.replace(SCENARIO_ALIASES))
    g = product_results.groupby("scenario", as_index=False).agg(
        exposure_bn=("exposure", "sum"),
        pricing_income_bn=("pricing_income_bn", "sum"),
        funding_cost_bn=("funding_cost_bn", "sum"),
        credit_loss_bn=("credit_loss_bn", "sum"),
        risk_adjusted_financial_result_bn=("risk_adjusted_financial_result_bn", "sum"),
    )
    g["credit_risk_adjusted_spread"] = g.risk_adjusted_financial_result_bn / g.exposure_bn / horizon_years
    g["scenario"] = pd.Categorical(g["scenario"], categories=SCENARIO_ORDER, ordered=True)
    g = g.sort_values("scenario").reset_index(drop=True)
    g["scenario"] = g["scenario"].astype(str)
    g["scenario_type"] = g["scenario"].map(SCENARIO_TYPES)
    return g


def portfolio_mix_sensitivity(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    product_results = product_results.assign(scenario=product_results.scenario.replace(SCENARIO_ALIASES))
    rows = []
    step = float(cfg.reverse_stress.get("share_step", 0.001))
    for scenario in SCENARIO_ORDER:
        g0 = product_results[product_results["scenario"] == scenario]
        if g0.empty:
            continue
        g = g0.set_index("product")
        total = float(g.exposure.sum())
        base_w = (g.exposure / total).to_dict()
        for target in RISKIER_PRODUCTS:
            other = [p for p in RISKIER_PRODUCTS if p != target]
            fixed_sum = sum(base_w[p] for p in other)
            max_target = 1.0 - fixed_sum
            for wt in np.arange(0.0, max_target + step / 2.0, step):
                wm = 1.0 - fixed_sum - wt
                weights = {p: base_w[p] for p in other}
                weights[target] = float(wt)
                weights["Mortgage"] = float(wm)
                result = 0.0
                for p in PRODUCTS:
                    spread = g.loc[p, "product_rate"] - g.loc[p, "funding_rate"] - g.loc[p, "credit_cost"]
                    result += total * weights[p] * spread * cfg.horizon_years
                rows.append({"scenario": scenario, "target_product": target, "target_share": float(wt), "mortgage_share": float(wm), "risk_adjusted_financial_result_bn": result})
    return pd.DataFrame(rows)


structural_sensitivity = portfolio_mix_sensitivity  # Legacy callable alias.


def factor_sensitivity(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    product_results = product_results.assign(scenario=product_results.scenario.replace(SCENARIO_ALIASES))
    rows = []
    h = cfg.horizon_years
    for scenario in SCENARIO_ORDER:
        g0 = product_results[product_results["scenario"] == scenario]
        if g0.empty:
            continue
        g = g0.set_index("product")
        total = float(g.exposure.sum())
        base_result = float(g.risk_adjusted_financial_result_bn.sum())
        for p in PRODUCTS:
            exp = float(g.loc[p, "exposure"])
            rows.extend([
                {"scenario": scenario, "product": p, "factor": "pricing_plus_100bp", "delta_result_bn": exp * 0.01 * h, "base_result_bn": base_result},
                {"scenario": scenario, "product": p, "factor": "funding_plus_100bp", "delta_result_bn": -exp * 0.01 * h, "base_result_bn": base_result},
                {"scenario": scenario, "product": p, "factor": "credit_cost_plus_100bp", "delta_result_bn": -exp * 0.01 * h, "base_result_bn": base_result},
            ])
        for p in RISKIER_PRODUCTS:
            delta = total * 0.01 * h * (g.loc[p, "credit_risk_adjusted_spread"] - g.loc["Mortgage", "credit_risk_adjusted_spread"])
            rows.append({"scenario": scenario, "product": p, "factor": "share_plus_1pp_vs_mortgage", "delta_result_bn": delta, "base_result_bn": base_result})
    return pd.DataFrame(rows)


def reverse_stress(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    product_results = product_results.assign(scenario=product_results.scenario.replace(SCENARIO_ALIASES))
    rows = []
    boundary = cfg.critical_result_bn
    h = cfg.horizon_years
    for scenario in SCENARIO_ORDER:
        g0 = product_results[product_results["scenario"] == scenario]
        if g0.empty:
            continue
        g = g0.set_index("product")
        total = float(g.exposure.sum())
        base_result = float(g.risk_adjusted_financial_result_bn.sum())
        pre_credit = float(((g.product_rate - g.funding_rate) * g.exposure * h).sum())
        base_credit_loss = float((g.credit_cost * g.exposure * h).sum())
        solved_mult = (pre_credit - boundary) / base_credit_loss if base_credit_loss > 0 else math.nan
        if math.isnan(solved_mult):
            mult = math.nan
            status = "NO_CREDIT_LOSS_BASE"
        elif solved_mult < 0:
            mult = math.nan
            status = "NO_NONNEGATIVE_SOLUTION"
        else:
            mult = solved_mult
        if not math.isnan(mult) and base_result <= boundary and mult < 1.0:
            status = "THRESHOLD_BELOW_CURRENT_1X"
        elif not math.isnan(mult):
            status = "FEASIBLE"
        rows.append({"scenario": scenario, "reverse_type": "portfolio_credit_cost_multiplier", "target_product": "ALL", "threshold": mult, "threshold_unit": "x", "boundary_result_bn": boundary, "base_result_bn": base_result, "status": status})

        mortgage_spread = float(g.loc["Mortgage", "credit_risk_adjusted_spread"])
        weights = (g.exposure / total).to_dict()
        for p in PRODUCTS:
            solved_break_even_cc = float(g.loc[p, "product_rate"] - g.loc[p, "funding_rate"])
            if solved_break_even_cc < 0:
                own_break_even_cc, own_status = math.nan, "NO_NONNEGATIVE_BREAK_EVEN"
            else:
                own_break_even_cc, own_status = solved_break_even_cc, "FEASIBLE"
            rows.append({"scenario": scenario, "reverse_type": "product_break_even_credit_cost", "target_product": p, "threshold": own_break_even_cc, "threshold_unit": "annual_rate", "boundary_result_bn": boundary, "base_result_bn": base_result, "status": own_status})
        for p in RISKIER_PRODUCTS:
            marginal_break_even_cc = float(g.loc[p, "product_rate"] - g.loc[p, "funding_rate"] - mortgage_spread)
            rows.append({"scenario": scenario, "reverse_type": "marginal_break_even_credit_cost_vs_mortgage", "target_product": p, "threshold": marginal_break_even_cc, "threshold_unit": "annual_rate", "boundary_result_bn": boundary, "base_result_bn": base_result, "status": "FEASIBLE" if marginal_break_even_cc >= 0 else "NEGATIVE_BREAK_EVEN"})

            derivative = total * h * (float(g.loc[p, "credit_risk_adjusted_spread"]) - mortgage_spread)
            base_share = weights[p]
            max_share = 1.0 - sum(weights[q] for q in RISKIER_PRODUCTS if q != p)
            if base_result <= boundary:
                threshold, status2 = math.nan, "ALREADY_AT_OR_BELOW_BOUNDARY"
            elif derivative >= 0:
                threshold, status2 = math.nan, "NO_ADVERSE_CROSSING_WHEN_SHARE_INCREASES"
            else:
                threshold = base_share + (boundary - base_result) / derivative
                if threshold < base_share - 1e-12 or threshold > max_share + 1e-12:
                    threshold, status2 = math.nan, "NO_FEASIBLE_CROSSING"
                else:
                    status2 = "FEASIBLE"
            rows.append({"scenario": scenario, "reverse_type": "critical_product_share_vs_mortgage", "target_product": p, "threshold": threshold, "threshold_unit": "share", "boundary_result_bn": boundary, "base_result_bn": base_result, "status": status2, "marginal_result_change_bn_per_1pp_share": derivative * 0.01})
    return pd.DataFrame(rows)


def robustness_assessment(
    product_results: pd.DataFrame,
    summary: pd.DataFrame,
    mortgage: pd.DataFrame,
    cfg: ModelConfig,
) -> pd.DataFrame:
    product_results = product_results.assign(scenario=product_results.scenario.replace(SCENARIO_ALIASES))
    summary = summary.assign(scenario=summary.scenario.replace(SCENARIO_ALIASES))
    base = summary.set_index("scenario").loc["Base"]
    alt_row = mortgage.loc[mortgage["mortgage_pricing_rate"].idxmax()]
    alt_rate = float(alt_row["mortgage_pricing_rate"])
    alt_result = float(alt_row["risk_adjusted_financial_result_bn"])
    scenario_map = summary.set_index("scenario")["risk_adjusted_financial_result_bn"].to_dict()
    spread = product_results.pivot(index="scenario", columns="product", values="credit_risk_adjusted_spread")
    share_direction_positive = bool((spread[RISKIER_PRODUCTS].sub(spread["Mortgage"], axis=0) > 0).all().all())
    return pd.DataFrame([
        {
            "classification": "mechanically_stable",
            "finding": f"Baseline total is RUB {base.exposure_bn:,.1f} bn and is recomputed from four exposures.",
            "dependency": "Changes automatically with the current dataset; it is not a 7 tn or fixed 6,573 bn constraint.",
        },
        {
            "classification": "mechanically_stable",
            "finding": "CRAS and six-month RAFR follow the configured annual-rate and 0.5-year identities.",
            "dependency": "Stable arithmetic conditional on the input exposures, pricing, funding and direct credit-cost components.",
        },
        {
            "classification": "proxy_sensitive",
            "finding": f"Base RAFR is RUB {base.risk_adjusted_financial_result_bn:,.1f} bn at the dataset mortgage proxy; it is RUB {alt_result:,.1f} bn at the {alt_rate:.1%} mortgage sensitivity endpoint.",
            "dependency": "The sign and magnitude are not robust to the mortgage pricing proxy; the sensitivity endpoint is not a VTB yield estimate.",
        },
        {
            "classification": "working_assumption_dependent",
            "finding": f"Moderate RAFR is RUB {scenario_map['Moderate']:,.1f} bn and Severe RAFR is RUB {scenario_map['Severe']:,.1f} bn.",
            "dependency": "Depends on provisional sigma multipliers and a primary credit-cost calibration sample of only three observations per product.",
        },
        {
            "classification": "working_assumption_dependent",
            "finding": f"Portfolio-mix sensitivity RAFR is RUB {scenario_map['PortfolioMix']:,.1f} bn and Severe + Portfolio Mix RAFR is RUB {scenario_map['SevereMix']:,.1f} bn.",
            "dependency": "Depends on explicit portfolio-mix percentage-point shifts; only the fixed-total identity is mechanically stable.",
        },
        {
            "classification": "conditional_direction",
            "finding": "Replacing Mortgage with Consumer, Auto or Cards improves RAFR in every configured scenario." if share_direction_positive else "Product-share direction is not uniform across configured scenarios.",
            "dependency": "This direction holds under current pricing/funding/credit-cost proxies and can change under alternative product-pricing assumptions.",
        },
        {
            "classification": "boundary_sensitive",
            "finding": f"Reverse-stress statuses are evaluated against RAFR_6M = RUB {cfg.critical_result_bn:,.1f} bn.",
            "dependency": "Threshold existence and interpretation change if the critical boundary or input proxies change; infeasible thresholds are reported as NA.",
        },
    ])


def mortgage_pricing_sensitivity(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = baseline_table(df, cfg)
    base_rate = float(base.loc[base["product"] == "Mortgage", "product_rate"].iloc[0])
    sens = cfg.mortgage_pricing_sensitivity
    if not sens.get("enabled", False):
        return pd.DataFrame([{"mortgage_pricing_rate": base_rate, "risk_adjusted_financial_result_bn": float(calculate_product_results(base, cfg.horizon_years, "Base").risk_adjusted_financial_result_bn.sum())}])
    alt = float(sens.get("alternative_market_rate", base_rate))
    lo, hi = sorted([base_rate, alt])
    grid = np.linspace(lo, hi, 101) if hi > lo else np.array([lo])
    rows = []
    for rate in grid:
        x = base.copy()
        x.loc[x["product"] == "Mortgage", "product_rate"] = rate
        res = calculate_product_results(x, cfg.horizon_years, "BaseSensitivity")
        rows.append({"mortgage_pricing_rate": float(rate), "risk_adjusted_financial_result_bn": float(res.risk_adjusted_financial_result_bn.sum())})
    return pd.DataFrame(rows)


def make_figures(summary: pd.DataFrame, portfolio_mix: pd.DataFrame, mortgage: pd.DataFrame, outdir: Path) -> None:
    figdir = outdir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    order = SCENARIO_ORDER
    s = summary.set_index("scenario").reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar([scenario_label(name) for name in s.index], s.risk_adjusted_financial_result_bn)
    ax.tick_params(axis="x", labelrotation=15)
    ax.axhline(0, linewidth=1)
    ax.set_ylabel("Финансовый результат, млрд руб. за 6 месяцев")
    ax.set_title("Финансовый результат: сценарии и изменение состава портфеля")
    fig.tight_layout(); fig.savefig(figdir / "scenario_results.png", dpi=160); plt.close(fig)

    sev = portfolio_mix[portfolio_mix.scenario == "Severe"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for p, g in sev.groupby("target_product"):
        ax.plot(g.target_share * 100, g.risk_adjusted_financial_result_bn, label=PRODUCT_LABELS[p])
    ax.axhline(0, linewidth=1); ax.set_xlabel("Доля выбранного продукта, %"); ax.set_ylabel("Финансовый результат, млрд руб. за 6 месяцев"); ax.set_title("Чувствительность к продуктовому составу: тяжёлый сценарий"); ax.legend()
    fig.tight_layout(); fig.savefig(figdir / "portfolio_mix_sensitivity_severe.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(mortgage.mortgage_pricing_rate * 100, mortgage.risk_adjusted_financial_result_bn)
    ax.axhline(0, linewidth=1); ax.set_xlabel("Ипотечная ставка-заменитель, %"); ax.set_ylabel("Финансовый результат, млрд руб. за 6 месяцев"); ax.set_title("Чувствительность к ипотечной ставке: базовый сценарий")
    fig.tight_layout(); fig.savefig(figdir / "mortgage_pricing_sensitivity.png", dpi=160); plt.close(fig)


def build_report(df: pd.DataFrame, cfg: ModelConfig, qa: pd.DataFrame, adequacy: pd.DataFrame, sigmas: pd.DataFrame, product_results: pd.DataFrame, summary: pd.DataFrame, reverse: pd.DataFrame, factor: pd.DataFrame, robustness: pd.DataFrame) -> str:
    base = baseline_table(df, cfg)
    lines = [f"# {cfg.research_title}", "", "## Дизайн исследования", "",
             f"Объект: **{russian_text(cfg.portfolio_nature)}**.",
             f"Исследовательский вопрос: **{russian_text(cfg.primary_research_question)}**",
             f"Базовая дата: {cfg.baseline_date.strftime('%d.%m.%Y')}; горизонт: {cfg.horizon_years:.1f} года — второе полугодие 2026 года (2026H2).",
             f"Общая экспозиция четырёх продуктов: **{base.exposure.sum():,.1f} млрд руб.**; сумма рассчитана из текущих данных.",
             "Публичные экспозиции ВТБ задают ориентиры объёма. В сочетании с внешними ставками и сценарными предпосылками они образуют синтетический портфель.",
             "Модель исследует влияние продуктового состава на финансовый результат с учётом кредитного риска и величину кредитных потерь. Критические доли ищутся там, где существует допустимое пересечение границы в сторону ухудшения результата (adverse crossing); наличие порога не предполагается заранее.",
             "RAFR (risk-adjusted financial result — финансовый результат с учётом кредитного риска) не является фактической прибылью ВТБ, NIM (net interest margin — чистой процентной маржой), внутренней продуктовой маржой или RAROC (risk-adjusted return on capital — доходностью капитала с учётом риска).", "",
             "Публичные данные и рыночные показатели-заменители → синтетический базовый портфель → финансовый стресс → чувствительность к продуктовому составу → чувствительность к факторам → обратное стресс-тестирование → управленческая интерпретация.", "",
             "## Термины и сокращения", "", TERMINOLOGY_NOTE, "",
             "Продукты: Mortgage (ипотека), Consumer (потребительские кредиты), Auto (автокредиты), Cards (кредитные карты).", "",
             "## Происхождение исходных данных и результатов", "",
             "| Категория | Элементы модели |", "|---|---|",
             "| FACT (опубликованный факт) | Компоненты экспозиции и ожидаемых кредитных убытков там, где источник проверен. Реконструированная и интерполированная история остаётся вспомогательной. |",
             "| MARKET PROXY (рыночный показатель-заменитель) | Внешние ставки Банка России по кредитам и фондированию; они не являются доходностью продуктов ВТБ или внутренней трансфертной ценой фондирования. |",
             "| SYNTHETIC (синтетическая конструкция) | Сочетание четырёх публичных экспозиций с внешними ставками в модельный портфель. |",
             "| MODEL ASSUMPTION (модельная предпосылка) | Множители умеренного и тяжёлого финансового стресса и сдвиги продуктовых долей. |",
             "| CALCULATED (расчётная величина) | Продуктовый показатель стоимости риска, CRAS, шестимесячный RAFR и допустимые пороги. |", "",
             "## Достаточность данных", ""]
    for _, r in adequacy.iterrows():
        lines.append(f"- **{russian_text(r['item'])}**: {russian_text(r['value'])} — {russian_text(r['assessment'])}")
    lines += ["", "## Базовый портфель", "", "Экспозиции и результат — в млрд руб.; ставки, стоимость риска и спред — в годовом выражении. Доля резерва ECL — показатель запаса на дату, а не стоимость риска за период.", "",
              "| Продукт | Экспозиция | Доля | Доля резерва ECL | Стоимость риска | Ставка по кредиту | Фондирование | Спред CRAS | Результат RAFR за 6 месяцев |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    bres = calculate_product_results(base, cfg.horizon_years, "Base")
    for _, r in bres.iterrows():
        lines.append(f"| {PRODUCT_LABELS[r['product']]} | {r['exposure']:,.1f} | {r['weight']:.2%} | {r['ecl_rate']:.2%} | {r['credit_cost']:.2%} | {r['product_rate']:.2%} | {r['funding_rate']:.2%} | {r['credit_risk_adjusted_spread']:.2%} | {r['risk_adjusted_financial_result_bn']:,.1f} |")
    for heading, names in [
        ("Финансовые стресс-сценарии", ["Base", "Moderate", "Severe"]),
        ("Эксперименты с продуктовой структурой", ["Base", "PortfolioMix", "SevereMix"]),
    ]:
        lines += ["", f"## {heading}", ""]
        if heading == "Эксперименты с продуктовой структурой":
            lines += ["Исходный состав сохраняет базовые доли. Чувствительность к продуктовому составу меняет доли четырёх продуктов при фиксированной общей экспозиции и базовых финансовых предпосылках; используется настроенный умеренный сдвиг долей. Тяжёлый сценарий с изменением состава сочетает тяжёлые финансовые предпосылки и настроенный тяжёлый сдвиг долей. Изменение состава является модельным экспериментом.", ""]
        lines += ["| Сценарий / эксперимент | Кредитные потери, млрд руб. | Годовой спред CRAS | Результат RAFR за 6 месяцев, млрд руб. |", "|---|---:|---:|---:|"]
        for _, r in summary[summary.scenario.isin(names)].iterrows():
            label = "Исходный состав" if heading == "Эксперименты с продуктовой структурой" and r['scenario'] == "Base" else scenario_label(r['scenario'])
            lines.append(f"| {label} | {r['credit_loss_bn']:,.1f} | {r['credit_risk_adjusted_spread']:.2%} | {r['risk_adjusted_financial_result_bn']:,.1f} |")
    sigma_view = sigmas.copy()
    sigma_view['product'] = sigma_view['product'].map(PRODUCT_LABELS)
    sigma_view = sigma_view.rename(columns={
        'product': 'Продукт', 'credit_cost_sigma': 'Станд. отклонение стоимости риска',
        'product_rate_sigma': 'Станд. отклонение кредитной ставки', 'funding_rate_sigma': 'Станд. отклонение фондирования',
        'credit_cost_n': 'Число наблюдений стоимости риска', 'product_rate_n': 'Число наблюдений кредитной ставки', 'funding_rate_n': 'Число наблюдений фондирования',
    })
    lines += ["", "## Диагностика калибровки", "", "Стандартные отклонения служат рабочими ориентирами сценариев и не являются статистически оценёнными параметрами прогноза. Ставки представлены в долях единицы.", "", sigma_view.to_markdown(index=False), "", "## Обратное стресс-тестирование", ""]
    lines += ["Если исходный сценарий уже находится на критической границе или ниже, пересечения в сторону ухудшения из этой точки нет. Для продуктовых долей модель возвращает NA с причиной. Статус THRESHOLD_BELOW_CURRENT_1X (граница требует снижения текущей стоимости риска) обозначает рассчитанный множитель ниже 1; это не порог ухудшения. Статус ALREADY_AT_OR_BELOW_BOUNDARY (исходный результат уже на границе или ниже) сопровождает NA для продуктовых долей.", "",
              "Множитель измеряется в разах относительно текущей стоимости риска; критическая доля — в долях единицы.", ""]
    sub = reverse[reverse.reverse_type.isin(["portfolio_credit_cost_multiplier", "critical_product_share_vs_mortgage"])]
    lines.append("| Сценарий | Вид порога | Продукт | Порог | Пояснение статуса |")
    lines.append("|---|---|---|---:|---|")
    for _, r in sub.iterrows():
        th = "NA" if pd.isna(r.threshold) else f"{r.threshold:.4f}"
        lines.append(f"| {scenario_label(r['scenario'])} | {REVERSE_LABELS[r['reverse_type']]} | {PRODUCT_LABELS[r['target_product']]} | {th} | {STATUS_LABELS.get(r['status'], r['status'])} |")
    lines += ["", "## Наиболее сильные локальные чувствительности", ""]
    top = factor.reindex(factor.delta_result_bn.abs().sort_values(ascending=False).index).head(12)
    lines.append("| Сценарий | Продукт | Изменение фактора | Изменение результата RAFR, млрд руб. |")
    lines.append("|---|---|---|---:|")
    for _, r in top.iterrows():
        lines.append(f"| {scenario_label(r['scenario'])} | {PRODUCT_LABELS[r['product']]} | {FACTOR_LABELS.get(r['factor'], r['factor'])} | {r['delta_result_bn']:,.2f} |")
    lines += ["", "## Устойчивость выводов и зависимость от предпосылок", ""]
    for _, r in robustness.iterrows():
        lines.append(f"- **{russian_text(r['classification'])}**: {russian_text(r['finding'])} {russian_text(r['dependency'])}")
    lines += ["", "## Управленческая интерпретация", "",
              "Чувствительности и допустимые пороги обратного стресс-тестирования позволяют условно интерпретировать последствия изменения состава портфеля. При текущих ставках и границе критические доли могут отсутствовать; NA является допустимым исследовательским результатом. Автоматический выбор оптимального портфеля не реализован. Последующая оптимизация требует экспертной фиксации доходной части модели и финансовых стресс-сценариев.",
              "", "## Ограничения интерпретации", "",
              "- Ставки по кредитам и фондированию — внешние рыночные показатели-заменители, а не доходность продуктов ВТБ или внутренний FTP.",
              "- Базовая ипотечная ставка взята из набора данных; альтернативная рыночная ставка используется только для анализа чувствительности.",
              "- Карточная ставка не учитывает льготный период, использование лимита, межбанковское вознаграждение за карточные операции и комиссии.",
              "- Операционные расходы, комиссии, налоги и стоимость капитала исключены.",
              "- Интеграция Почта Банка меняет периметр к первому полугодию 2026 года.",
              "- Короткая история позволяет проводить прозрачный сценарный анализ, анализ чувствительности и обратное стресс-тестирование, но не устойчивое эконометрическое оценивание.", "", "## Проверка качества данных", ""]
    for _, r in qa.iterrows():
        lines.append(f"- {STATUS_LABELS.get(r['status'], r['status'])}: {russian_text(r['check'])} — {russian_text(r['detail'])}")
    return "\n".join(lines) + "\n"


def run_model(config_path: Path) -> Dict[str, Path]:
    cfg = load_config(config_path)
    root = config_path.parent.parent
    input_path = Path(cfg.input_file) if Path(cfg.input_file).is_absolute() else root / cfg.input_file
    outdir = Path(cfg.output_dir) if Path(cfg.output_dir).is_absolute() else root / cfg.output_dir
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(input_path, cfg.data_sheet)
    qa = validate_data(df, cfg)
    adequacy = data_adequacy_report(df, cfg)
    product_results, sigmas = build_scenarios(df, cfg)
    summary = scenario_summary(product_results, cfg.horizon_years)
    portfolio_mix = portfolio_mix_sensitivity(product_results, cfg)
    factor = factor_sensitivity(product_results, cfg)
    reverse = reverse_stress(product_results, cfg)
    mortgage = mortgage_pricing_sensitivity(df, cfg)
    robustness = robustness_assessment(product_results, summary, mortgage, cfg)

    files = {
        "qa": outdir / "qa_report.csv",
        "adequacy": outdir / "data_adequacy.csv",
        "calibration": outdir / "calibration_sigmas.csv",
        "baseline": outdir / "baseline_product_results.csv",
        "scenario_product": outdir / "scenario_product_results.csv",
        "scenario_summary": outdir / "scenario_summary.csv",
        "portfolio_mix": outdir / "portfolio_mix_sensitivity.csv",
        "factor": outdir / "factor_sensitivity.csv",
        "reverse": outdir / "reverse_stress.csv",
        "mortgage": outdir / "mortgage_pricing_sensitivity.csv",
        "robustness": outdir / "results_robustness.csv",
        "report": outdir / "model_report.md",
    }
    qa.to_csv(files["qa"], index=False)
    adequacy.to_csv(files["adequacy"], index=False)
    sigmas.to_csv(files["calibration"], index=False)
    product_results[product_results.scenario == "Base"].to_csv(files["baseline"], index=False)
    product_results.to_csv(files["scenario_product"], index=False)
    summary.to_csv(files["scenario_summary"], index=False)
    portfolio_mix.to_csv(files["portfolio_mix"], index=False)
    factor.to_csv(files["factor"], index=False)
    reverse.to_csv(files["reverse"], index=False)
    mortgage.to_csv(files["mortgage"], index=False)
    robustness.to_csv(files["robustness"], index=False)
    files["report"].write_text(build_report(df, cfg, qa, adequacy, sigmas, product_results, summary, reverse, factor, robustness), encoding="utf-8")
    make_figures(summary, portfolio_mix, mortgage, outdir)
    files["structural"] = files["portfolio_mix"]  # Legacy returned-key alias.
    return files


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/model_config.json")
    args = p.parse_args()
    files = run_model(Path(args.config).resolve())
    print("Расчёт модели успешно завершён.")
    for k, v in files.items():
        if k == "structural":  # Compatibility key is not a presentation label.
            continue
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
