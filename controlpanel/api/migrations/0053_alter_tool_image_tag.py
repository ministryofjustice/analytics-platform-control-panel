# Generated by Django 5.1.2 on 2024-12-10 09:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0052_add_image_tag_value"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tool",
            name="image_tag",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
    ]
