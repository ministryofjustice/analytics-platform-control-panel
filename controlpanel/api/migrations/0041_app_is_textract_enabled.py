# Generated by Django 5.0.4 on 2024-10-02 08:39

# Third-party
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0040_alter_s3bucket_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="app",
            name="is_textract_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
