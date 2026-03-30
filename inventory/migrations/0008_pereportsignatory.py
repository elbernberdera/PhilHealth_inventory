# Generated manually for PpeReportSignatory

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_alter_ppeasset_category_choices'),
    ]

    operations = [
        migrations.CreateModel(
            name='PpeReportSignatory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('prepared', 'Prepared by'), ('verified', 'Verified by'), ('noted', 'Noted by')], db_index=True, max_length=16)),
                ('name', models.CharField(max_length=200, verbose_name='Name')),
                ('position', models.CharField(blank=True, max_length=200, verbose_name='Position / Title')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Sort order')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'PPE Report Signatory',
                'verbose_name_plural': 'PPE Report Signatories',
                'ordering': ['role', 'sort_order', 'name'],
            },
        ),
    ]
