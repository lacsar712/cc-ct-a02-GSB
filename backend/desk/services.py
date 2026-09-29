from django.db import transaction
from django.utils import timezone

from desk.models import LimitChange, OffsetSubmission, ToleranceLimit, User


def current_limit_um() -> int:
    return ToleranceLimit.get().limit_um


def evaluate_verdict(offset_um: int, limit_um: int) -> str:
    if abs(offset_um) <= limit_um:
        return OffsetSubmission.Verdict.PASS
    return OffsetSubmission.Verdict.FAIL


def change_limit(user: User, new_limit_um: int) -> tuple[ToleranceLimit, LimitChange | None]:
    """操作员改档：锁住现行上限后改写，并留一条改档痕迹。

    与改档并发的 worker 认领事务会被行锁串行化，保证认领吃到的
    要么是改档前、要么是改档后的确定值。
    """
    if new_limit_um < 0:
        raise ValueError("上限不能为负数")
    with transaction.atomic():
        limit = (
            ToleranceLimit.objects.select_for_update()
            .get(pk=ToleranceLimit.SINGLETON_ID)
        )
        old_limit_um = limit.limit_um
        if old_limit_um == new_limit_um:
            return limit, None
        limit.limit_um = new_limit_um
        limit.save(update_fields=["limit_um", "updated_at"])
        record = LimitChange.objects.create(
            old_limit_um=old_limit_um,
            new_limit_um=new_limit_um,
            changed_by=user,
        )
    return limit, record


def apply_verdict(submission: OffsetSubmission) -> None:
    # 正常路径下限额已在认领时盖入 limit_um；这里兜底读最新上限。
    limit_um = (
        submission.limit_um
        if submission.limit_um is not None
        else current_limit_um()
    )
    submission.verdict = evaluate_verdict(submission.offset_um, limit_um)
    submission.status = OffsetSubmission.Status.DONE
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=["verdict", "status", "reviewed_at"],
    )
