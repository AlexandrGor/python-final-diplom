# Generated by Django 3.2.16 on 2023-01-16 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0011_remove_shop_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='is_active',
            field=models.BooleanField(default=False, verbose_name='active'),
        ),
    ]
