"""Load and VALIDATE the spec. A spec you don't validate is just a hopeful comment.

Main point: the spec is the single source of truth for the run. Loading it through
a Pydantic model means an invalid or drifted spec fails loudly at startup, not halfway
through a run after you've spent tokens.
"""

from pathlib import Path
import yaml
from pydantic import BaseModel, Field


class Constraints(BaseModel):
    max_insights: int = 5
    max_tool_calls_per_goal: int = 6
    temperature_planning: float = 0.7
    temperature_grounding: float = 0.0
    pii_allowed: bool = False
    require_grounding: bool = True


class Dataset(BaseModel):
    source: str
    primary_keys: list[str]
    known_metrics: list[str]


class HumanInTheLoop(BaseModel):
    approve_before_report: bool = True


class Spec(BaseModel):
    version: int
    name: str
    goal: str
    dataset: Dataset
    constraints: Constraints = Field(default_factory=Constraints)
    acceptance_criteria: list[str]
    output_contract: str
    human_in_the_loop: HumanInTheLoop = Field(default_factory=HumanInTheLoop)


def load_spec(path: str | Path) -> Spec:
    raw = yaml.safe_load(Path(path).read_text())
    return Spec(**raw)   # raises ValidationError on a malformed spec
