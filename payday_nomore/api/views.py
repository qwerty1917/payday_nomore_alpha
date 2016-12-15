from django.http import HttpResponse
from django.middleware import csrf
from django.views import View
from time import strptime
from django.http import JsonResponse
from .models import TradingDay, StockMaster, DailyQuote, BaseInterest, OilPrice, CurrencyRate
from .serializers import TradingDaySerializer, StockMasterSerializer, DailyQuoteSerializer
import json
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework.renderers import JSONRenderer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import pandas_datareader.data as web
import pandas as pd
from .sub_data_packages.sub_data_funcs import *
from dateutil.relativedelta import relativedelta
import numpy as np
from random import shuffle
import tensorflow as tf
import time


class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)
        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


class ApiTestView(View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'success': True})


class ApiTokenView(View):
    def get(self, request):
        return JsonResponse({'token': csrf.get_token(request)})


class GetTradingDayByDaysView(View):
    def get(self, request, *args, **kwargs):
        start_raw = request.GET.get('start', None)
        end_raw = request.GET.get('end', None)
        result_dict = {'success': False, 'messages': []}

        if start_raw and end_raw:
            try:
                start = strptime(start_raw, '%Y-%m-%d')
                end = strptime(end_raw, '%Y-%m-%d')
            except ValueError as e:
                result_dict['messages'].append('start, end 입력 형식 오류: \n{}'.format(str(e)))
            else:
                try:
                    days = TradingDay.objects.filter(date__range=[start_raw, end_raw])
                    count = len(days)
                except Exception as e:
                    result_dict['messages'].append('cannot get data from db: \n{}'.format(str(e)))
                else:
                    result_dict['success'] = True
                    result_dict['data'] = {'days': json.dumps(list(days), cls=DjangoJSONEncoder), 'count': count}

        else:
            result_dict['messages'].append('start_raw: {}, end_raw: {}'.format(start_raw, end_raw))

        return JsonResponse(result_dict)


@method_decorator(csrf_exempt, name='dispatch')
class StockMasterView(View):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', False)
        name = request.GET.get('name', False)
        flag = request.GET.get('flag', False)

        if flag == 'all':
            stock_master = StockMaster.objects.all()
            serializer = StockMasterSerializer(stock_master, many=True)
        elif code:
            stock_master = StockMaster.objects.filter(code=code)[0]
            serializer = StockMasterSerializer(stock_master, many=False)
        elif name:
            stock_master = StockMaster.objects.filter(name=name)[0]
            serializer = StockMasterSerializer(stock_master, many=False)
        else:
            return JsonResponse({'error': 'code: {}, name: {}'.format(code, name)})

        return JSONResponse(serializer.data)

    def post(self, request, *args, **kwargs):
        code = request.POST.get('code', None)
        name = request.POST.get('name', None)

        if code and name:
            try:
                new_stock_master = StockMaster(
                    code=code,
                    name=name
                )
                new_stock_master.save()
            except Exception as e:
                return JsonResponse({'error': str(e)})
            else:
                serializer = StockMasterSerializer(new_stock_master, many=False)
                return JSONResponse(serializer.data)
        else:
            return JsonResponse({'error': 'code: {}, name: {}'.format(code, name)})


class ParseStockCodesView(View):
    def get(self, request):
        SITE = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        flag = request.GET.get('flag', None)  # sector, all, sector_list 중 하나

        response = urllib.request.urlopen(SITE)
        html = response.read()
        soup = BeautifulSoup(html)

        table = soup.find('table', {'class': 'wikitable sortable'})
        data = {}
        for row in table.findAll('tr'):
            col = row.findAll('td')
            if len(col) > 0:
                sector = str(col[3].string.strip()).lower().replace(' ', '_')
                name = str(col[1].string.strip())
                ticker = str(col[0].string.strip())
                if flag == 'sector':
                    if sector not in data:
                        data[sector] = list()
                    data[sector].append({ticker: name})
                elif flag == 'all':
                    if 'all' not in data:
                        data['all'] = []
                    data['all'].append({ticker: name})
                elif flag == 'sector_list':
                    if 'all' not in data:
                        data['all'] = []
                    if sector not in data['all']:
                        data['all'].append(sector)

        return JsonResponse({'success': True, 'data': data})


