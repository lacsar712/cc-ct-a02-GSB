"""Background worker: claim pending rows with SKIP LOCKED and apply verdict."""

import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import django


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def claim_one_pending():
    from django.db import transaction

    from desk.models import OffsetSubmission, ToleranceLimit
    from desk.services import apply_verdict

    with transaction.atomic():
        submission = (
            OffsetSubmission.objects.select_for_update(skip_locked=True)
            .filter(status=OffsetSubmission.Status.PENDING)
            .order_by("created_at", "id")
            .first()
        )
        if submission is None:
            return False

        # 认领瞬间记下当时上限；此后即使上限改档，本单仍按该快照判定。
        # 锁上限行：改档进行中时在此等待其提交，必读到确定的现行值；
        # 本事务先持锁时，改档会等认领提交后再生效，彼时本单已进复核中。
        limit = (
            ToleranceLimit.objects.select_for_update()
            .get(pk=ToleranceLimit.SINGLETON_ID)
        )
        submission.limit_um = limit.limit_um
        submission.status = OffsetSubmission.Status.PROCESSING
        submission.save(update_fields=["limit_um", "status"])

    apply_verdict(submission)
    return True


def run_loop(poll_seconds: float = 0.5) -> None:
    setup_django()
    print("cnc-offset worker started", flush=True)
    while True:
        claimed = claim_one_pending()
        if not claimed:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    setup_django()
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        claim_one_pending()
    else:
        run_loop()
