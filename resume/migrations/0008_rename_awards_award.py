# Generated by Django 5.0.1 on 2024-01-23 22:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('resume', '0007_awards_resume_awards'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Awards',
            new_name='Award',
        ),
    ]
