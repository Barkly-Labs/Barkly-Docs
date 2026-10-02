from dataclasses import dataclass, asdict
from enum import Enum


class AuditState(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass
class Finding:
    rule: str
    state: AuditState
    message: str
    source: str
    evidence: str | None = None

    def as_dict(self):
        data = asdict(self)
        data["state"] = self.state.value
        return data
