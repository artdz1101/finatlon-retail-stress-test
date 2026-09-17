#!/usr/bin/env python3
"""Прозрачная сценарная модель синтетического розничного портфеля."""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRODUCTS = ["Mortgage", "Consumer", "Auto", "Cards"]
RISKIER_PRODUCTS = ["Consumer", "Auto", "Cards"]
SCENARIO_ORDER = ["Base", "Moderate", "Severe"]
PRODUCT_LABELS = {
    "Mortgage": "Ипотека",
    "Consumer": "Потребительские кредиты",
    "Auto": "Автокредиты",
    "Cards": "Кредитные карты",
}
SCENARIO_LABELS = {"Base": "Базовый", "Moderate": "Умеренный", "Severe": "Тяжёлый"}

ALIASES = {
    "Отчетная дата": "report_date", "Report date": "report_date", "report_date": "report_date",
    "Продукт": "product", "Product": "product", "product": "product",
    "Экспозиция, млрд руб.": "exposure", "Exposure, RUB bn": "exposure", "exposure": "exposure",
    "Стоимость кредитного риска, %": "credit_cost", "Credit cost, %": "credit_cost", "credit_cost": "credit_cost",
    "Рыночный pricing proxy, %": "product_rate_proxy", "Market pricing proxy, %": "product_rate_proxy",
    "product_rate_proxy": "product_rate_proxy", "product_rate": "product_rate_proxy",
    "Якорь средней маржи, %": "margin_anchor", "Average margin anchor, %": "margin_anchor", "margin_anchor": "margin_anchor",
    "Коэффициент передачи λ": "lambda", "Pass-through coefficient λ": "lambda", "lambda": "lambda",
    "Средневзвешенный pricing proxy, %": "weighted_product_rate", "Weighted pricing proxy, %": "weighted_product_rate",
    "weighted_product_rate": "weighted_product_rate",
    "Синтетическая маржа до кредитного риска, %": "synthetic_margin",
    "Synthetic pre-credit margin, %": "synthetic_margin", "synthetic_margin": "synthetic_margin",
    "Риск-скорректированная ставка, %": "risk_adjusted_rate", "Risk-adjusted rate, %": "risk_adjusted_rate",
    "risk_adjusted_rate": "risk_adjusted_rate",
    "Коэффициент периода": "period_factor", "Period factor": "period_factor", "period_factor": "period_factor",
    "Риск-скорректированный результат, млрд руб.": "source_raf_result",
    "Risk-adjusted result, RUB bn": "source_raf_result", "risk_adjusted_result": "source_raf_result",
}
REQUIRED = [
    "report_date", "product", "exposure", "credit_cost", "product_rate_proxy",
    "margin_anchor", "lambda", "weighted_product_rate", "synthetic_margin",
    "risk_adjusted_rate", "period_factor",
]


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
    portfolio_mix_sensitivity: Mapping[str, object]
    reverse_stress: Mapping[str, object]
    qa_tolerance: float
    output_dir: str
    research_title: str
    portfolio_nature: str
    primary_research_question: str


def load_config(path: Path) -> ModelConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ModelConfig(
        input_file=raw["input_file"],
        data_sheet=raw.get("data_sheet", "MODEL_DATA"),
        baseline_date=pd.Timestamp(raw["baseline_date"]),
        history_start_date=pd.Timestamp(raw["history_start_date"]),
        history_end_date=pd.Timestamp(raw["history_end_date"]),
        horizon_years=float(raw.get("horizon_years", 0.5)),
        products=list(raw.get("products", PRODUCTS)),
        critical_result_bn=float(raw.get("critical_result_bn", 0.0)),
        scenario_calibration=raw["scenario_calibration"],
        portfolio_mix_sensitivity=raw.get("portfolio_mix_sensitivity", {}),
        reverse_stress=raw.get("reverse_stress", {}),
        qa_tolerance=float(raw.get("qa_tolerance", 1e-8)),
        output_dir=raw.get("output_dir", "outputs"),
        research_title=raw["research_title"],
        portfolio_nature=raw["portfolio_nature"],
        primary_research_question=raw["primary_research_question"],
    )


