"""OCR evaluation against plate labels (C-09).

Plate label format (proposed until the team label schema is fixed): a JSON
object mapping each frame file name to its plates. A folder of such files is
merged. text null means the plate is not readable by eye.

    {"fog_01_3500.png": [{"bbox": [x, y, w, h], "text": "12가3456"},
                         {"bbox": [x, y, w, h], "text": null}],
     "fog_01_7000.png": []}

Usage:
    python -m src.eval.ocr [--labels data/labels] [--results results]
"""

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONDITIONS = ("orig", "fixed", "adaptive")
IOU_MATCH = 0.5
OCR_METRICS = ["detection_rate", "exact_match", "char_accuracy", "overconfident"]
SUMMARY_FIELDS = ["condition", "frames", "plates", "unreadable_labels", *OCR_METRICS, "readable_wrong", "missing_frames"]


def iou(a, b):  # (x, y, w, h)
    ix = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def edit_distance(a, b):  # Levenshtein
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[len(b)]


def char_accuracy(pred, label):
    return max(0.0, 1 - edit_distance(pred or "", label) / len(label))


def frame_key(name):
    return Path(str(name)).stem  # "x.png" and "x" are the same frame


def load_labels(labels):
    """dict, JSON file or folder of JSON files -> {frame: [{"bbox", "text"}]}; text None if unreadable."""
    if isinstance(labels, dict):
        data = labels
    else:
        path = Path(labels)
        data = {}
        for f in sorted(path.glob("*.json")) if path.is_dir() else [path]:
            data.update(json.loads(f.read_text(encoding="utf-8")))
    out = {}
    for frame, plates in data.items():
        out[frame_key(frame)] = [{"bbox": tuple(int(v) for v in p["bbox"]),
                                  "text": p.get("text") if p.get("text") not in ("", "unreadable") else None}
                                 for p in plates]
    return out


def load_results(results):
    """<cond>.csv path or its rows -> {frame: [{"bbox", "text", "status"}]}; frames without plates map to []."""
    rows = results
    if isinstance(results, (str, Path)):
        with open(results, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    out = {}
    for r in rows:
        plates = out.setdefault(frame_key(r["frame"]), [])
        if r.get("status"):
            plates.append({"bbox": (int(r["x"]), int(r["y"]), int(r["w"]), int(r["h"])),
                           "text": r.get("text") or None, "status": r["status"]})
    return out


def match_frame(preds, labels):
    """One-to-one matching with IoU >= IOU_MATCH, highest IoU first. Returns {label index: pred}."""
    pairs = sorted(((iou(p["bbox"], lab["bbox"]), -i, -j) for j, p in enumerate(preds) for i, lab in enumerate(labels)),
                   reverse=True)
    used_p, matched = set(), {}
    for v, i, j in pairs:
        i, j = -i, -j
        if v < IOU_MATCH:
            break
        if i not in matched and j not in used_p:
            matched[i] = preds[j]
            used_p.add(j)
    return matched


def score(results, labels):
    """Returns (summary dict, {frame: mean char accuracy of its readable labels, or None})."""
    preds, gold = load_results(results), load_labels(labels)
    plates = detected = exact = unreadable = overconfident = readable_wrong = missing = 0
    accs, frames = [], {}
    for frame, labs in gold.items():
        missing += frame not in preds
        matched = match_frame(preds.get(frame, []), labs)
        frame_accs = []
        for i, lab in enumerate(labs):
            p = matched.get(i)
            if lab["text"] is None:  # not readable by eye: only check for confident answers
                unreadable += 1
                overconfident += p is not None and p["status"] == "readable"
                continue
            plates += 1
            detected += p is not None
            exact += p is not None and p["text"] == lab["text"]
            readable_wrong += p is not None and p["status"] == "readable" and p["text"] != lab["text"]
            frame_accs.append(char_accuracy(p["text"], lab["text"]) if p else 0.0)
        accs += frame_accs
        frames[frame] = sum(frame_accs) / len(frame_accs) if frame_accs else None
    summary = {
        "frames": len(gold),
        "plates": plates,
        "unreadable_labels": unreadable,
        "detection_rate": detected / plates if plates else None,
        "exact_match": exact / plates if plates else None,
        "char_accuracy": sum(accs) / plates if plates else None,
        "overconfident": overconfident,
        "readable_wrong": readable_wrong,
        "missing_frames": missing,
    }
    return summary, frames


def eval_ocr(results, labels) -> dict:
    """Score one condition's OCR results.

    Args:
        results: path to results/ocr/<cond>.csv, or its rows as dicts.
        labels: dict, JSON file or folder in the plate label format above.

    Returns:
        {"frames", "plates", "unreadable_labels", "detection_rate", "exact_match",
         "char_accuracy", "overconfident", "readable_wrong", "missing_frames"}.
        Rates are None when there is no readable labeled plate.
        Labels with text None are left out of the three rates; "overconfident"
        counts those that were read as readable.
    """
    return score(results, labels)[0]


def frame_char_accuracy(results, labels) -> dict:
    """{frame: mean char accuracy of its readable labeled plates, or None if it has none}."""
    return score(results, labels)[1]


def write_summary(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: round(v, 4) if isinstance(v, float) else ("" if v is None else v) for k, v in r.items()})
    return path


def main():
    ap = argparse.ArgumentParser(description="Score results/ocr/<cond>.csv against plate labels.")
    ap.add_argument("--labels", type=Path, default=ROOT / "data" / "labels")
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    args = ap.parse_args()
    rows = []
    for cond in CONDITIONS:
        path = args.results / "ocr" / f"{cond}.csv"
        if path.exists():
            rows.append({"condition": cond, **eval_ocr(path, args.labels)})
    if not rows:
        raise SystemExit(f"no {args.results / 'ocr'}/<cond>.csv found")
    out = write_summary(rows, args.results / "ocr" / "ocr_summary.csv")
    print(out)
    for r in rows:
        print({k: round(v, 4) if isinstance(v, float) else v for k, v in r.items()})


if __name__ == "__main__":
    main()
