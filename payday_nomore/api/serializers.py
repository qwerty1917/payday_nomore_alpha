from rest_framework import serializers
from .models import TradingDay, StockMaster, DailyQuote


class TradingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = TradingDay
        fields = ('date',
                  'yesterday',
                  'is_rest_day',
                  'weekday',
                  'is_last_business_day_of_week',
                  'is_last_business_day_of_month',
                  'is_last_business_day_of_year')


class StockMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMaster
        fields = ('code',
                  'name')


class DailyQuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyQuote
        fields = ('date',
                  'stock',
                  'start',
                  'end',
                  'high',
                  'low',
                  'volume_share',
                  'volume_dollar')
