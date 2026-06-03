from __future__ import annotations

import json
import random
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CronJob:
    id: str
    cron: str
    prompt: str
    recurring: bool
    durable: bool


def _field_matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return step > 0 and value % step == 0
    if "," in field:
        return any(_field_matches(part.strip(), value) for part in field.split(","))
    if "-" in field:
        lo, hi = field.split("-", 1)
        return int(lo) <= value <= int(hi)
    return value == int(field)


def cron_matches(cron_expr: str, dt: datetime) -> bool:
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    dow_val = (dt.weekday() + 1) % 7
    m = _field_matches(minute, dt.minute)
    h = _field_matches(hour, dt.hour)
    dom_ok = _field_matches(dom, dt.day)
    month_ok = _field_matches(month, dt.month)
    dow_ok = _field_matches(dow, dow_val)
    if not (m and h and month_ok):
        return False
    if dom == "*" and dow == "*":
        return True
    if dom == "*":
        return dow_ok
    if dow == "*":
        return dom_ok
    return dom_ok or dow_ok


def _validate_field(field: str, lo: int, hi: int) -> str | None:
    if field == "*":
        return None
    if field.startswith("*/"):
        step = field[2:]
        if not step.isdigit() or int(step) <= 0:
            return f"Invalid step: {field}"
        return None
    if "," in field:
        for part in field.split(","):
            err = _validate_field(part.strip(), lo, hi)
            if err:
                return err
        return None
    if "-" in field:
        left, right = field.split("-", 1)
        if not left.isdigit() or not right.isdigit():
            return f"Invalid range: {field}"
        a, b = int(left), int(right)
        if a < lo or a > hi or b < lo or b > hi:
            return f"Range {field} out of bounds [{lo}-{hi}]"
        if a > b:
            return f"Range start > end: {field}"
        return None
    if not field.isdigit():
        return f"Invalid field: {field}"
    value = int(field)
    if value < lo or value > hi:
        return f"Value {value} out of bounds [{lo}-{hi}]"
    return None


def validate_cron(cron_expr: str) -> str | None:
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        return f"Expected 5 fields, got {len(fields)}"
    bounds = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    names = ["minute", "hour", "day-of-month", "month", "day-of-week"]
    for field, (lo, hi), name in zip(fields, bounds, names):
        err = _validate_field(field, lo, hi)
        if err:
            return f"{name}: {err}"
    return None


class CronScheduler:
    def __init__(self, workdir: Path) -> None:
        self.durable_path = workdir / ".scheduled_tasks.json"
        self.jobs: dict[str, CronJob] = {}
        self.queue: list[CronJob] = []
        self.lock = threading.Lock()
        self.last_fired: dict[str, str] = {}
        self._started = False
        self.load_durable_jobs()

    def save_durable_jobs(self) -> None:
        durable = [asdict(job) for job in self.jobs.values() if job.durable]
        self.durable_path.write_text(json.dumps(durable, indent=2), encoding="utf-8")

    def load_durable_jobs(self) -> None:
        if not self.durable_path.exists():
            return
        try:
            for item in json.loads(self.durable_path.read_text(encoding="utf-8")):
                job = CronJob(**item)
                if not validate_cron(job.cron):
                    self.jobs[job.id] = job
        except Exception:
            pass

    def schedule(self, cron: str, prompt: str, recurring: bool = True, durable: bool = True) -> str:
        err = validate_cron(cron)
        if err:
            return f"Error: {err}"
        job = CronJob(
            id=f"cron_{random.randint(0, 999999):06d}",
            cron=cron,
            prompt=prompt,
            recurring=recurring,
            durable=durable,
        )
        with self.lock:
            self.jobs[job.id] = job
        if durable:
            self.save_durable_jobs()
        return f"Scheduled {job.id}: '{cron}' -> {prompt}"

    def cancel(self, job_id: str) -> str:
        with self.lock:
            job = self.jobs.pop(job_id, None)
        if not job:
            return f"Job {job_id} not found"
        if job.durable:
            self.save_durable_jobs()
        return f"Cancelled {job_id}"

    def list_jobs(self) -> str:
        with self.lock:
            jobs = list(self.jobs.values())
        if not jobs:
            return "No cron jobs."
        return "\n".join(
            f"  {job.id}: '{job.cron}' -> {job.prompt[:40]} "
            f"[{'recurring' if job.recurring else 'one-shot'}, {'durable' if job.durable else 'session'}]"
            for job in jobs
        )

    def loop(self) -> None:
        while True:
            time.sleep(1)
            now = datetime.now()
            marker = now.strftime("%Y-%m-%d %H:%M")
            with self.lock:
                jobs = list(self.jobs.values())
            for job in jobs:
                try:
                    if cron_matches(job.cron, now) and self.last_fired.get(job.id) != marker:
                        with self.lock:
                            self.queue.append(job)
                            self.last_fired[job.id] = marker
                            if not job.recurring:
                                self.jobs.pop(job.id, None)
                                if job.durable:
                                    self.save_durable_jobs()
                except Exception:
                    continue

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        threading.Thread(target=self.loop, daemon=True).start()

    def consume(self) -> list[CronJob]:
        with self.lock:
            fired = list(self.queue)
            self.queue.clear()
        return fired
