# Generated by Django 2.1.7 on 2019-03-27 14:20

# Third-party
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_s3bucket_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="last_name",
            field=models.CharField(
                blank=True, max_length=150, verbose_name="last name"
            ),
        ),
    ]