"""G3: TemporalMemory thread safety and snapshot delete semantics."""
import threading
from datetime import datetime, timezone, timedelta

from evolver.temporal_memory import TemporalMemory


def test_remove_expired_snapshots_before_deleting():
    tm = TemporalMemory()
    old = datetime.now(timezone.utc) - timedelta(days=400)
    tm.register(1, last_accessed=old, decay_rate=0.5)
    tm.register(2)  # fresh entry, far from expiry
    assert tm.remove_expired() == 1
    assert tm.get(1) is None
    assert tm.get(2) is not None


def test_temporal_memory_survives_concurrent_mutation():
    tm = TemporalMemory()
    old = datetime.now(timezone.utc) - timedelta(days=400)
    tm.register(0, last_accessed=old, decay_rate=0.5)  # always expired
    errors = []

    def worker(base):
        try:
            for i in range(200):
                mid = base + i
                tm.register(mid)
                tm.touch(mid)
                tm.get(mid)
                if i % 3 == 0:
                    # Concurrent with other threads' register/touch: the
                    # snapshot delete must never raise or eat live entries.
                    tm.remove_expired()
                tm.get_stats()
                tm.remove(base + i - 1)
        except Exception as e:  # noqa: BLE001 - test records any failure
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n * 100_000,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    stats = tm.get_stats()
    assert stats["total"] == len(tm._entries)
    assert stats["total"] > 0
    # The permanently-expired entry is gone; nothing it deleted by mistake.
    assert tm.get(0) is None
