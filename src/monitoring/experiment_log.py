"""Records thesis-evaluation trials and exports them, without ever touching
raw audio or video (only derived fields). Participant tracking is off by
default - the caller supplies an identifier only if they choose to."""
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class Trial:
    expected_command: str
    recognized_command: Optional[str]
    correct: bool
    modality: str
    language: str
    confidence: float
    latency_ms: float
    noise_condition: str = ""
    lighting_condition: str = ""
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExperimentLog:
    def __init__(self, experiment_name: str = "", session_id: str = ""):
        self.experiment_name = experiment_name
        self.session_id = session_id
        self._trials: List[Trial] = []

    def add_trial(self, trial: Trial) -> None:
        self._trials.append(trial)

    @property
    def trials(self) -> List[Trial]:
        return list(self._trials)

    def accuracy(self) -> Optional[float]:
        if not self._trials:
            return None
        return sum(1 for t in self._trials if t.correct) / len(self._trials)

    def export_csv(self, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(Trial("", None, False, "", "", 0, 0)).keys()))
            writer.writeheader()
            for trial in self._trials:
                writer.writerow(asdict(trial))

    def export_json(self, path: str) -> None:
        payload = {
            "experiment_name": self.experiment_name,
            "session_id": self.session_id,
            "accuracy": self.accuracy(),
            "trials": [asdict(t) for t in self._trials],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
