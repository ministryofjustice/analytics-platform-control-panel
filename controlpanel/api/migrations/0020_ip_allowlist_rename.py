# Generated by Django 3.2.15 on 2022-09-22 17:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0019_historicalipallowlist_ipallowlist_validation'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='ipallowlist',
            options={'ordering': ('name',)},
        ),
        migrations.AlterModelTable(
            name='historicalipallowlist',
            table='control_panel_api_ip_allowlist_history',
        ),
        migrations.AlterModelTable(
            name='ipallowlist',
            table='control_panel_api_ip_allowlist',
        ),
    ]