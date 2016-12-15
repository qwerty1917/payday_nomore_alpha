from bs4 import BeautifulSoup
import urllib
from datetime import datetime, date
import calendar
import csv
import requests
from django.conf import settings


def get_base_interest_rate(start='2005-01-01', end='2016-11-30'):
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')

    SITE = 'http://www.multpl.com/10-year-treasury-rate/table/by-month'
    response = urllib.request.urlopen(SITE)
    html = response.read()
    soup = BeautifulSoup(html, "html.parser")

    table = soup.find('table', {'id': 'datatable'})
    data = []
    for row in table.findAll('tr'):
        col = row.findAll('td')
        if len(col) > 0:
            interest_date_raw = str(col[0].string.strip()).lower()
            interest_rate_raw = str(col[1].string.strip())

            # print('date: {}, rate: {}'.format(interest_date_raw, interest_rate_raw))

            interest_date = datetime.strptime(interest_date_raw, '%b %d, %Y')
            interest_rate = float(interest_rate_raw.replace('%',''))

            num_days = calendar.monthrange(interest_date.year, interest_date.month)[1]

            for tmp_day in range(1, num_days+1):
                tmp_daetime = datetime(year=interest_date.year, month=interest_date.month, day=tmp_day)
                if start_date <= tmp_daetime <= end_date:
                    data.append({'date': tmp_daetime, 'interest': interest_rate})
    return data


def get_oil_price(start='2005-01-01', end='2016-11-30'):
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')

    with open(settings.BASE_DIR + "/static/" + 'CHRIS-CME_CL1.csv', 'r') as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        data = []
        for index, row in enumerate(csvreader):
            if index == 0:  # 첫 행은 라벨임
                continue
            oil_date = datetime.strptime(row[0], '%Y-%m-%d')
            if start_date <= oil_date <= end_date:
                oil_price = float(row[4])
                data.append({'date': oil_date, 'price': oil_price})
            else:
                continue
        return data


def exchange_rate(start='2005-01-01', end='2016-11-30'):
    start_date = datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.strptime(end, '%Y-%m-%d')

    file_names = ['EUR.txt', 'JPY.txt', 'GBP.txt', 'CNY.txt']
    data = []
    for file_name in file_names:
        print('\n' + file_name)
        currency = file_name.split('.')[0].strip()
        f = open(settings.BASE_DIR + "/static/" + file_name, 'r')
        for line in f:
            line_raw = line.strip().split('	')
            currency_date = datetime.strptime(line_raw[0], '%d/%m/%Y')
            rate = float(line_raw[1])

            if start_date <= currency_date <= end_date:
                print('date: {}, currency: {}'.format(currency_date, rate))
                data.append({'currency': currency, 'date': currency_date, 'rate': rate})

    return data




if __name__ == '__main__':
    pass
    # baseInterestRate()
    # oilPrice()
    # exchange_rate()
