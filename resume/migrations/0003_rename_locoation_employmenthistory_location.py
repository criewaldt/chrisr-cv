# Generated by Django 5.0.1 on 2024-01-22 12:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('resume', '0002_remove_resume_job_title_resume_current_title_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='employmenthistory',
            old_name='locoation',
            new_name='location',
        ),
    ]
