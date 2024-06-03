# Generated by Django 5.0.6 on 2024-06-03 14:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_user_social_alter_user_gender"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="is_alert",
            field=models.BooleanField(blank=True, default=True, null=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="social",
            field=models.CharField(max_length=100, null=True),
        ),
    ]
