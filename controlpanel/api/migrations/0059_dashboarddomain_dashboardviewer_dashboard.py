# Generated by Django 5.1.4 on 2025-03-25 09:00

import django.db.models.deletion
import django_extensions.db.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0058_add_initial_justice_domains"),
    ]

    operations = [
        migrations.CreateModel(
            name="DashboardDomain",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
            ],
            options={
                "db_table": "control_panel_api_dashboard_domain",
            },
        ),
        migrations.CreateModel(
            name="DashboardViewer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("email", models.EmailField(max_length=254, unique=True)),
            ],
            options={
                "db_table": "control_panel_api_dashboard_viewer",
            },
        ),
        migrations.CreateModel(
            name="Dashboard",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("quicksight_id", models.CharField(max_length=100, unique=True)),
                (
                    "admins",
                    models.ManyToManyField(related_name="dashboards", to=settings.AUTH_USER_MODEL),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "whitelist_domains",
                    models.ManyToManyField(related_name="dashboards", to="api.dashboarddomain"),
                ),
                (
                    "viewers",
                    models.ManyToManyField(related_name="dashboards", to="api.dashboardviewer"),
                ),
            ],
            options={
                "db_table": "control_panel_api_dashboard",
            },
        ),
    ]