class InitStockCodesView(View):
    def get(self, request):
        HOST = request.META['HTTP_HOST']
        get_data = {'flag': 'all'}
        response = requests.get('http://' + str(HOST) + '/api/parse_stock_codes/', params=get_data)
        received_json_data = json.loads(response.text)['data']['all']

        for index, code_name_pair in enumerate(received_json_data):
            code = list(code_name_pair.keys())[0]
            name = code_name_pair[code]

            post_data = {'code': code, 'name': name}
            response = requests.post('http://' + str(HOST) + '/api/stock_master/', data=post_data)
            print('running: ' + str(index) + '/' + str(len(received_json_data)))

        return JsonResponse({'success': True, 'added count': len(received_json_data)})


@method_decorator(csrf_exempt, name='dispatch')
class DailyQuoteAddView(View):
    def post(self, request):
        code = request.POST.get('code', None)
        start_raw = request.POST.get('start', None)  # 2011-01-01
        end_raw = request.POST.get('end', None)  # 2011-12-31
        pass_duplicated = int(request.POST.get('pass_duplicated', 0))
        working_now_str = request.POST.get('working_now_str', '')

        if not (code or start_raw or end_raw):
            error_msg = ''
            if not code:
                error_msg += 'code, '
            if not start_raw:
                error_msg += 'start, '
            if not end_raw:
                error_msg += 'end, '
            return JsonResponse({'success': False, 'message': 'your input (' + error_msg + ') is None'})

        try:
            start = datetime.strptime(start_raw, '%Y-%m-%d')
            end = datetime.strptime(end_raw, '%Y-%m-%d')
        except:
            return JsonResponse({'success': False, 'message': 'start and end should be in format %Y-%m-%d'})

        try:
            stock = StockMaster.objects.get(code=code)
        except:
            return JsonResponse({'success': False, 'message': 'cannot find StockMaster code {}'.format(code)})

        table = web.DataReader(code, 'yahoo', start, end)
        count_success = 0
        count_failure = 0
        count_exists = 0
        count_total = len(table.index)
        for r_index, row in table.iterrows():
            print('code: {}, code_working: {}, add_working: {}/{}'.format(code,
                                                                          working_now_str,
                                                                          count_success+count_failure,
                                                                          count_total))

            open_price = round(row['Open'])
            close_price = round(row['Close'])
            high = round(row['High'])
            low = round(row['Low'])
            volume_share = round(row['Volume'])
            volume_dollar = round(row['Volume'] * row['Close'])

            if False:
                print('\nday: ' + str(r_index))
                print('open: ' + str(open_price))
                print('close: ' + str(close_price))
                print('high: ' + str(high))
                print('low: ' + str(low))
                print('volume_share: ' + str(volume_share))
                print('volume_dolor: ' + str(volume_dollar))

            try:
                if len(list(DailyQuote.objects.filter(date=r_index, stock=stock))) != 0:
                    if pass_duplicated != 1:  # overwrite duplicated
                        DailyQuote.objects.filter(date=r_index, stock=stock).delete()

                        new_daily_quote = DailyQuote(
                            date=r_index,
                            stock=stock,
                            open=open_price,
                            close=close_price,
                            high=high,
                            low=low,
                            volume_share=volume_share,
                            volume_dollar=volume_dollar,
                        )
                        new_daily_quote.save()
                    else:
                        pass

                    count_exists += 1

                else:
                    new_daily_quote = DailyQuote(
                        date=r_index,
                        stock=stock,
                        open=open_price,
                        close=close_price,
                        high=high,
                        low=low,
                        volume_share=volume_share,
                        volume_dollar=volume_dollar,
                    )
                    new_daily_quote.save()

            except Exception as e:
                print(str(e))
                count_failure += 1
            else:
                count_success += 1

        return JsonResponse({'success': True,
                             'count_total': count_total,
                             'count_success': count_success,
                             'count_failure': count_failure,
                             'count_exists': count_exists,
                             'code': code,
                             'start': start_raw,
                             'end': end_raw})


