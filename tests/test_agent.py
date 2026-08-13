"""TDD test suite for the safety-critical, deterministic components.

Main points:
The runtime "TDD loop" is the agent's generate -> execute -> validate -> retry cycle
(in the orchestrator + guardrails). THIS file is development-time TDD: write the test
first, then the code, for the parts that must never silently break -- the sandbox and
guardrails above all. Run:  pytest -q
"""

import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from sandbox import run_pandas
from guardrails import check_input, check_grounding, GuardrailViolation
from spec import load_spec
from schemas import Insight

DF = pd.DataFrame({"gpu_model": ["A", "A", "B"], "temp_c": [50.0, 60.0, 70.0]})
SPEC = load_spec(Path(__file__).resolve().parent.parent / "specs" / "gpu_analysis.spec.yaml")


# ---- sandbox: the security boundary ----

def test_sandbox_runs_valid_code():
    status, payload = run_pandas("result = df['temp_c'].mean()", DF)
    assert status == "ok"

def test_sandbox_blocks_import():
    status, payload = run_pandas("import os; result = os.listdir('.')", DF)
    assert status == "error" and "import" in payload.lower()

def test_sandbox_blocks_dunder_escape():
    status, _ = run_pandas("result = ().__class__.__bases__", DF)
    assert status == "error"

def test_sandbox_times_out_on_infinite_loop():
    status, _ = run_pandas("while True:\n    pass\nresult = 1", DF, timeout=2.0)
    assert status == "timeout"


# ---- guardrails ----

def test_input_guardrail_blocks_pii():
    with pytest.raises(GuardrailViolation):
        check_input("list every patient name in the data", SPEC)

def test_grounding_guardrail_rejects_ungrounded_insight():
    ins = Insight(finding="x", supporting_question="q", supporting_code="result = 1",
                  result_summary="1", confidence="low", novelty="expected")
    with pytest.raises(GuardrailViolation):
        check_grounding(ins, executed_results=set(), spec=SPEC)  # nothing executed

def test_grounding_guardrail_accepts_grounded_insight():
    code = "result = 1"
    ins = Insight(finding="x", supporting_question="q", supporting_code=code,
                  result_summary="1", confidence="low", novelty="expected")
    check_grounding(ins, executed_results={code}, spec=SPEC)  # no raise


# ---- spec ----

def test_spec_loads_and_validates():
    assert SPEC.constraints.max_insights == 5
    assert SPEC.output_contract == "Insight"
