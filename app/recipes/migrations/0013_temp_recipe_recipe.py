# Generated by Django 5.0.6 on 2024-06-07 17:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recipes", "0012_recipe_step_order_alter_recipe_main_image_temp_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="temp_recipe",
            name="recipe",
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="recipes.recipe",
            ),
        ),
    ]