class DailyQuoteInitView(View):
    def get(self, request):
        HOST = request.META['HTTP_HOST']
        start_raw = request.GET.get('start', None)
        end_raw = request.GET.get('end', None)
        pass_duplicated = int(request.GET.get('pass_duplicated', 0))


        if not (start_raw or end_raw):
            error_msg = ''
            if not start_raw:
                error_msg += 'start, '
            if not end_raw:
                error_msg += 'end, '
            return JsonResponse({'success': False, 'message': 'your input (' + error_msg + ') is None'})

        try:
            start = datetime.strptime(start_raw, '%Y-%m-%d')
            end = datetime.strptime(end_raw, '%Y-%m-%d')
        except:
            return JsonResponse({'success': False, 'message': 'start and end should be in format %Y-%m-%d'})

        total_added = 0
        total_failed = 0
        stock_master_list = list(StockMaster.objects.all())
        for index, stock_master in enumerate(stock_master_list):
            code = stock_master.code
            working_now_str = str('code_total: {}, code_working: {}'.format(len(stock_master_list), index))

            post_data = {'code': code, 'start': start_raw, 'end': end_raw, 'pass_duplicated': pass_duplicated, 'working_now_str': working_now_str}
            response = requests.post('http://' + str(HOST) + '/api/daily_quote/add/', data=post_data)
            result = json.loads(response.text)
            total_added += result['count_success']
            total_failed += result['count_failure']
            print('running: ' + str(index) + '/' + str(len(stock_master_list)))

        return JsonResponse({'success': True,
                             'added count': len(stock_master_list),
                             'total added': total_added,
                             'total failed': total_failed})


class BaseInterestInitView(View):
    def get(self, request):
        start_raw = request.GET.get('start', None)
        end_raw = request.GET.get('end', None)

        if not (start_raw or end_raw):
            error_msg = ''
            if not start_raw:
                error_msg += 'start, '
            if not end_raw:
                error_msg += 'end, '
            return JsonResponse({'success': False, 'message': 'your input (' + error_msg + ') is None'})

        try:
            start = datetime.strptime(start_raw, '%Y-%m-%d')
            end = datetime.strptime(end_raw, '%Y-%m-%d')
        except:
            return JsonResponse({'success': False, 'message': 'start and end should be in format %Y-%m-%d'})

        data_set = get_base_interest_rate(start_raw, end_raw)
        for index, interest_data_point in enumerate(data_set):
            print('working: {}/{}'.format(index+1, len(data_set)))
            new_base_interest = BaseInterest(
                date=interest_data_point['date'],
                interest=interest_data_point['interest'],
            )
            new_base_interest.save()

        return JsonResponse({'success': True})


class OilPriceInitView(View):
    def get(self, request):
        start_raw = request.GET.get('start', None)
        end_raw = request.GET.get('end', None)

        if not (start_raw or end_raw):
            error_msg = ''
            if not start_raw:
                error_msg += 'start, '
            if not end_raw:
                error_msg += 'end, '
            return JsonResponse({'success': False, 'message': 'your input (' + error_msg + ') is None'})

        try:
            start = datetime.strptime(start_raw, '%Y-%m-%d')
            end = datetime.strptime(end_raw, '%Y-%m-%d')
        except:
            return JsonResponse({'success': False, 'message': 'start and end should be in format %Y-%m-%d'})

        data_set = get_oil_price(start_raw, end_raw)
        for index, oil_data_point in enumerate(data_set):
            print('working: {}/{}'.format(index + 1, len(data_set)))
            new_oil_price = OilPrice(
                date=oil_data_point['date'],
                price=oil_data_point['price'],
            )
            new_oil_price.save()

        return JsonResponse({'success': True})


class OilPriceDelAllView(View):
    def get(self, request):
        OilPrice.objects.all().delete()

        return JsonResponse({'success': True})


class CurrencyRateInitView(View):
    def get(self, request):
        start_raw = request.GET.get('start', None)
        end_raw = request.GET.get('end', None)

        if not (start_raw or end_raw):
            error_msg = ''
            if not start_raw:
                error_msg += 'start, '
            if not end_raw:
                error_msg += 'end, '
            return JsonResponse({'success': False, 'message': 'your input (' + error_msg + ') is None'})

        try:
            start = datetime.strptime(start_raw, '%Y-%m-%d')
            end = datetime.strptime(end_raw, '%Y-%m-%d')
        except:
            return JsonResponse({'success': False, 'message': 'start and end should be in format %Y-%m-%d'})

        data_set = exchange_rate(start_raw, end_raw)
        for index, currency_data_point in enumerate(data_set):
            print('working: {}/{}'.format(index + 1, len(data_set)))
            new_currency_rate = CurrencyRate(
                currency=currency_data_point['currency'],
                date=currency_data_point['date'],
                rate=currency_data_point['rate'],
            )
            new_currency_rate.save()

        return JsonResponse({'success': True})


