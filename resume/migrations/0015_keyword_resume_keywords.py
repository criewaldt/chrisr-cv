# Generated by Django 5.0.1 on 2024-02-05 04:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resume', '0014_rename_description_employmenthistory_description_html_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Keyword',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('category', models.CharField(blank=True, max_length=100)),
            ],
        ),
        migrations.AddField(
            model_name='resume',
            name='keywords',
            field=models.ManyToManyField(to='resume.keyword'),
        ),
    ]
