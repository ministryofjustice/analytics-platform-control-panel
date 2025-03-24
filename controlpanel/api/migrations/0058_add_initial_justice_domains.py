# Generated by Django 5.1.4 on 2025-03-21 09:44

from django.db import migrations


def forwards(apps, schema_editor):
    JusticeDomain = apps.get_model("api", "JusticeDomain")
    JusticeDomain.objects.bulk_create(
        [
            JusticeDomain(domain="justice.gov.uk"),
            JusticeDomain(domain="cica.gov.uk"),
            JusticeDomain(domain="publicguardian.gov.uk"),
        ]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0057_justicedomain"),
    ]

    operations = [migrations.RunPython(code=forwards, reverse_code=migrations.RunPython.noop)]
