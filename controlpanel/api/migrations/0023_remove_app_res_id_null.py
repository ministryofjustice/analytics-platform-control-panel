# Generated by Django 4.1.4 on 2022-12-26 12:52
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0022_populate_app_res_id_values'),
    ]

    operations = [
        migrations.AlterField(
            model_name='app',
            name='res_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
