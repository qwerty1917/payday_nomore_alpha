# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-11-25 11:33
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_auto_20161125_1116'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tradingday',
            options={'ordering': ('date',)},
        ),
    ]
