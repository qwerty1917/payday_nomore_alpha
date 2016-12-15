from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^test/$', views.ApiTestView.as_view(), name='test'),
    url(r'^token/$', views.ApiTokenView.as_view(), name='token'),

    url(r'^trading_day/get/by_day/$', views.GetTradingDayByDaysView.as_view(), name='get_trading_day_by_days'),

    url(r'^stock_master/$', views.StockMasterView.as_view(), name='stock_master'),
    url(r'^stock_codes/parse/$', views.ParseStockCodesView.as_view(), name='stock_codes_parse'),
    url(r'^stock_codes/init/$', views.InitStockCodesView.as_view(), name='stock_codes_init'),

    url(r'daily_quote/add/$', views.DailyQuoteAddView.as_view(), name='daily_quote_add_view'),
    url(r'daily_quote/init/$', views.DailyQuoteInitView.as_view(), name='daily_quote_init_view'),

    url(r'base_interest/init/$', views.BaseInterestInitView.as_view(), name='base_interest_init_view'),
    url(r'oil_price/init/$', views.OilPriceInitView.as_view(), name='oil_price_init_view'),
    url(r'oil_price/del/all/$', views.OilPriceDelAllView.as_view(), name='oil_price_del_all_view'),
    url(r'currency_rate/init/$', views.CurrencyRateInitView.as_view(), name='currency_rate'),

    url(r'training_data/get/$', views.GetTrainingDataView.as_view(), name='training_data_get'),
    url(r'stock/variation/get/$', views.GetStockVariation.as_view(), name='stock_variation_get'),
    url(r'LSTMTrain/$', views.LSTMTrainView.as_view(), name='LSTMTrain'),
]