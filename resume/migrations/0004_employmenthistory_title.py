# Generated by Django 5.0.1 on 2024-01-22 21:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resume', '0003_rename_locoation_employmenthistory_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='employmenthistory',
            name='title',
            field=models.CharField(default='System Admin', max_length=100),
            preserve_default=False,
        ),
    ]
