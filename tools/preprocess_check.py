"""Compare OCR with and without plate preprocessing (C-04 evidence).

Uses the same sample folder as tools/model_check.py (crops/ and labels.csv).

Usage:
    python tools/preprocess_check.py <samples>
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_check import char_accuracy, imread, list_images, read_labels  # noqa: E402
from src.plate.judge import judge  # noqa: E402
from src.plate.ocr import recognize  # noqa: E402
from src.plate.preprocess import preprocess_plate  # noqa: E402

MODES = {
    "raw": lambda c: c,
    "gray+stretch": lambda c: preprocess_plate(c, deskew=False),
    "gray+stretch+deskew": lambda c: preprocess_plate(c),
    "binary (Otsu)": lambda c: preprocess_plate(c, binarize=True),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("samples", type=Path, help="sample folder with crops/ and labels.csv")
    args = ap.parse_args()

    crops = list_images(args.samples / "crops")
    labels = read_labels(args.samples / "labels.csv")
    recognize(imread(crops[0]))  # warm-up
    print(f"{'mode':<22} {'exact':>6} {'char_acc':>9} {'readable':>9} {'wrong readable':>15} {'uncertain':>10} {'unreadable':>11} {'ms':>5}")
    for name, prep in MODES.items():
        exact, accs, status, wrong, ms = 0, [], [], 0, []
        for path in crops:
            label = labels.get(path.name, "")
            t = time.perf_counter()
            text, conf = recognize(prep(imread(path)))
            ms.append((time.perf_counter() - t) * 1000)
            st, out = judge(text, conf)
            exact += text == label
            accs.append(char_accuracy(text, label))
            status.append(st)
            wrong += st == "readable" and out != label
        n = len(crops)
        print(f"{name:<22} {exact:>3}/{n:<2} {np.mean(accs):>9.2f} {status.count('readable'):>9} {wrong:>15} "
              f"{status.count('uncertain'):>10} {status.count('unreadable'):>11} {np.mean(ms):>5.0f}")


if __name__ == "__main__":
    main()
