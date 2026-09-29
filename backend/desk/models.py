from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        MACHINIST = "machinist", "操作员"
        AUDITOR = "auditor", "复核员"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MACHINIST,
    )

    @property
    def can_write(self) -> bool:
        return self.role == self.Role.MACHINIST


class ToleranceLimit(models.Model):
    """合格上限（微米）单例：pk 恒为 1，绝对值不大于该值判合格。"""

    SINGLETON_ID = 1
    DEFAULT_UM = 12

    limit_um = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "合格上限"
        verbose_name_plural = "合格上限"

    @classmethod
    def get(cls) -> "ToleranceLimit":
        obj, _ = cls.objects.get_or_create(
            pk=cls.SINGLETON_ID,
            defaults={"limit_um": cls.DEFAULT_UM},
        )
        return obj

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"上限 {self.limit_um}µm"


class LimitChange(models.Model):
    """上限改档痕迹：谁在何时把上限从多少改成多少。"""

    old_limit_um = models.IntegerField()
    new_limit_um = models.IntegerField()
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="limit_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-changed_at", "-id"]

    def __str__(self) -> str:
        return f"{self.old_limit_um}→{self.new_limit_um}µm"


class OffsetSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待复核"
        PROCESSING = "processing", "复核中"
        DONE = "done", "已完成"

    class Verdict(models.TextChoices):
        PASS = "合格", "合格"
        FAIL = "超差", "超差"

    tool_code = models.CharField(max_length=32, db_index=True)
    offset_um = models.IntegerField()
    # 认领（转复核中）瞬间记下的当时上限；待复核为 NULL，表示继续吃最新上限。
    limit_um = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    verdict = models.CharField(
        max_length=8,
        choices=Verdict.choices,
        blank=True,
        default="",
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.tool_code} {self.offset_um}µm"
