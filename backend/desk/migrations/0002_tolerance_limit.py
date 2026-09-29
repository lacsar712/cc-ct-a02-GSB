import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def init_limit_and_backfill(apps, schema_editor):
    ToleranceLimit = apps.get_model("desk", "ToleranceLimit")
    OffsetSubmission = apps.get_model("desk", "OffsetSubmission")
    ToleranceLimit.objects.create(pk=1, limit_um=12)
    # 历史记录均按 12µm 判定，回填快照以保持结论一致。
    OffsetSubmission.objects.filter(limit_um__isnull=True).update(limit_um=12)


def remove_limit(apps, schema_editor):
    ToleranceLimit = apps.get_model("desk", "ToleranceLimit")
    ToleranceLimit.objects.filter(pk=ToleranceLimit.SINGLETON_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("desk", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ToleranceLimit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("limit_um", models.IntegerField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "合格上限",
                "verbose_name_plural": "合格上限",
            },
        ),
        migrations.CreateModel(
            name="LimitChange",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("old_limit_um", models.IntegerField()),
                ("new_limit_um", models.IntegerField()),
                ("changed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="limit_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-changed_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="offsetsubmission",
            name="limit_um",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(init_limit_and_backfill, remove_limit),
    ]
