# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-10-17 15:34
# Future
from __future__ import unicode_literals

# Third-party
import django.contrib.auth.models
import django.contrib.auth.validators
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import django_extensions.db.fields
from django.conf import settings
from django.db import migrations, models

# First-party/Local
import controlpanel.api.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0008_alter_user_username_max_length"),
    ]

    replaces = [("control_panel_api", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",  # noqa: E501
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",  # noqa: E501
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",  # noqa: E501
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",  # noqa: E501
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "auth0_id",
                    models.CharField(max_length=128, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(blank=True, max_length=256)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",  # noqa: E501
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.Group",
                        verbose_name="groups",
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_user",
                "ordering": ("username",),
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="App",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("name", models.CharField(max_length=100)),
                (
                    "slug",
                    django_extensions.db.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="_repo_name"
                    ),
                ),
                ("repo_url", models.URLField(max_length=512, unique=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_app",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="AppS3Bucket",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                (
                    "access_level",
                    models.CharField(
                        choices=[
                            ("readonly", "Read-only"),
                            ("readwrite", "Read-write"),
                        ],
                        default="readonly",
                        max_length=9,
                    ),
                ),
                (
                    "app",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="apps3buckets",
                        to="api.App",
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_apps3bucket",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="Role",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("name", models.CharField(max_length=256, unique=True)),
                ("code", models.CharField(max_length=256, unique=True)),
            ],
            options={
                "db_table": "control_panel_api_role",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="S3Bucket",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                (
                    "name",
                    models.CharField(
                        max_length=63,
                        unique=True,
                        validators=[
                            controlpanel.api.validators.validate_env_prefix,
                            django.core.validators.RegexValidator(
                                message="must be between 3 and 63 characters",
                                regex="^.{3,63}$",
                            ),
                            django.core.validators.RegexValidator(
                                message="is invalid, check AWS S3 bucket names restrictions (for example, can only contains letters, digits, dots and hyphens)",  # noqa: E501
                                regex="^([a-z][a-z0-9-]*[a-z0-9])(.[a-z][a-z0-9-]*[a-z0-9])*$",  # noqa: E501
                            ),
                        ],
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_s3bucket",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="Team",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("name", models.CharField(max_length=256)),
                (
                    "slug",
                    django_extensions.db.fields.AutoSlugField(
                        blank=True, editable=False, populate_from="name"
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_team",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="TeamMembership",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="api.Role"
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="api.Team"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_teammembership",
            },
        ),
        migrations.CreateModel(
            name="UserApp",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("is_admin", models.BooleanField(default=False)),
                (
                    "app",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="userapps",
                        to="api.App",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="userapps",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_userapp",
                "ordering": ("id",),
            },
        ),
        migrations.CreateModel(
            name="UserS3Bucket",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                (
                    "access_level",
                    models.CharField(
                        choices=[
                            ("readonly", "Read-only"),
                            ("readwrite", "Read-write"),
                        ],
                        default="readonly",
                        max_length=9,
                    ),
                ),
                ("is_admin", models.BooleanField(default=False)),
                (
                    "s3bucket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="users3buckets",
                        to="api.S3Bucket",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="users3buckets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "control_panel_api_users3bucket",
                "ordering": ("id",),
            },
        ),
        migrations.AddField(
            model_name="team",
            name="users",
            field=models.ManyToManyField(
                through="api.TeamMembership", to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name="apps3bucket",
            name="s3bucket",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="apps3buckets",
                to="api.S3Bucket",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="teams",
            field=models.ManyToManyField(through="api.TeamMembership", to="api.Team"),
        ),
        migrations.AddField(
            model_name="user",
            name="user_permissions",
            field=models.ManyToManyField(
                blank=True,
                help_text="Specific permissions for this user.",
                related_name="user_set",
                related_query_name="user",
                to="auth.Permission",
                verbose_name="user permissions",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="users3bucket",
            unique_together=set([("user", "s3bucket")]),
        ),
        migrations.AlterUniqueTogether(
            name="userapp",
            unique_together=set([("app", "user")]),
        ),
        migrations.AlterUniqueTogether(
            name="teammembership",
            unique_together=set([("user", "team")]),
        ),
        migrations.AlterUniqueTogether(
            name="apps3bucket",
            unique_together=set([("app", "s3bucket")]),
        ),
    ]