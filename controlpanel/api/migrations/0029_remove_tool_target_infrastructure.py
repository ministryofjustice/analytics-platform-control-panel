# Generated by Django 4.1.4 on 2023-06-15 20:48

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0028_alter_s3bucket_name"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tool",
            name="target_infrastructure",
        ),
    ]
