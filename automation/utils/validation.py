"""
Automated validation for LBIC simulation results.

Layer 2: Batch-level statistical checks (magnitude, cutoff, inter-case physics).
Layer 3: Cross-version regression against a saved v2 baseline reference.
"""
import json
import os
from pathlib import Path

from automation.utils.plt_parser import (
    extract_photocurrent,
    sanity_check,
    DARK_CURRENT_THRESHOLD,
)

REFERENCE_DIR = Path(__file__).parent.parent / "config" / "reference"

# Expected photocurrent magnitude range for 500nm YOUR_MATERIAL device at V=1V, λ=450nm
EXPECTED_CURRENT_MIN = 1e-11
EXPECTED_CURRENT_MAX = 5e-10

# Cutoff should be near bx≈220-270nm depending on parameter set
EXPECTED_CUTOFF_MIN_NM = 180
EXPECTED_CUTOFF_MAX_NM = 300

# Parallel TB should increase photocurrent relative to baseline
PARALLEL_TB_CASES = ["tb_parallel_single", "tb_parallel_multi"]
# Vertical TB should decrease photocurrent (slightly) relative to baseline
VERTICAL_TB_CASES = ["tb_vertical_single", "tb_double", "tb_wide", "tb_dense"]


# ---------------------------------------------------------------------------
# Layer 2: Batch-level statistical validation
# ---------------------------------------------------------------------------

def validate_batch(results, dark_threshold=DARK_CURRENT_THRESHOLD):
    """
    Validate a batch of LBIC results.

    Parameters
    ----------
    results : dict
        {case_name: {bx_nm: abs_current, ...}, ...}
        At minimum should contain "baseline".

    Returns
    -------
    report : dict
        {"passed": bool, "checks": [{"name", "status", "message"}, ...]}
    """
    checks = []

    # --- Check 1: Baseline magnitude ---
    baseline = results.get("baseline", {})
    if baseline:
        active_currents = [v for v in baseline.values() if v > dark_threshold]
        if active_currents:
            peak = max(active_currents)
            if EXPECTED_CURRENT_MIN <= peak <= EXPECTED_CURRENT_MAX:
                checks.append({"name": "baseline_magnitude", "status": "OK",
                    "message": f"Peak {peak:.2e} A in expected range"})
            else:
                checks.append({"name": "baseline_magnitude", "status": "WARN",
                    "message": f"Peak {peak:.2e} A outside [{EXPECTED_CURRENT_MIN:.0e}, {EXPECTED_CURRENT_MAX:.0e}]"})
        else:
            checks.append({"name": "baseline_magnitude", "status": "FAIL",
                "message": "No active photocurrent above dark threshold"})

    # --- Check 2: Cutoff position ---
    if baseline:
        sorted_bx = sorted(baseline.keys())
        cutoff_bx = None
        for bx in sorted_bx:
            if baseline[bx] < dark_threshold:
                cutoff_bx = bx
                break
        if cutoff_bx is not None:
            if EXPECTED_CUTOFF_MIN_NM <= cutoff_bx <= EXPECTED_CUTOFF_MAX_NM:
                checks.append({"name": "cutoff_position", "status": "OK",
                    "message": f"Cutoff at bx={cutoff_bx}nm (expected {EXPECTED_CUTOFF_MIN_NM}-{EXPECTED_CUTOFF_MAX_NM}nm)"})
            else:
                checks.append({"name": "cutoff_position", "status": "WARN",
                    "message": f"Cutoff at bx={cutoff_bx}nm outside expected range"})
        else:
            checks.append({"name": "cutoff_position", "status": "INFO",
                "message": "No cutoff detected (all positions have signal)"})

    # --- Check 3: Inter-case physics ---
    if baseline:
        baseline_mean = _mean_active(baseline, dark_threshold)
        if baseline_mean and baseline_mean > 0:
            for case in PARALLEL_TB_CASES:
                if case not in results:
                    continue
                case_mean = _mean_active(results[case], dark_threshold)
                if case_mean is None:
                    continue
                ratio = case_mean / baseline_mean
                if ratio >= 1.0:
                    checks.append({"name": f"physics_{case}", "status": "OK",
                        "message": f"Mean ratio {ratio:.4f} >= 1.0 (parallel TB increases current)"})
                else:
                    checks.append({"name": f"physics_{case}", "status": "WARN",
                        "message": f"Mean ratio {ratio:.4f} < 1.0 (expected parallel TB to increase current)"})

            for case in VERTICAL_TB_CASES:
                if case not in results:
                    continue
                case_mean = _mean_active(results[case], dark_threshold)
                if case_mean is None:
                    continue
                ratio = case_mean / baseline_mean
                if ratio <= 1.01:
                    checks.append({"name": f"physics_{case}", "status": "OK",
                        "message": f"Mean ratio {ratio:.4f} <= 1.01 (vertical TB slightly reduces current)"})
                else:
                    checks.append({"name": f"physics_{case}", "status": "WARN",
                        "message": f"Mean ratio {ratio:.4f} > 1.01 (unexpected increase for vertical TB)"})

    passed = all(c["status"] in ("OK", "INFO") for c in checks)
    return {"passed": passed, "checks": checks}


