"""Host-side L3 validation + plotting for batch results.

Pulls data from VM scheduler API, runs L2/L3 validation,
and generates standard LBIC comparison plots.
"""

import os
import sys
from pathlib import Path

# Add project root so imports work regardless of how script is invoked
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.utils.validation import validate_batch, regression_compare, print_report
from automation.client.batch_client import TCADSchedulerClient


def fetch_and_reshape(client: TCADSchedulerClient, batch_id: str) -> dict:
    """Pull results from API and reshape to {case: {bx_nm: current}}."""
    resp = client.get_results(batch_id)
    results = {}
    for r in resp.get("results", []):
        case = r["case_name"]
        bx = r["bx_nm"]
        current = r["photocurrent"]
        if current is None or current == 0.0:
            # Try to determine if this is a dark-current value
            if r.get("status") == "done":
                current = abs(current) if current else 0.0
        if case not in results:
            results[case] = {}
        results[case][bx] = current
    return results


def plot_batch(batch_id: str, client: TCADSchedulerClient | None = None,
               ref_version: str = "v4fix", output_dir: str | None = None) -> dict:
    """Full validation + plotting pipeline for a completed batch.

    Returns dict with batch_id, l2_report, l3_report, figures.
    """
    if client is None:
        client = TCADSchedulerClient()

    # 1. Fetch results
    data = fetch_and_reshape(client, batch_id)
    if not data:
        print(f"[WARN] No results found for batch '{batch_id}'")
        return {"batch_id": batch_id, "error": "no_results"}

    # 2. L2 Batch Validation
    l2 = validate_batch(data)

    # 3. L3 Regression
    l3 = regression_compare(data, ref_version=ref_version)

    # 4. Print report
    print_report(batch_report=l2, regression_report=l3)

    # 5. Generate plots
    figures = []
    figure_dir = output_dir or str(PROJECT_ROOT / "output" / "figures" / batch_id)
    os.makedirs(figure_dir, exist_ok=True)

    try:
        f1 = _plot_absolute(data, batch_id, figure_dir)
        figures.append(f1)
    except Exception as e:
        print(f"[WARN] Absolute plot failed: {e}")

    try:
        f2 = _plot_normalized(data, batch_id, figure_dir)
        figures.append(f2)
    except Exception as e:
        print(f"[WARN] Normalized plot failed: {e}")

    try:
        f3 = _plot_deviation(data, batch_id, figure_dir)
        figures.append(f3)
    except Exception as e:
        print(f"[WARN] Deviation plot failed: {e}")

    return {
        "batch_id": batch_id,
        "l2_report": l2,
        "l3_report": l3,
        "figures": figures,
    }


def _plot_absolute(data: dict, batch_id: str, out_dir: str) -> str:
    """Absolute photocurrent vs beam position, all cases overlaid."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab10(range(len(data)))
    for (case, values), color in zip(data.items(), colors):
        sorted_bx = sorted(values.keys())
        currents = [values[bx] for bx in sorted_bx]
        ax.plot(sorted_bx, currents, "o-", color=color, ms=4, label=case, linewidth=1)

    ax.set_xlabel("Beam Position X (nm)")
    ax.set_ylabel("Photocurrent (A)")
    ax.set_title(f"LBIC Scan — {batch_id}")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"{batch_id}_absolute.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  [+] {path}")
    return path


def _plot_normalized(data: dict, batch_id: str, out_dir: str) -> str:
    """Normalized photocurrent I/I_baseline vs beam position."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if "baseline" not in data:
        print("[WARN] No baseline case — skipping normalized plot")
        return ""

    base = data["baseline"]
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab10(range(len(data)))
    i = 0
    for case, values in data.items():
        if case == "baseline":
            i += 1
            continue
        sorted_bx = sorted(values.keys())
        ratios = []
        for bx in sorted_bx:
            if bx in base and base[bx] and abs(base[bx]) > 1e-15:
                ratios.append(values[bx] / base[bx])
            else:
                ratios.append(1.0)
        ax.plot(sorted_bx, ratios, "o-", color=colors[i % 10], ms=4, label=case, linewidth=1)
        i += 1

    ax.axhline(y=1.0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Beam Position X (nm)")
    ax.set_ylabel("I / I_baseline")
    ax.set_title(f"Normalized LBIC — {batch_id}")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"{batch_id}_normalized.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  [+] {path}")
    return path


def _plot_deviation(data: dict, batch_id: str, out_dir: str) -> str:
    """Deviation from baseline: (I - I_baseline) / I_baseline vs beam position."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if "baseline" not in data:
        print("[WARN] No baseline case — skipping deviation plot")
        return ""

    base = data["baseline"]
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.tab10(range(len(data)))
    i = 0
    for case, values in data.items():
        if case == "baseline":
            i += 1
            continue
        sorted_bx = sorted(values.keys())
        deviations = []
        for bx in sorted_bx:
            if bx in base and base[bx] and abs(base[bx]) > 1e-15:
                deviations.append((values[bx] - base[bx]) / base[bx] * 100)
            else:
                deviations.append(0.0)
        ax.plot(sorted_bx, deviations, "o-", color=colors[i % 10], ms=4, label=case, linewidth=1)
        i += 1

    ax.axhline(y=0.0, color="gray", linestyle="--", alpha=0.5)
    ax.set_xlabel("Beam Position X (nm)")
    ax.set_ylabel("Deviation from Baseline (%)")
    ax.set_title(f"TB Effect vs Beam Position — {batch_id}")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    path = os.path.join(out_dir, f"{batch_id}_deviation.png")
    fig.savefig(path, dpi=200)
    plt.close(fig)
    print(f"  [+] {path}")
    return path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Plot LBIC batch results from VM scheduler")
    parser.add_argument("batch_id", help="Batch ID to plot")
    parser.add_argument("--vm", default="YOUR_VM_IP", help="VM host")
    parser.add_argument("--port", type=int, default=8899, help="API port")
    parser.add_argument("--ref", default="v4fix", help="Reference version for L3 regression")
    parser.add_argument("--output", help="Output directory for figures")
    args = parser.parse_args()

    client = TCADSchedulerClient(vm_host=args.vm, port=args.port)
    result = plot_batch(args.batch_id, client=client, ref_version=args.ref,
                        output_dir=args.output)
    passed = (result.get("l2_report", {}).get("passed", False) and
              result.get("l3_report", {}).get("passed", False))
    print(f"\n{'='*50}")
    print(f"Validation: {'PASS' if passed else 'FAIL'}")