def normalize_columns(raw: pd.DataFrame) -> pd.DataFrame:
    renamed = {column: ALIASES[str(column).strip()] for column in raw.columns if str(column).strip() in ALIASES}
    df = raw.rename(columns=renamed).copy()
    missing = [column for column in REQUIRED if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required MODEL_DATA columns: {missing}")
    df["product"] = df["product"].astype(str).str.strip()
    df = df[df["product"].isin(PRODUCTS)].copy()
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce", format="mixed", dayfirst=True)
    numeric = [column for column in REQUIRED if column not in {"report_date", "product"}]
    if "source_raf_result" in df.columns:
        numeric.append("source_raf_result")
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    columns = REQUIRED + (["source_raf_result"] if "source_raf_result" in df.columns else [])
    return df[columns].sort_values(["report_date", "product"]).reset_index(drop=True)


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


def recompute_margin(params: pd.DataFrame) -> pd.DataFrame:
    """Apply m_i = M + lambda * (p_i - weighted_p) to the current composition."""
    out = params.copy()
    total = float(out["exposure"].sum())
    if total <= 0:
        raise ValueError("Portfolio exposure must be positive")
    out["weight"] = out["exposure"] / total
    weighted_proxy = float((out["weight"] * out["product_rate_proxy"]).sum())
    out["weighted_product_rate"] = weighted_proxy
    out["synthetic_margin"] = out["margin_anchor"] + out["lambda"] * (
        out["product_rate_proxy"] - weighted_proxy
    )
    out["risk_adjusted_rate"] = out["synthetic_margin"] - out["credit_cost"]
    return out


def validate_data(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows: List[dict] = []

    def add(check: str, status: str, detail: str) -> None:
        rows.append({"check": check, "status": status, "detail": detail})

    numeric = [column for column in REQUIRED if column not in {"report_date", "product"}]
    add("duplicate report_date/product", "PASS" if not df.duplicated(["report_date", "product"]).any() else "FAIL",
        str(int(df.duplicated(["report_date", "product"]).sum())))
    missing = int(df[numeric].isna().sum().sum())
    add("complete numeric inputs", "PASS" if missing == 0 else "FAIL", f"missing_cells={missing}")
    finite = bool(np.isfinite(df[numeric].to_numpy(dtype=float)).all())
    add("finite numeric inputs", "PASS" if finite else "FAIL", f"all_finite={finite}")
    add("positive exposure", "PASS" if (df.exposure > 0).all() else "FAIL", f"bad_rows={int((df.exposure <= 0).sum())}")

    expected_dates = df[(df.report_date >= cfg.history_start_date) & (df.report_date <= cfg.history_end_date)]
    panel_ok = all(set(group["product"]) == set(cfg.products) for _, group in expected_dates.groupby("report_date"))
    add("complete four-product panel", "PASS" if panel_ok else "FAIL",
        f"dates={expected_dates.report_date.nunique()}, rows={len(expected_dates)}")

    max_weighted_diff = 0.0
    max_margin_diff = 0.0
    max_rate_diff = 0.0
    max_result_diff = 0.0
    for _, group in df.groupby("report_date"):
        calculated = recompute_margin(group)
        max_weighted_diff = max(max_weighted_diff, float((calculated.weighted_product_rate - group.weighted_product_rate).abs().max()))
        max_margin_diff = max(max_margin_diff, float((calculated.synthetic_margin - group.synthetic_margin).abs().max()))
        max_rate_diff = max(max_rate_diff, float((calculated.risk_adjusted_rate - group.risk_adjusted_rate).abs().max()))
        if "source_raf_result" in group.columns:
            calculated_result = calculated.exposure * calculated.risk_adjusted_rate * calculated.period_factor
            max_result_diff = max(max_result_diff, float((calculated_result - group.source_raf_result).abs().max()))
    tol = cfg.qa_tolerance
    add("weighted pricing proxy formula", "PASS" if max_weighted_diff <= tol else "FAIL", f"max_abs_diff={max_weighted_diff:.3e}")
    add("synthetic margin formula", "PASS" if max_margin_diff <= tol else "FAIL", f"max_abs_diff={max_margin_diff:.3e}")
    add("risk-adjusted rate formula", "PASS" if max_rate_diff <= tol else "FAIL", f"max_abs_diff={max_rate_diff:.3e}")
    if "source_raf_result" in df.columns:
        add("RAFR source formula", "PASS" if max_result_diff <= tol else "FAIL", f"max_abs_diff={max_result_diff:.3e}")

    base = df[df.report_date.eq(cfg.baseline_date)]
    add("baseline products present", "PASS" if set(base["product"]) == set(cfg.products) else "FAIL",
        f"products={sorted(base['product'].tolist())}")
    add("baseline total exposure", "INFO", f"RUB_bn={base.exposure.sum():.1f}")
    report = pd.DataFrame(rows)
    failed = report[report.status.eq("FAIL")]
    if not failed.empty:
        raise ValueError("QA failed:\n" + failed.to_string(index=False))
    return report


def data_adequacy_report(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    history = df[(df.report_date >= cfg.history_start_date) & (df.report_date <= cfg.history_end_date)]
    return pd.DataFrame([
        {"item": "Панель данных", "value": f"{history.report_date.nunique()} дат / {len(history)} строк",
         "assessment": "Пригодна для прозрачного сценарного анализа; не для устойчивой эконометрической оценки"},
        {"item": "Доходная часть", "value": "margin_anchor, lambda, pricing proxy",
         "assessment": "Синтетическая конструкция из листа MODEL_DATA"},
        {"item": "Стоимость риска", "value": "annualized credit_cost",
         "assessment": "Вход MODEL_DATA; формула RAFR проверена по строкам Excel"},
    ])


def baseline_table(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = df[df.report_date.eq(cfg.baseline_date) & df["product"].isin(cfg.products)].copy()
    if set(base["product"]) != set(cfg.products):
        raise ValueError("Baseline does not contain all configured products")
    return recompute_margin(base).sort_values("product").reset_index(drop=True)


def apply_financial_stress(base: pd.DataFrame, assumptions: Mapping[str, float]) -> pd.DataFrame:
    out = base.copy()
    out["credit_cost"] = out["credit_cost"] + float(assumptions["credit_cost_shift_pp"]) / 100.0
    out["margin_anchor"] = out["margin_anchor"] + float(assumptions["margin_anchor_shift_pp"]) / 100.0
    if (out.credit_cost < 0).any() or (out.margin_anchor < 0).any():
        raise ValueError("Stress assumptions create negative credit cost or margin anchor")
    return recompute_margin(out)


def apply_portfolio_mix_shift(base: pd.DataFrame, target: str, share_change_pp: float) -> pd.DataFrame:
    if target not in RISKIER_PRODUCTS:
        raise ValueError(f"Target must be one of {RISKIER_PRODUCTS}")
    out = base.copy()
    total = float(out.exposure.sum())
    amount = total * float(share_change_pp) / 100.0
    mortgage_mask = out["product"].eq("Mortgage")
    target_mask = out["product"].eq(target)
    if amount < 0 or amount > float(out.loc[mortgage_mask, "exposure"].iloc[0]) + 1e-12:
        raise ValueError("Portfolio-mix shift is outside the feasible range")
    out.loc[mortgage_mask, "exposure"] -= amount
    out.loc[target_mask, "exposure"] += amount
    shifted = recompute_margin(out)
    if not np.isclose(shifted.exposure.sum(), total):
        raise ValueError("Portfolio-mix shift changed total exposure")
    return shifted


def calculate_product_results(params: pd.DataFrame, horizon_years: float, scenario: str) -> pd.DataFrame:
    out = recompute_margin(params)
    out["risk_adjusted_financial_result_bn"] = out.exposure * out.risk_adjusted_rate * horizon_years
    out["scenario"] = scenario
    return out


def build_scenarios(df: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = baseline_table(df, cfg)
    scenarios = [calculate_product_results(base, cfg.horizon_years, "Base")]
    for scenario in ["Moderate", "Severe"]:
        stressed = apply_financial_stress(base, cfg.scenario_calibration[scenario.lower()])
        scenarios.append(calculate_product_results(stressed, cfg.horizon_years, scenario))
    return pd.concat(scenarios, ignore_index=True)


def scenario_summary(product_results: pd.DataFrame) -> pd.DataFrame:
    summary = product_results.groupby("scenario", as_index=False).agg(
        risk_adjusted_financial_result_bn=("risk_adjusted_financial_result_bn", "sum")
    )
    summary["scenario"] = pd.Categorical(summary.scenario, SCENARIO_ORDER, ordered=True)
    summary = summary.sort_values("scenario").reset_index(drop=True)
    summary["scenario"] = summary["scenario"].astype(str)
    return summary


def solve_critical_margin(params: pd.DataFrame, target: str, cfg: ModelConfig) -> Tuple[float, str]:
    """Solve target m_i such that total portfolio RAFR reaches the configured boundary."""
    group = params.set_index("product")
    if target not in group.index or float(group.loc[target, "exposure"]) <= 0:
        return math.nan, "NO_FEASIBLE_SOLUTION"
    other = group.drop(index=target)
    other_annual = float((other.exposure * (other.synthetic_margin - other.credit_cost)).sum())
    target_exposure = float(group.loc[target, "exposure"])
    target_cc = float(group.loc[target, "credit_cost"])
    boundary_annual = cfg.critical_result_bn / cfg.horizon_years
    threshold = target_cc + (boundary_annual - other_annual) / target_exposure
    status = "FEASIBLE" if threshold >= 0 else "NEGATIVE_THRESHOLD"
    return threshold, status


def critical_margin_table(product_results: pd.DataFrame, cfg: ModelConfig, scenario: str = "Base") -> pd.DataFrame:
    group = product_results[product_results.scenario.eq(scenario)].copy()
    if group.empty:
        raise ValueError(f"Scenario not found: {scenario}")
    mortgage_margin = float(group.loc[group["product"].eq("Mortgage"), "synthetic_margin"].iloc[0])
    rows = []
    for product in cfg.products:
        threshold, status = solve_critical_margin(group, product, cfg)
        current = float(group.loc[group["product"].eq(product), "synthetic_margin"].iloc[0])
        rows.append({
            "product": product,
            "current_margin": current,
            "critical_margin": threshold,
            "required_margin_premium_vs_mortgage": 0.0 if product == "Mortgage" else threshold - mortgage_margin,
            "status": "REFERENCE_PRODUCT" if product == "Mortgage" else status,
        })
    return pd.DataFrame(rows)


def stress_critical_margin(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    values = []
    statuses = []
    for scenario in SCENARIO_ORDER:
        table = critical_margin_table(product_results, cfg, scenario)
        for _, row in table.iterrows():
            values.append({"product": row["product"], "scenario": scenario, "critical_margin": row["critical_margin"]})
            statuses.append({"product": row["product"], "scenario": scenario, "status": row["status"]})
    value_frame = pd.DataFrame(values).pivot(index="product", columns="scenario", values="critical_margin")
    status_frame = pd.DataFrame(statuses).pivot(index="product", columns="scenario", values="status")
    result = pd.DataFrame({"product": cfg.products})
    for scenario in SCENARIO_ORDER:
        result[f"{scenario.lower()}_critical_margin"] = result["product"].map(value_frame[scenario])
        result[f"{scenario.lower()}_status"] = result["product"].map(status_frame[scenario])
    return result


def portfolio_mix_sensitivity(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = product_results[product_results.scenario.eq("Base")].copy()
    rows = []
    for product in RISKIER_PRODUCTS:
        baseline_threshold, _ = solve_critical_margin(base, product, cfg)
        for change in cfg.portfolio_mix_sensitivity.get("share_changes_pp", [1.0, 5.0, 10.0]):
            shifted = apply_portfolio_mix_shift(base, product, float(change))
            threshold, status = solve_critical_margin(shifted, product, cfg)
            rows.append({
                "product": product,
                "share_change_pp": float(change),
                "critical_margin_change": threshold - baseline_threshold,
                "shifted_critical_margin": threshold,
                "status": status,
            })
    return pd.DataFrame(rows)


def reverse_stress(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    rows = []
    for scenario in SCENARIO_ORDER:
        group = product_results[product_results.scenario.eq(scenario)].copy()
        if group.empty:
            continue
        total = float(group.exposure.sum())
        base_result = float(group.risk_adjusted_financial_result_bn.sum())
        for product in cfg.products:
            threshold, status = solve_critical_margin(group, product, cfg)
            rows.append({
                "scenario": scenario, "reverse_type": "critical_margin", "target_product": product,
                "threshold": threshold, "threshold_unit": "annual_rate", "status": status,
            })
        if not cfg.reverse_stress.get("include_critical_share", True):
            continue
        indexed = group.set_index("product")
        weights = (indexed.exposure / total).to_dict()
        annual_boundary_rate = cfg.critical_result_bn / total / cfg.horizon_years
        current_annual_rate = base_result / total / cfg.horizon_years
        for product in RISKIER_PRODUCTS:
            cc_gap = float(indexed.loc[product, "credit_cost"] - indexed.loc["Mortgage", "credit_cost"])
            max_share = weights[product] + weights["Mortgage"]
            if base_result <= cfg.critical_result_bn + cfg.qa_tolerance:
                threshold, status = math.nan, "ALREADY_AT_OR_BELOW_BOUNDARY"
            elif cc_gap <= 0:
                threshold, status = math.nan, "NO_ADVERSE_CROSSING"
            else:
                threshold = weights[product] + (current_annual_rate - annual_boundary_rate) / cc_gap
                if threshold > max_share + cfg.qa_tolerance:
                    threshold, status = math.nan, "NO_FEASIBLE_CROSSING"
                else:
                    status = "FEASIBLE"
            rows.append({
                "scenario": scenario, "reverse_type": "critical_share_vs_mortgage", "target_product": product,
                "threshold": threshold, "threshold_unit": "share", "status": status,
            })
    return pd.DataFrame(rows)


def factor_sensitivity(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
    base = product_results[product_results.scenario.eq("Base")].copy()
    rows = []
    for factor, cc_shift, anchor_shift in [
        ("credit_cost_plus_1pp", 1.0, 0.0),
        ("margin_anchor_minus_0_5pp", 0.0, -0.5),
    ]:
        stressed = apply_financial_stress(base, {
            "credit_cost_shift_pp": cc_shift,
            "margin_anchor_shift_pp": anchor_shift,
        })
        result = calculate_product_results(stressed, cfg.horizon_years, factor)
        rows.append({"factor": factor, "risk_adjusted_financial_result_bn": float(result.risk_adjusted_financial_result_bn.sum())})
    return pd.DataFrame(rows)


def make_figures(summary: pd.DataFrame, critical: pd.DataFrame, mix: pd.DataFrame, outdir: Path) -> None:
    figdir = outdir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([SCENARIO_LABELS[x] for x in summary.scenario], summary.risk_adjusted_financial_result_bn)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("RAFR, млрд руб. за 6 месяцев")
    ax.set_title("Сценарный финансовый результат")
    fig.tight_layout()
    fig.savefig(figdir / "scenario_summary.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    view = critical.copy()
    x = np.arange(len(view))
    ax.bar(x - 0.18, view.current_margin * 100, width=0.36, label="Текущая маржа")
    ax.bar(x + 0.18, view.critical_margin * 100, width=0.36, label="Критическая маржа")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, [PRODUCT_LABELS[p] for p in view["product"]], rotation=12)
    ax.set_ylabel("% годовых")
    ax.set_title("Текущая и критическая маржа: базовый сценарий")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "critical_margin.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    for product, group in mix.groupby("product"):
        ax.plot(group.share_change_pp, group.critical_margin_change * 100, marker="o", label=PRODUCT_LABELS[product])
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Увеличение доли за счёт ипотеки, п.п.")
    ax.set_ylabel("Изменение критической маржи, п.п.")
    ax.set_title("Чувствительность критической маржи к составу")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figdir / "portfolio_mix_critical_margin.png", dpi=160)
    plt.close(fig)


def build_report(cfg: ModelConfig, qa: pd.DataFrame, adequacy: pd.DataFrame, product_results: pd.DataFrame,
                 summary: pd.DataFrame, critical: pd.DataFrame, stress: pd.DataFrame,
                 mix: pd.DataFrame, reverse: pd.DataFrame) -> str:
    base = product_results[product_results.scenario.eq("Base")]
    summary_view = summary.rename(columns={
        "scenario": "Сценарий", "risk_adjusted_financial_result_bn": "RAFR, млрд руб."
    })
    critical_view = critical.copy()
    for column in ["current_margin", "critical_margin", "required_margin_premium_vs_mortgage"]:
        critical_view[column] *= 100
    critical_view = critical_view.rename(columns={
        "product": "Продукт", "current_margin": "Текущая маржа, %",
        "critical_margin": "Критическая маржа, %",
        "required_margin_premium_vs_mortgage": "Премия к ипотеке, п.п.", "status": "Статус",
    })
    stress_view = stress.copy()
    for column in [name for name in stress_view.columns if name.endswith("critical_margin")]:
        stress_view[column] *= 100
    mix_view = mix.copy()
    mix_view["critical_margin_change"] *= 100
    mix_view["shifted_critical_margin"] *= 100
    mix_view = mix_view.rename(columns={
        "product": "Продукт", "share_change_pp": "Изменение доли, п.п.",
        "critical_margin_change": "Изменение критической маржи, п.п.",
        "shifted_critical_margin": "Новая критическая маржа, %", "status": "Статус",
    })
    lines = [
        f"# {cfg.research_title}", "",
        f"**Исследовательский вопрос:** {cfg.primary_research_question}", "",
        f"Объект исследования — {cfg.portfolio_nature}. Продуктовые доходы синтетические; RAFR "
        "(risk-adjusted financial result — финансовый результат с учётом риска) не является прибылью ВТБ или RAROC.", "",
        "## Метод", "",
        "Синтетическая маржа до кредитного риска рассчитывается как "
        "`m_i,t = M_t + lambda * (p_i,t - weighted_p_t)`. Затем "
        "`RAR_i,t = m_i,t - credit_cost_i,t`, а "
        "`RAFR_i,t = Exposure_i,t * RAR_i,t * 0.5`.", "",
        "Критическая маржа продукта — значение его маржи, при котором совокупный RAFR портфеля равен нулю "
        "при неизменных параметрах остальных продуктов. Она отличается от собственной маржи безубыточности продукта, "
        "поскольку учитывает вклад всего портфеля.", "",
        "Moderate: стоимость риска +1 п.п., якорь маржи −0,5 п.п. Severe: стоимость риска +3 п.п., "
        "якорь маржи −1 п.п. Это прозрачные модельные предпосылки, а не макроэкономический прогноз.", "",
        "## Сценарный результат", "",
        summary_view.to_markdown(index=False, floatfmt=".3f"), "",
        "## Главная таблица: критическая маржа", "",
        critical_view.to_markdown(index=False, floatfmt=".2f"), "",
        "`required_margin_premium_vs_mortgage` показывает разницу между критической маржой продукта и текущей "
        "синтетической маржой ипотеки. Отрицательный порог имеет явный статус: остальные продукты уже создают "
        "достаточный запас для достижения нулевой границы при отрицательной марже выбранного продукта.", "",
        "## Критическая маржа в стрессе", "",
        stress_view.to_markdown(index=False, floatfmt=".2f"), "",
        "## Чувствительность к составу", "",
        mix_view.to_markdown(index=False, floatfmt=".2f"), "",
        "При изменении состава общая экспозиция сохраняется, средневзвешенный pricing proxy пересчитывается, "
        "а маржа вновь центрируется вокруг заданного `margin_anchor`.", "",
        "## Ограничения", "",
        "Экспозиции и стоимость риска опираются на набор данных, pricing proxy является рыночным показателем-заменителем, "
        "а маржа — синтетической конструкцией. Комиссии, операционные расходы, налоги, капитал, RWA и RAROC не рассчитываются. "
        "Короткая история не используется для регрессии, машинного обучения или причинных выводов.", "",
        "## Проверки данных", "",
        qa.to_markdown(index=False), "",
        adequacy.to_markdown(index=False), "",
        f"Базовая экспозиция: {base.exposure.sum():,.1f} млрд руб.; базовый RAFR: "
        f"{base.risk_adjusted_financial_result_bn.sum():,.3f} млрд руб.", "",
        "Вспомогательная критическая доля сохранена в `reverse_stress.csv`, но не является главным результатом.",
    ]
    return "\n".join(lines).replace("6,573.0", "6 573,0")


def run_model(config_path: Path) -> Dict[str, Path]:
    cfg = load_config(config_path)
    root = config_path.parent.parent
    input_path = Path(cfg.input_file) if Path(cfg.input_file).is_absolute() else root / cfg.input_file
    outdir = Path(cfg.output_dir) if Path(cfg.output_dir).is_absolute() else root / cfg.output_dir
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(input_path, cfg.data_sheet)
    qa = validate_data(df, cfg)
    adequacy = data_adequacy_report(df, cfg)
    product_results = build_scenarios(df, cfg)
    summary = scenario_summary(product_results)
    critical = critical_margin_table(product_results, cfg)
    stress = stress_critical_margin(product_results, cfg)
    mix = portfolio_mix_sensitivity(product_results, cfg)
    reverse = reverse_stress(product_results, cfg)
    factor = factor_sensitivity(product_results, cfg)

    files = {
        "qa": outdir / "qa_report.csv",
        "adequacy": outdir / "data_adequacy.csv",
        "baseline": outdir / "baseline_product_results.csv",
        "scenario_product": outdir / "scenario_product_results.csv",
        "scenario_summary": outdir / "scenario_summary.csv",
        "critical_margin": outdir / "critical_margin.csv",
        "stress_critical_margin": outdir / "stress_critical_margin.csv",
        "portfolio_mix": outdir / "portfolio_mix_sensitivity.csv",
        "factor": outdir / "factor_sensitivity.csv",
        "reverse": outdir / "reverse_stress.csv",
        "report": outdir / "model_report.md",
    }
    qa.to_csv(files["qa"], index=False)
    adequacy.to_csv(files["adequacy"], index=False)
    compact_columns = ["scenario", "product", "exposure", "weight", "credit_cost", "product_rate_proxy",
                       "margin_anchor", "lambda", "weighted_product_rate", "synthetic_margin",
                       "risk_adjusted_rate", "risk_adjusted_financial_result_bn"]
    product_results[product_results.scenario.eq("Base")][compact_columns].to_csv(files["baseline"], index=False)
    product_results[compact_columns].to_csv(files["scenario_product"], index=False)
    summary.to_csv(files["scenario_summary"], index=False)
    critical.to_csv(files["critical_margin"], index=False)
    stress.to_csv(files["stress_critical_margin"], index=False)
    mix.to_csv(files["portfolio_mix"], index=False)
    factor.to_csv(files["factor"], index=False)
    reverse.to_csv(files["reverse"], index=False)
    files["report"].write_text(
        build_report(cfg, qa, adequacy, product_results, summary, critical, stress, mix, reverse), encoding="utf-8"
    )
    make_figures(summary, critical, mix, outdir)
    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/model_config.json")
    args = parser.parse_args()
    files = run_model(Path(args.config).resolve())
    print("Расчёт модели успешно завершён.")
    for name, path in files.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
