# Generated by Django 5.1.2 on 2024-12-11 14:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0053_alter_tool_image_tag"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tool",
            name="description",
            field=models.TextField(),
        ),
    ]
