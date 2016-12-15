from django.contrib import admin
from .models import TradingDay, StockMaster, DailyQuote, BaseInterest, OilPrice, CurrencyRate


@admin.register(TradingDay)
class TradingDayAdmin(admin.ModelAdmin):
    list_display = [f.name for f in TradingDay._meta.fields]


@admin.register(StockMaster)
class StockMasterAdmin(admin.ModelAdmin):
    list_display = [f.name for f in StockMaster._meta.fields]
    search_fields = ('code', 'name',)


@admin.register(DailyQuote)
class DailyQuoteAdmin(admin.ModelAdmin):
    list_display = ['get_stock_code',
                    'get_stock_name',
                    'date', 'open',
                    'close', 'high',
                    'low',
                    'volume_share',
                    'volume_dollar',]
    search_fields = ('date', 'close')

    def get_stock_name(self, obj):
        return obj.stock.name
    get_stock_name.short_description = 'name'

    def get_stock_code(self, obj):
        return obj.stock.code
    get_stock_code.short_description = 'code'


@admin.register(BaseInterest)
class BaseInterestAdmin(admin.ModelAdmin):
    list_display = [f.name for f in BaseInterest._meta.fields]
    search_fields = ('date',)


@admin.register(OilPrice)
class OilPriceAdmin(admin.ModelAdmin):
    list_display = [f.name for f in OilPrice._meta.fields]
    search_fields = ('date',)


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = [f.name for f in CurrencyRate._meta.fields]
    search_fields = ('date',)