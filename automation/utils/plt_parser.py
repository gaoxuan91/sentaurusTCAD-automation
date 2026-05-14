import re


def _parse_datasets(content):
    match = re.search(r'datasets\s*=\s*\[(.*?)\]', content, re.DOTALL)
    if not match:
        return []
    raw = match.group(1)
    return re.findall(r'"([^"]+)"', raw)


def _parse_data_block(content):
    match = re.search(r'Data\s*\{(.*)\}', content, re.DOTALL)
    if not match:
        return []
    values = []
    for token in match.group(1).split():
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values


def parse_plt(content):
    datasets = _parse_datasets(content)
    values = _parse_data_block(content)
    n_cols = len(datasets)
    if n_cols == 0 or len(values) == 0:
        return {"datasets": datasets, "n_cols": 0, "n_rows": 0, "rows": []}
    n_rows = len(values) // n_cols
    rows = []
    for i in range(n_rows):
        rows.append(values[i * n_cols:(i + 1) * n_cols])
    return {"datasets": datasets, "n_cols": n_cols, "n_rows": n_rows, "rows": rows}


def extract_photocurrent(content, electrode="Anode", quantity="TotalCurrent"):
    datasets = _parse_datasets(content)
    target = f"{electrode} {quantity}"
    try:
        col_idx = datasets.index(target)
    except ValueError:
        return None
    values = _parse_data_block(content)
    n_cols = len(datasets)
    if n_cols == 0 or len(values) < n_cols:
        return None
    n_rows = len(values) // n_cols
    last_row_start = (n_rows - 1) * n_cols
    return values[last_row_start + col_idx]


def extract_all_currents(content):
    datasets = _parse_datasets(content)
    values = _parse_data_block(content)
    n_cols = len(datasets)
    if n_cols == 0 or len(values) < n_cols:
        return {}
    n_rows = len(values) // n_cols
    last_row_start = (n_rows - 1) * n_cols
    result = {}
    for i, name in enumerate(datasets):
        if "TotalCurrent" in name:
            result[name] = values[last_row_start + i]
    return result


def extract_photocurrent_from_file(filepath, electrode="Anode", quantity="TotalCurrent"):
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return extract_photocurrent(content, electrode, quantity)


# ---------------------------------------------------------------------------
# Layer 1: Single-point sanity check
# ---------------------------------------------------------------------------

DARK_CURRENT_THRESHOLD = 1e-15

def sanity_check(content, label="", dark_threshold=DARK_CURRENT_THRESHOLD):
    current = extract_photocurrent(content)
    if current is None:
        return {"status": "ERROR", "label": label, "current": None,
                "message": "Failed to parse Anode TotalCurrent"}
    abs_current = abs(current)
    if abs_current < dark_threshold:
        return {"status": "WARN", "label": label, "current": abs_current,
                "message": f"Current {abs_current:.2e} A <= dark threshold {dark_threshold:.0e}"}
    return {"status": "OK", "label": label, "current": abs_current, "message": ""}


def sanity_check_file(filepath, label="", dark_threshold=DARK_CURRENT_THRESHOLD):
    if label == "":
        label = filepath
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except FileNotFoundError:
        return {"status": "ERROR", "label": label, "current": None,
                "message": f"File not found: {filepath}"}
    return sanity_check(content, label, dark_threshold)
