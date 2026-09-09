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
SCENARIO_ORDER = ["Base", "Moderate", "Severe", "Structural", "Combined"]

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
    structural_shift_pp: Mapping[str, object]
    mortgage_pricing_sensitivity: Mapping[str, object]
    reverse_stress: Mapping[str, float]
    qa_tolerance: float
    output_dir: str
    research_title: str = "Retail portfolio risk-return stress testing"
    portfolio_nature: str = "Synthetic four-product retail credit portfolio calibrated on public data"
    primary_research_question: str = "When does additional modeled income cease to compensate for higher credit losses?"


def load_config(path: Path) -> ModelConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
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
        structural_shift_pp=raw["structural_shift_pp"],
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


def apply_structural_shift(base: pd.DataFrame, shift_pp: Mapping[str, float]) -> pd.DataFrame:
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
        raise ValueError("Structural shift creates infeasible weights")
    out["weight"] = out["product"].map(weights)
    out["exposure"] = out.weight * total
    if not np.isclose(out.exposure.sum(), total):
        raise ValueError("Structural stress changed total exposure")
    return out


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
    out["scenario"] = scenario
    return out


def build_scenarios(df: pd.DataFrame, cfg: ModelConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    base = baseline_table(df, cfg)
    sig = calibration_sigmas(df, cfg)
    results = [calculate_product_results(base, cfg.horizon_years, "Base")]

    moderate = apply_financial_stress(base, sig, cfg.scenario_calibration["moderate"])
    results.append(calculate_product_results(moderate, cfg.horizon_years, "Moderate"))

    severe = apply_financial_stress(base, sig, cfg.scenario_calibration["severe"])
    results.append(calculate_product_results(severe, cfg.horizon_years, "Severe"))

    structural = apply_structural_shift(base, cfg.structural_shift_pp["moderate"])
    results.append(calculate_product_results(structural, cfg.horizon_years, "Structural"))

    combined = apply_structural_shift(severe, cfg.structural_shift_pp["severe"])
    results.append(calculate_product_results(combined, cfg.horizon_years, "Combined"))
    return pd.concat(results, ignore_index=True), sig


def scenario_summary(product_results: pd.DataFrame, horizon_years: float) -> pd.DataFrame:
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
    return g


def structural_sensitivity(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
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


def factor_sensitivity(product_results: pd.DataFrame, cfg: ModelConfig) -> pd.DataFrame:
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
            "finding": f"Structural RAFR is RUB {scenario_map['Structural']:,.1f} bn and Combined RAFR is RUB {scenario_map['Combined']:,.1f} bn.",
            "dependency": "Depends on explicit structural percentage-point shifts; only the fixed-total identity is mechanically stable.",
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


def make_figures(summary: pd.DataFrame, structural: pd.DataFrame, mortgage: pd.DataFrame, outdir: Path) -> None:
    figdir = outdir / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    order = ["Base", "Moderate", "Severe", "Structural", "Combined"]
    s = summary.set_index("scenario").reindex(order).dropna()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(s.index, s.risk_adjusted_financial_result_bn)
    ax.axhline(0, linewidth=1)
    ax.set_ylabel("RUB bn, 6M")
    ax.set_title("Risk-adjusted financial result by scenario")
    fig.tight_layout(); fig.savefig(figdir / "scenario_results.png", dpi=160); plt.close(fig)

    sev = structural[structural.scenario == "Severe"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for p, g in sev.groupby("target_product"):
        ax.plot(g.target_share * 100, g.risk_adjusted_financial_result_bn, label=p)
    ax.axhline(0, linewidth=1); ax.set_xlabel("Target product share, %"); ax.set_ylabel("RUB bn, 6M"); ax.set_title("Structural sensitivity — Severe"); ax.legend()
    fig.tight_layout(); fig.savefig(figdir / "structural_sensitivity_severe.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(mortgage.mortgage_pricing_rate * 100, mortgage.risk_adjusted_financial_result_bn)
    ax.axhline(0, linewidth=1); ax.set_xlabel("Mortgage pricing proxy, %"); ax.set_ylabel("RUB bn, 6M"); ax.set_title("Mortgage pricing sensitivity — Base")
    fig.tight_layout(); fig.savefig(figdir / "mortgage_pricing_sensitivity.png", dpi=160); plt.close(fig)


def build_report(df: pd.DataFrame, cfg: ModelConfig, qa: pd.DataFrame, adequacy: pd.DataFrame, sigmas: pd.DataFrame, product_results: pd.DataFrame, summary: pd.DataFrame, reverse: pd.DataFrame, factor: pd.DataFrame, robustness: pd.DataFrame) -> str:
    base = baseline_table(df, cfg)
    lines = [f"# {cfg.research_title}", "", "## Research design", "",
             f"Object: **{cfg.portfolio_nature}**.",
             f"Primary question: **{cfg.primary_research_question}**.",
             f"Baseline: {cfg.baseline_date.date()}; horizon: {cfg.horizon_years:.1f} year (2026H2).",
             f"Four-product baseline exposure: **RUB {base.exposure.sum():,.1f} bn** (derived from the current dataset, not hard-coded).",
             "Published VTB exposures anchor the baseline, while external pricing/funding proxies and scenario assumptions make the modeled portfolio synthetic.",
             "The model calculates an annualized credit-risk-adjusted spread and a six-month risk-adjusted financial result. It is not VTB actual profit, NIM, internal margin or RAROC.", "",
             "## Data adequacy", ""]
    for _, r in adequacy.iterrows():
        lines.append(f"- **{r['item']}**: {r['value']} — {r['assessment']}")
    lines += ["", "## Baseline", "", "| Product | Exposure | Weight | ECL rate | Credit cost | Pricing | Funding | CRAS | RAFR 6M |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    bres = calculate_product_results(base, cfg.horizon_years, "Base")
    for _, r in bres.iterrows():
        lines.append(f"| {r['product']} | {r['exposure']:,.1f} | {r['weight']:.2%} | {r['ecl_rate']:.2%} | {r['credit_cost']:.2%} | {r['product_rate']:.2%} | {r['funding_rate']:.2%} | {r['credit_risk_adjusted_spread']:.2%} | {r['risk_adjusted_financial_result_bn']:,.1f} |")
    lines += ["", "## Scenario summary", "", "| Scenario | Credit loss, RUB bn | CRAS annualized | RAFR 6M, RUB bn |", "|---|---:|---:|---:|"]
    for _, r in summary.iterrows():
        lines.append(f"| {r['scenario']} | {r['credit_loss_bn']:,.1f} | {r['credit_risk_adjusted_spread']:.2%} | {r['risk_adjusted_financial_result_bn']:,.1f} |")
    lines += ["", "## Calibration diagnostics", "", "Current sigma values are working scenario anchors, not statistically estimated forecast parameters.", "", sigmas.to_markdown(index=False), "", "## Reverse stress highlights", ""]
    sub = reverse[reverse.reverse_type.isin(["portfolio_credit_cost_multiplier", "critical_product_share_vs_mortgage"])]
    lines.append("| Scenario | Type | Product | Threshold | Status |")
    lines.append("|---|---|---|---:|---|")
    for _, r in sub.iterrows():
        th = "NA" if pd.isna(r.threshold) else f"{r.threshold:.4f}"
        lines.append(f"| {r['scenario']} | {r['reverse_type']} | {r['target_product']} | {th} | {r['status']} |")
    lines += ["", "## Largest local sensitivities", ""]
    top = factor.reindex(factor.delta_result_bn.abs().sort_values(ascending=False).index).head(12)
    lines.append("| Scenario | Product | Factor | Delta RAFR, RUB bn |")
    lines.append("|---|---|---|---:|")
    for _, r in top.iterrows():
        lines.append(f"| {r['scenario']} | {r['product']} | {r['factor']} | {r['delta_result_bn']:,.2f} |")
    lines += ["", "## Robustness and assumption dependence", ""]
    for _, r in robustness.iterrows():
        lines.append(f"- **{r['classification']}**: {r['finding']} {r['dependency']}")
    lines += ["", "## Interpretation constraints", "",
              "- Pricing/funding are external market proxies, not VTB product yield or internal FTP.",
              "- Base mortgage pricing keeps the dataset proxy; alternative market mortgage pricing is sensitivity only.",
              "- Cards proxy does not model grace period, utilization, interchange or fees.",
              "- Opex, fees, taxes and capital charges are excluded.",
              "- Pochta Bank integration creates a perimeter break into 2026H1.",
              "- The short history supports transparent scenario calibration and sensitivity/reverse stress, not robust econometric inference.", "", "## QA", ""]
    for _, r in qa.iterrows():
        lines.append(f"- {r['status']}: {r['check']} — {r['detail']}")
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
    structural = structural_sensitivity(product_results, cfg)
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
        "structural": outdir / "structural_sensitivity.csv",
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
    structural.to_csv(files["structural"], index=False)
    factor.to_csv(files["factor"], index=False)
    reverse.to_csv(files["reverse"], index=False)
    mortgage.to_csv(files["mortgage"], index=False)
    robustness.to_csv(files["robustness"], index=False)
    files["report"].write_text(build_report(df, cfg, qa, adequacy, sigmas, product_results, summary, reverse, factor, robustness), encoding="utf-8")
    make_figures(summary, structural, mortgage, outdir)
    return files


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/model_config.json")
    args = p.parse_args()
    files = run_model(Path(args.config).resolve())
    print("Model completed successfully.")
    for k, v in files.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
