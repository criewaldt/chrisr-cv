# Generated by Django 5.0.1 on 2024-01-19 06:11

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='EmploymentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=100)),
                ('locoation', models.CharField(max_length=100)),
                ('position', models.CharField(max_length=100)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('description', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='ProfessionalSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('summary', models.TextField()),
                ('highlights', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Resume',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('email', models.EmailField(max_length=254)),
                ('phone', models.CharField(max_length=20)),
                ('job_title', models.CharField(max_length=100)),
                ('employment_history', models.ManyToManyField(to='resume.employmenthistory')),
                ('professional_summary', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='resume.professionalsummary')),
            ],
        ),
    ]
