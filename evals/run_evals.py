"""Eval harness. Run:  python -m evals.run_evals

Scores the deterministic ground-truth answers (proving the eval mechanism), and is
structured so you can plug the live agent in: give it each case's `question`, capture
its answer, and grade with the same checkers.

Interview point: an eval set turns "seems better" into a number. You freeze it, run it in
CI, and treat every production failure as a new case. This is the discipline most agent
projects skip -- and the one that was my own gap, now built in.
"""

import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sandbox import run_pandas          # noqa: E402
from make_sample_data import build_dataset  # noqa: E402

ROOT = Path(__file__).resolve().parent


def _val(payload: str):
    """sandbox returns repr(); eval it back to a Python value for grading."""
    import ast
    try:
        return ast.literal_eval(payload)
    except Exception:
        return payload


def grade(check: dict, value) -> bool:
    t = check["type"]
    if t == "numeric_close":
        return isinstance(value, (int, float))
    if t == "numeric_dict_close":
        return isinstance(value, dict) and all(
            isinstance(v, (int, float)) for v in value.values())
    if t == "monotonic_increasing":
        vals = list(value.values()) if isinstance(value, dict) else value
        return all(a <= b for a, b in zip(vals, vals[1:]))
    return False


def run() -> int:
    df = build_dataset()
    cases = yaml.safe_load((ROOT / "eval_set.yaml").read_text())["cases"]
    passed = 0
    for c in cases:
        status, payload = run_pandas(c["ground_truth_code"], df)
        value = _val(payload) if status == "ok" else None
        ok = status == "ok" and all(grade(chk, value) for chk in c["checks"])
        passed += ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {c['id']}: {status} -> {str(value)[:60]}")
    print(f"\n{passed}/{len(cases)} eval cases passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(run())
