from __future__ import annotations

import gzip
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True)
class RawRecord:
    url: str
    status_code: int
    fetched_at: str
    html: str


class RawStore:
    """Append-only, gzipped raw HTML archive: one file per collection date.

    Each `append()` call writes a new gzip member holding one JSON line, so a run
    can be interrupted and restarted without corrupting the file or losing earlier
    pages. `fetched_urls`/`read` let a resumed run and future re-parses see exactly
    what was on the wire that day, without re-fetching anything.
    """

    def __init__(self, raw_dir: Path) -> None:
        self._raw_dir = raw_dir
        self._raw_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_date: date) -> Path:
        return self._raw_dir / f"{run_date.isoformat()}.jsonl.gz"

    def fetched_urls(self, run_date: date) -> set[str]:
        return {record.url for record in self.read(run_date)}

    def append(self, run_date: date, url: str, status_code: int, html: str) -> None:
        record = {
            "url": url,
            "status_code": status_code,
            "fetched_at": datetime.now(UTC).isoformat(),
            "html": html,
        }
        line = (json.dumps(record) + "\n").encode("utf-8")
        with gzip.open(self.path_for(run_date), "ab") as fh:
            fh.write(line)

    def read(self, run_date: date) -> Iterator[RawRecord]:
        path = self.path_for(run_date)
        if not path.exists():
            return
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                yield RawRecord(**json.loads(line))
