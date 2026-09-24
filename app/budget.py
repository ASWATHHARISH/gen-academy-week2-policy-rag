"""Persistent, cross-process attempt reservations with a hard free-demo cap."""
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import time

from app.config import Settings


class BudgetError(RuntimeError):
    pass


@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        acquired = False
        deadline = time.monotonic() + 30
        while not acquired:
            lock.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    raise BudgetError("api_budget_lock_timeout") from None
                time.sleep(0.1)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def reserve_attempt(settings: Settings) -> int:
    """Consume one attempt BEFORE a request; failed requests also consume attempts.

    The ledger never automatically resets or refunds. A missing ledger means the
    first run; malformed existing state fails closed.
    """
    path = settings.api_budget_path
    cap = min(30, max(0, int(settings.max_api_attempts)))
    interval = max(5.0, float(settings.api_min_interval_seconds))
    if not math.isfinite(interval) or interval > 60:
        raise BudgetError("invalid_api_interval")
    with _locked(path.with_suffix(path.suffix + ".lock")):
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
                count = state["attempts"]
                last = float(state["last_attempt_at"])
                if type(count) is not int or count < 0 or not math.isfinite(last):
                    raise ValueError
            except (OSError, ValueError, KeyError, TypeError):
                raise BudgetError("api_budget_invalid") from None
        else:
            count, last = 0, 0.0
        if count >= cap:
            raise BudgetError("api_budget_exhausted")
        remaining = interval - (time.time() - last)
        if remaining > 60:
            raise BudgetError("api_budget_clock_changed")
        if remaining > 0:
            time.sleep(remaining)
        record = {"attempts": count + 1, "limit": cap, "last_attempt_at": time.time()}
        # A unique temporary file and atomic replace avoid partial JSON state.
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as out:
                json.dump(record, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, path)
        except OSError:
            raise BudgetError("api_budget_write_failed") from None
        return count + 1

