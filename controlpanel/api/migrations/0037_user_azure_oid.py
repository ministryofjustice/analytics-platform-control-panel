# Generated by Django 5.0.4 on 2024-04-10 09:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0036_user_justice_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="azure_oid",
            field=models.CharField(blank=True, null=True, unique=True),
        ),
    ]