class GetTrainingDataView(View):
    def get(self, request):
        pivot_raw = request.GET.get('pivot', None)  # pivot: 2006-01-01 ~ 2015-11-30
        code = request.GET.get('code', None)
        reform = request.GET.get('reform', False)

        if int(reform) == 1:
            reform = True
        else:
            reform = False

        if not pivot_raw:
            return JsonResponse({'success': False, 'message': 'your input pivot is None'})

        try:
            pivot = datetime.strptime(pivot_raw, '%Y-%m-%d')
        except:
            return JsonResponse({'success': False, 'message': 'pivot should be in format %Y-%m-%d'})

        end = pivot + relativedelta(months=+12)
        start = pivot - relativedelta(months=+1)  # 한달전 데이터만 수집
        if start < datetime.strptime('2005-01-01', '%Y-%m-%d'):
            return JsonResponse({'success': False, 'message': 'start day before 2005-01-01', 'end': end, 'start': start})

        if end > datetime.strptime('2016-11-30', '%Y-%m-%d'):
            return JsonResponse({'success': False, 'message': 'end day over 2016-11-30', 'end': end, 'start': start})

        after_1_month = pivot + relativedelta(months=+1)
        after_3_month = pivot + relativedelta(months=+3)
        after_6_month = pivot + relativedelta(months=+6)
        after_12_month = end

        after_1_day = pivot + relativedelta(days=+1)

        stock = StockMaster.objects.get(code=code)
        daily_quotes_list = DailyQuote.objects.filter(stock=stock).filter(date__range=(start, end + relativedelta(days=+20)))
        input_quote_set = daily_quotes_list.filter(date__range=(start, pivot)).order_by('date')
        after_1_month_quote = daily_quotes_list.filter(date__range=(after_1_month, after_1_month + relativedelta(days=+14)))[0]
        after_3_month_quote = daily_quotes_list.filter(date__range=(after_3_month, after_3_month + relativedelta(days=+14)))[0]
        after_6_month_quote = daily_quotes_list.filter(date__range=(after_6_month, after_6_month + relativedelta(days=+14)))[0]
        after_12_month_quote = daily_quotes_list.filter(date__range=(after_12_month, after_12_month + relativedelta(days=+14)))[0]

        after_1_day_quote = daily_quotes_list.filter(date__range=(after_1_day, after_1_day + relativedelta(days=+14)))[0]

        input_interest_set = [BaseInterest.objects.get(date=x.date) for x in input_quote_set]
        input_oil_price_set = [OilPrice.objects.filter(date__range=(x.date, x.date + relativedelta(days=14)))[0] for x in input_quote_set]

        # currency_name_list = ['EUR', 'JPY', 'GBP', 'CNY']

        input_currency_rate_set_EUR = [CurrencyRate.objects.filter(currency='EUR').filter(date__range=(x.date, x.date + relativedelta(days=+14)))[0] for x in input_quote_set]
        input_currency_rate_set_JPY = [CurrencyRate.objects.filter(currency='JPY').filter(date__range=(x.date, x.date + relativedelta(days=+14)))[0] for x in input_quote_set]
        input_currency_rate_set_GBP = [CurrencyRate.objects.filter(currency='GBP').filter(date__range=(x.date, x.date + relativedelta(days=+14)))[0] for x in input_quote_set]
        input_currency_rate_set_CNY = [CurrencyRate.objects.filter(currency='CNY').filter(date__range=(x.date, x.date + relativedelta(days=+14)))[0] for x in input_quote_set]

        if not (len(input_quote_set) ==
                len(input_interest_set) ==
                len(input_oil_price_set) ==
                len(input_currency_rate_set_EUR) ==
                len(input_currency_rate_set_JPY) ==
                len(input_currency_rate_set_GBP) ==
                len(input_currency_rate_set_CNY)):
            return JsonResponse({'success': False, 'message': 'input vectors length not match', 'end': end, 'start': start, 'code': code})

        close_list = np.asarray([x.close for x in input_quote_set])
        interest_list = np.asarray([x.interest for x in input_interest_set])
        oil_list = np.asarray([x.price for x in input_oil_price_set])
        currency_list_EUR = np.asarray([x.rate for x in input_currency_rate_set_EUR])
        currency_list_JPY = np.asarray([x.rate for x in input_currency_rate_set_JPY])
        currency_list_GBP = np.asarray([x.rate for x in input_currency_rate_set_GBP])
        currency_list_CNY = np.asarray([x.rate for x in input_currency_rate_set_CNY])

        training_input = np.matrix([close_list,
                                    interest_list,
                                    oil_list,
                                    currency_list_EUR,
                                    currency_list_JPY,
                                    currency_list_GBP,
                                    currency_list_CNY]).transpose()

        print('input len (days): {}'.format(len(input_quote_set)))

        training_data = {
            'input':training_input.tolist(),
            'label':
                {
                    'after_1_month_quote': after_1_month_quote.close,
                    'after_3_month_quote': after_3_month_quote.close,
                    'after_6_month_quote': after_6_month_quote.close,
                    'after_12_month_quote': after_12_month_quote.close,
                    'after_1_day_quote': after_1_day_quote.close,
                }
        }

        return JsonResponse({
            'success': True,
            'start': start,
            'pivot': pivot,
            'after_1_month': after_1_month,
            'after_3_month': after_3_month,
            'after_6_month': after_6_month,
            'after_12_month': after_12_month,
            'training_data': training_data
        })


