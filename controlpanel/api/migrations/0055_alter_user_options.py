# Generated by Django 5.1.2 on 2025-01-07 14:21

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0054_alter_tool_description"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={
                "ordering": ("username",),
                "permissions": [
                    (
                        "quicksight_embed_author_access",
                        "Can access the embedded Quicksight as an author",
                    ),
                    (
                        "quicksight_embed_reader_access",
                        "Can access the embedded Quicksight as a reader",
                    ),
                ],
            },
        ),
    ]
