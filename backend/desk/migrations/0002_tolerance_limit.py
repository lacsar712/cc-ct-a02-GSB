from django.db import migrations, models
import django.db.models.deletion


def seed_limit(apps, schema_editor):
    ToleranceLimit = apps.get_model("desk", "ToleranceLimit")
    ToleranceLimit.objects.get_or_create(pk=1, defaults={"limit_um": 12})


def remove_limit(apps, schema_editor):
    ToleranceLimit = apps.get_model("desk", "ToleranceLimit")
    ToleranceLimit.objects.filter(pk=1).delete()


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
                ("limit_um", models.IntegerField(default=12)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="limit_updates",
                        to="desk.user",
                    ),
                ),
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
                        to="desk.user",
                    ),
                ),
            ],
            options={
                "ordering": ["-changed_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="offsetsubmission",
            name="claimed_limit_um",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(seed_limit, remove_limit),
    ]