class GetStockVariation(View):
    def get(self, request):
        code = request.GET.get('code', None)
        month = int(request.GET.get('month', None))
        chunk_count = int(request.GET.get('chunk_count', 5))

        data_length = 150
        date1 = '2006-01-01'
        date2 = '2015-11-30'
        full_dates = pd.date_range(date1, date2).tolist()
        full_dates_len = len(full_dates)
        interval = int(full_dates_len / data_length)
        print('full_len: {}'.format(full_dates_len))
        print('interval: {}'.format(interval))
        date_index_to_pick = [(full_dates_len - 1) - x * interval for x in range(data_length)]
        date_to_use_before = [full_dates[x] for x in date_index_to_pick]

        stock_master = StockMaster.objects.get(code=code)

        quote_list_before = DailyQuote.objects.filter(stock=stock_master, date__in=date_to_use_before)
        quote_list_after = []
        for quote in quote_list_before:
            if month != 0:
                after_date = quote.date + relativedelta(months=+month)
            else:
                after_date = quote.date + relativedelta(days=+1)
            quote_list_after.append(DailyQuote.objects.filter(stock=stock_master, date__range=(after_date, after_date + relativedelta(days=+14)))[0])

        min_len = min(len(quote_list_before), len(quote_list_after))
        quote_list_before = quote_list_before[:min_len]
        quote_list_after = quote_list_after[:min_len]

        diff_list = []

        for index, quote_before in enumerate(quote_list_before):
            quote_after = quote_list_after[index]
            diff_list.append((quote_after.close-quote_before.close)/quote_before.close)

        diff_list.sort()

        num_to_del = len(diff_list)%chunk_count
        if num_to_del != 0:
            gap = len(diff_list)/num_to_del
        else:
            gap = len(diff_list)
        index_to_del_list = [int(x*gap) for x in range(num_to_del)]
        item_to_del_list = [diff_list[x] for x in index_to_del_list]
        for item_to_del in item_to_del_list:
            diff_list.remove(item_to_del)



        chunk_len = int(len(diff_list)/chunk_count)
        diff_chunk_list = []
        for i in range(0, len(diff_list), chunk_len):
            diff_chunk_list.append(diff_list[i:i+chunk_len])

        return_data = {}
        for index, chunk in enumerate(diff_chunk_list):
            if index == 0:
                return_data[index] = {"low": None, "high": max(chunk)}
            elif index == len(diff_chunk_list)-1:
                return_data[index] = {"low": max(diff_chunk_list[index-1]), "high": None}
            else:
                return_data[index] = {"low": max(diff_chunk_list[index-1]), "high": max(chunk)}

        return JsonResponse({"success": True, "result": return_data, "length": [len(x) for x in diff_chunk_list]})




