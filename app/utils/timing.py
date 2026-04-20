import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class StageTimings:
    stages: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.perf_counter)

    @contextmanager
    def measure(self, stage: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.stages[stage] = round(time.perf_counter() - start, 4)

    @property
    def total(self) -> float:
        return round(time.perf_counter() - self.started_at, 4)
