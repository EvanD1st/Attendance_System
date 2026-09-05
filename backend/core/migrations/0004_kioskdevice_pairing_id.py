from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0003_alter_managerscope_options")]

    # Existing displays must be paired again; old timestamp-bound QRs fail closed.
    operations = [
        migrations.AddField(
            model_name="kioskdevice",
            name="pairing_id",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
    ]