class LSTMTrainView(View):
    def payload2data_formatted(self, payload, HOST, train_input, train_output, index, month, label_data):
        response = requests.get('http://' + str(HOST) + '/api/training_data/get/', params=payload)
        result = json.loads(response.text)

        input_elem_vector = []
        for input_vec in result['training_data']['input']:
            # str_vec = ','.join([str(x) for x in input_vec])
            # input_elem_vector.append([str_vec])

            input_elem_vector.append(input_vec)

        train_input.append(np.array(input_elem_vector))

        after = None
        if month == 1:
            after = result['training_data']["label"]['after_1_month_quote']
        elif month == 3:
            after = result['training_data']["label"]['after_3_month_quote']
        elif month == 6:
            after = result['training_data']["label"]['after_6_month_quote']
        elif month == 12:
            after = result['training_data']["label"]['after_12_month_quote']
        elif month == 0:
            after = result['training_data']["label"]['after_1_day_quote']

        before = result['training_data']['input'][-1][0]

        diff = (after-before)/before

        chunk_count = len(label_data['result'])
        output_elem_vector = [0]*chunk_count
        for chunk_index in range(chunk_count):
            chunk = label_data['result'][str(chunk_index)]
            if chunk_index == 0:
                if diff < chunk['high']:
                    output_elem_vector[chunk_index] = 1
            elif chunk_index == chunk_count-1:
                if diff >= chunk['low']:
                    output_elem_vector[chunk_index] = 1
            else:
                if chunk['high'] > diff >= chunk['low']:
                    output_elem_vector[chunk_index] = 1

        train_output.append(output_elem_vector)
        pass

    def get(self, request):
        code = request.GET.get('code', None)
        month = request.GET.get('month', None)
        chunk_count = int(request.GET.get('chunk_count', 5))
        data_length = int(request.GET.get('data_length', 100))
        epoch = int(request.GET.get('epoch', 5000))
        batch_size = int(request.GET.get('batch_size', 50))
        num_hidden = int(request.GET.get('num_hidden', 24))
        HOST = request.META['HTTP_HOST']

        if code in [None, '']:
            return JsonResponse({'success': False, 'message': 'no code'})

        if month in [None, '']:
            return JsonResponse({'success': False, 'message': 'no month'})
        month = int(month)

        if month not in [0, 1, 3, 6, 12]:
            return JsonResponse({'success': False, 'message': 'month should be one of 1, 3, 6, 12'})

        payload = {'code': code, 'month': month, 'chunk_count': chunk_count}
        var_response = requests.get('http://' + str(HOST) + '/api/stock/variation/get/', params=payload)
        label_data = json.loads(var_response.text)

        date1 = '2006-01-01'
        date2 = '2015-11-30'
        full_dates = pd.date_range(date1, date2).tolist()
        full_dates_len = len(full_dates)
        interval = max(1, int(full_dates_len/data_length))
        date_index_to_pick = [(full_dates_len - 1) - x*interval for x in range(data_length)]
        date_index_to_pick.reverse()
        date_to_use = [full_dates[x] for x in date_index_to_pick]

        train_input = []
        train_output = []
        date_to_use_len = len(date_to_use)
        for index, date in enumerate(date_to_use):
            start = time.time()
            print('getting data point {}, date: {}'.format(index+1, str(date)))
            payload = {'pivot': datetime.strftime(date, '%Y-%m-%d'), 'code': code}
            self.payload2data_formatted(payload, HOST, train_input, train_output, index, month, label_data)
            end = time.time()
            remaining_loop = date_to_use_len-index
            s_to_go = int((end - start)*remaining_loop)
            H = s_to_go//3600
            M = (s_to_go - H*3600)//60
            S = s_to_go - H*3600 - M*60
            print('[Data Get] remain: {}:{}:{}'.format(H,M,S))

        min_len_input = min([len(x) for x in train_input])
        print('min_len_input: {}'.format(min_len_input))
        for index, input in enumerate(train_input):
            train_input[index] = input[len(input)-min_len_input:]

        asdf = list(set([len(x) for x in train_input]))
        print('input_lens_list: {}'.format(asdf))

        for seq_index, seq in enumerate(train_input):
            close_maxmin = [max([x[0] for x in seq]), min([x[0] for x in seq])]
            interest_maxmin = [max([x[1] for x in seq]), min([x[1] for x in seq])]
            oil_maxmin = [max([x[2] for x in seq]), min([x[2] for x in seq])]
            eur_maxmin = [max([x[3] for x in seq]), min([x[3] for x in seq])]
            jyp_maxmin = [max([x[4] for x in seq]), min([x[4] for x in seq])]
            gbp_maxmin = [max([x[5] for x in seq]), min([x[5] for x in seq])]
            cny_maxmin = [max([x[6] for x in seq]), min([x[6] for x in seq])]

            for date_info_index, date_info in enumerate(seq):
                train_input[seq_index][date_info_index][0] = (date_info[0] - close_maxmin[1]) / (close_maxmin[0] - close_maxmin[1])
                train_input[seq_index][date_info_index][1] = (date_info[1] - interest_maxmin[1]) / (interest_maxmin[0] - interest_maxmin[1])
                train_input[seq_index][date_info_index][2] = (date_info[2] - oil_maxmin[1]) / (oil_maxmin[0] - oil_maxmin[1])
                train_input[seq_index][date_info_index][3] = (date_info[3] - eur_maxmin[1]) / (eur_maxmin[0] - eur_maxmin[1])
                train_input[seq_index][date_info_index][4] = (date_info[4] - jyp_maxmin[1]) / (jyp_maxmin[0] - jyp_maxmin[1])
                train_input[seq_index][date_info_index][5] = (date_info[5] - gbp_maxmin[1]) / (gbp_maxmin[0] - gbp_maxmin[1])
                train_input[seq_index][date_info_index][6] = (date_info[6] - cny_maxmin[1]) / (cny_maxmin[0] - cny_maxmin[1])

        for i in train_input[:100]:
            print(i)

        #
        ### 이까지가 데이터 준비
        #

        #
        ### 여기서부터 학습
        #

        NUM_EXAMPLES = int(data_length*0.8)  # 80 퍼센트 훈련하고 나머지로 테스트
        test_input = train_input[NUM_EXAMPLES:]
        test_output = train_output[NUM_EXAMPLES:]  # everything beyond 10,000

        train_input = train_input[:NUM_EXAMPLES]
        train_output = train_output[:NUM_EXAMPLES]

        data = tf.placeholder(tf.float32, [None, min_len_input, 7])  # [Batch Size, Sequence Length, Input Dimension]
        target = tf.placeholder(tf.float32, [None, chunk_count])  # 라벨의 길이는 chunk_count

        cell = tf.nn.rnn_cell.LSTMCell(num_hidden, state_is_tuple=True)
        cell = tf.nn.rnn_cell.DropoutWrapper(cell=cell, output_keep_prob=0.5)
        val, state = tf.nn.dynamic_rnn(cell, data, dtype=tf.float32)

        val = tf.transpose(val, [1, 0, 2])
        last = tf.gather(val, int(val.get_shape()[0]) - 1)

        weight = tf.Variable(tf.truncated_normal([num_hidden, int(target.get_shape()[1])]))
        bias = tf.Variable(tf.constant(0.1, shape=[target.get_shape()[1]]))

        prediction = tf.nn.softmax(tf.matmul(last, weight) + bias)

        cross_entropy = -tf.reduce_sum(target * tf.log(tf.clip_by_value(prediction, 1e-10, 1.0)))

        optimizer = tf.train.AdamOptimizer()
        minimize = optimizer.minimize(cross_entropy)

        mistakes = tf.not_equal(tf.argmax(target, 1), tf.argmax(prediction, 1))
        error = tf.reduce_mean(tf.cast(mistakes, tf.float32))

        init_op = tf.global_variables_initializer()
        sess = tf.Session()
        sess.run(init_op)

        no_of_batches = int(len(train_input) / batch_size)
        for i in range(epoch):
            start = time.time()
            ptr = 0
            for j in range(no_of_batches):
                inp, out = train_input[ptr:ptr + batch_size], train_output[ptr:ptr + batch_size]
                ptr += batch_size
                sess.run(minimize, {data: inp, target: out})
            if i % 50 == 0:
                print("Epoch - {}/{}".format(i, epoch))
                end = time.time()
                remaining_loop = epoch - i
                s_to_go = int((end - start) * remaining_loop)
                H = s_to_go // 3600
                M = (s_to_go - H * 3600) // 60
                S = s_to_go - H * 3600 - M * 60
                print('[Training] remain: {}:{}:{}'.format(H, M, S))
        incorrect = sess.run(error, {data: test_input, target: test_output})
        print('Epoch {:2d} error {:3.1f}%'.format(i + 1, 100 * incorrect))
        sess.close()


        return JsonResponse({'success': True,
                             'code': code,
                             'label_data': label_data,
                             'train_output': train_output,
                             'error': '{:3.1f}%'.format(100 * incorrect)})

