from django.db import transaction
from django.utils import timezone

from desk.models import LimitChange, OffsetSubmission, ToleranceLimit


def current_limit_um() -> int:
    return ToleranceLimit.load().limit_um


def evaluate_verdict(offset_um: int, limit_um: int) -> str:
    """绝对值不大于上限写合格，超过写超差。"""
    if abs(offset_um) <= limit_um:
        return OffsetSubmission.Verdict.PASS
    return OffsetSubmission.Verdict.FAIL


@transaction.atomic
def change_limit(user, new_limit_um: int):
    """操作员改上限：锁单行写入新值并追加改档痕迹；新旧相同则不留痕。

    返回 (上限单例, 痕迹或 None)。
    """
    limit = ToleranceLimit.objects.select_for_update().get(
        pk=ToleranceLimit.SINGLETON_ID,
    )
    old_limit_um = limit.limit_um
    if new_limit_um == old_limit_um:
        return limit, None
    limit.limit_um = new_limit_um
    limit.updated_by = user
    limit.save(update_fields=["limit_um", "updated_by", "updated_at"])
    change = LimitChange.objects.create(
        old_limit_um=old_limit_um,
        new_limit_um=new_limit_um,
        changed_by=user,
    )
    return limit, change


def apply_verdict(submission: OffsetSubmission) -> None:
    # 已进复核中的单继续用领取当时记下的上限。
    limit_um = submission.claimed_limit_um
    if limit_um is None:
        limit_um = current_limit_um()
    submission.verdict = evaluate_verdict(submission.offset_um, limit_um)
    submission.status = OffsetSubmission.Status.DONE
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=["verdict", "status", "reviewed_at"],
    )
