# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


#  일단 안씀
class TradingDay(models.Model):
    date = models.DateField(primary_key=True, unique=True)  # 날짜
    yesterday = models.DateField()  # 전일날짜
    is_rest_day = models.CharField(max_length=1)  # 휴장일 구분 (미국기준)
    weekday = models.CharField(max_length=1)  # 요일 구분
    is_last_business_day_of_week = models.CharField(max_length=1)  # 주별 마지막 영업일 구분
    is_last_business_day_of_month = models.CharField(max_length=1)  # 월별 마지막 영업일 구분
    is_last_business_day_of_year = models.CharField(max_length=1)  # 연별 마지막 영업일 구분

    class Meta:
        ordering = ('date',)


class StockMaster(models.Model):
    code = models.CharField(max_length=10)  # 미국 종목코드는 1~5글자 (선물은 1~2글자 정도 되는듯)
    name = models.CharField(max_length=100)  # 종목이름

    class Meta:
        ordering = ('code',)


class DailyQuote(models.Model):
    date = models.DateField(null=False)
    stock = models.ForeignKey(StockMaster,
                              related_name='DailyQuotes',
                              null=False,
                              on_delete=models.CASCADE)  # 종목정보 FK
    open = models.BigIntegerField()
    close = models.BigIntegerField()
    high = models.BigIntegerField()
    low = models.BigIntegerField()
    volume_share = models.BigIntegerField()
    volume_dollar = models.BigIntegerField()

    class Meta:
        ordering = ('stock_id',)


class BaseInterest(models.Model):
    date = models.DateField(null=False)
    interest = models.FloatField(null=False)

    class Meta:
        ordering = ('date',)


class OilPrice(models.Model):
    date = models.DateField(null=False)
    price = models.FloatField(null=False)

    class Meta:
        ordering = ('date',)


class CurrencyRate(models.Model):
    currency = models.CharField(max_length=20, null=True)
    date = models.DateField(null=False)
    rate = models.FloatField(null=False)

    class Meta:
        ordering = ('date',)