# ---------------------------------------------------------------------------
# Layer 3: Cross-version regression
# ---------------------------------------------------------------------------

def save_reference(results, version_tag, description=""):
    """Save a results dict as a reference baseline for future regression."""
    os.makedirs(REFERENCE_DIR, exist_ok=True)
    ref_path = REFERENCE_DIR / f"reference_{version_tag}.json"
    data = {
        "version": version_tag,
        "description": description,
        "results": {case: {str(k): v for k, v in positions.items()}
                    for case, positions in results.items()},
    }
    with open(ref_path, "w") as f:
        json.dump(data, f, indent=2)
    return str(ref_path)


def load_reference(version_tag):
    """Load a saved reference baseline."""
    ref_path = REFERENCE_DIR / f"reference_{version_tag}.json"
    if not ref_path.exists():
        return None
    with open(ref_path) as f:
        data = json.load(f)
    return {case: {int(k): v for k, v in positions.items()}
            for case, positions in data["results"].items()}


def regression_compare(new_results, ref_version="v2", tolerance=0.10):
    """
    Compare new results against a saved reference.

    Parameters
    ----------
    new_results : dict  — {case: {bx_nm: current}}
    ref_version : str   — version tag of saved reference
    tolerance   : float — max allowed relative deviation (0.10 = 10%)

    Returns
    -------
    report : dict
        {"passed": bool, "ref_version": str, "comparisons": [...]}
    """
    ref = load_reference(ref_version)
    if ref is None:
        return {"passed": True, "ref_version": ref_version,
                "comparisons": [{"status": "SKIP",
                    "message": f"No reference found for '{ref_version}'"}]}

    comparisons = []
    for case in ref:
        if case not in new_results:
            comparisons.append({"case": case, "status": "SKIP",
                "message": f"Case '{case}' not in new results"})
            continue

        ref_data = ref[case]
        new_data = new_results[case]
        deviations = []

        for bx in ref_data:
            if bx not in new_data:
                continue
            ref_val = ref_data[bx]
            new_val = new_data[bx]
            if ref_val > DARK_CURRENT_THRESHOLD:
                dev = abs(new_val - ref_val) / ref_val
                deviations.append((bx, dev))

        if not deviations:
            comparisons.append({"case": case, "status": "SKIP",
                "message": "No overlapping active positions"})
            continue

        max_dev_bx, max_dev = max(deviations, key=lambda x: x[1])
        mean_dev = sum(d for _, d in deviations) / len(deviations)

        if max_dev <= tolerance:
            comparisons.append({"case": case, "status": "OK",
                "message": f"Max deviation {max_dev:.1%} at bx={max_dev_bx}nm (mean {mean_dev:.1%})"})
        else:
            comparisons.append({"case": case, "status": "FAIL",
                "message": f"Max deviation {max_dev:.1%} at bx={max_dev_bx}nm exceeds {tolerance:.0%} tolerance"})

    passed = all(c["status"] in ("OK", "SKIP") for c in comparisons)
    return {"passed": passed, "ref_version": ref_version, "comparisons": comparisons}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean_active(data, dark_threshold):
    active = [v for v in data.values() if v > dark_threshold]
    return sum(active) / len(active) if active else None


# PLACEHOLDER_PRINT_REPORT


def print_report(batch_report=None, regression_report=None):
    """Print human-readable validation report."""
    if batch_report:
        status = "PASS" if batch_report["passed"] else "FAIL"
        print(f"\n{'='*60}")
        print(f"Batch Validation: {status}")
        print(f"{'='*60}")
        for c in batch_report["checks"]:
            icon = {"OK": "+", "WARN": "!", "FAIL": "X", "INFO": "~"}[c["status"]]
            print(f"  [{icon}] {c['name']}: {c['message']}")

    if regression_report:
        status = "PASS" if regression_report["passed"] else "FAIL"
        print(f"\n{'='*60}")
        print(f"Regression vs {regression_report['ref_version']}: {status}")
        print(f"{'='*60}")
        for c in regression_report["comparisons"]:
            icon = {"OK": "+", "SKIP": "-", "FAIL": "X"}[c["status"]]
            label = c.get("case", "")
            print(f"  [{icon}] {label}: {c['message']}")
