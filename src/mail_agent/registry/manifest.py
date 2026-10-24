"""에이전트 Manifest 로더·검증. agents/<name>/manifest.yaml + agent.py(AGENT_CLASS) 를 발견해 등록한다."""
import importlib
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from mail_agent.schemas import ARTIFACT_SCHEMAS

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
_COND = re.compile(r"^([A-Za-z_][\w]*(?:\.[\w]+)*)\s*(==|!=)\s*'([^']*)'$")


class Limits(BaseModel):
    max_steps: int = 3
    max_tokens: int = 4000
    timeout_s: int = 30


class EvalSpec(BaseModel):
    dataset: str = "-"
    evaluators: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    name: str
    team: str
    description: str
    order: int = 100                                 # 같은 조건일 때 실행 우선순위(낮을수록 먼저)
    requires: list[str] = Field(default_factory=list)  # 필요한 artifact
    produces: list[str]                              # 생성하는 artifact
    when: str | None = None                          # 실행 조건. 예: "classification.label == 'reply_needed'"
    model_tier: Literal["none", "light", "standard", "strong"] = "none"
    capabilities: list[str] = Field(default_factory=list)
    risk_tier: Literal["low", "medium", "high"] = "low"
    limits: Limits = Field(default_factory=Limits)
    eval: EvalSpec = Field(default_factory=EvalSpec)
    enabled: bool = True

    @model_validator(mode="after")
    def _check(self):
        for a in [*self.requires, *self.produces]:
            if a not in ARTIFACT_SCHEMAS:
                raise ValueError(f"{self.name}: 알 수 없는 artifact '{a}' (schemas.ARTIFACT_SCHEMAS 에 등록 필요)")
        if self.when and not _COND.match(self.when):
            raise ValueError(f"{self.name}: 지원하지 않는 when 식: {self.when!r}")
        return self

    def condition_ok(self, artifacts: dict[str, Any]) -> bool:
        if not self.when:
            return True
        path, op, lit = _COND.match(self.when).groups()  # type: ignore[union-attr]
        head, *rest = path.split(".")
        val: Any = artifacts.get(head)
        for k in rest:
            val = val.get(k) if isinstance(val, dict) else getattr(val, k, None)
        return (str(val) == lit) if op == "==" else (str(val) != lit)


class Registry:
    def __init__(self) -> None:
        self.manifests: dict[str, Manifest] = {}
        self.classes: dict[str, type] = {}

    def register(self, m: Manifest, cls: type) -> None:
        if m.name in self.manifests:
            raise ValueError(f"중복 에이전트: {m.name}")
        self.manifests[m.name] = m
        self.classes[m.name] = cls

    @classmethod
    def discover(cls, agents_dir: Path = AGENTS_DIR) -> "Registry":
        reg = cls()
        for mf in sorted(agents_dir.glob("*/manifest.yaml")):
            m = Manifest.model_validate(yaml.safe_load(mf.read_text()))
            if mf.parent.name != m.name:
                raise ValueError(f"디렉토리명과 manifest.name 불일치: {mf.parent.name} / {m.name}")
            if not m.enabled:
                continue
            mod = importlib.import_module(f"mail_agent.agents.{m.name}.agent")
            reg.register(m, mod.AGENT_CLASS)
        return reg

    def candidates(self, artifacts: dict[str, Any]) -> list[Manifest]:
        """아직 산출물이 없고 입력이 준비되며 조건을 만족하는 에이전트를 우선순위 순으로 반환."""
        out = [
            m for m in self.manifests.values()
            if all(r in artifacts for r in m.requires)
            and not any(p in artifacts for p in m.produces)
            and m.condition_ok(artifacts)
        ]
        return sorted(out, key=lambda m: (m.order, m.name))
