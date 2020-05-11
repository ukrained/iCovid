#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '0.9.4[rc]'
__release__ = '11 May 2020'
__author__ = 'Alex Viytiv'

# modules
import urllib.request
import urllib.parse
import requests
import argparse
import json
import glob
import ssl
import re
import os

from lxml import html
from ftplib import FTP
from getpass import getpass
from datetime import datetime, date, timedelta
from utils import colour, logLevel, logger
from urllib.parse import quote


class htmlWorker:
    ''' Provide HTML processing functionality '''
    def __init__(self, source, target, pattern='{{ ([a-zA-Z_0-9]*) }}'):
        ''' Constructor of htmlWorker object

        :param source: source HTML file
        :param target: target HTML file
        '''
        if not os.path.isfile(source):
            raise FileExistsError('File not exist')
        elif not source.endswith('.html') or not target.endswith('.html'):
            raise Exception('Not an HTML file')

        self._source = source
        self._target = target
        self._pattern = pattern
        self._vars = {}

        with open(self._source, 'r+') as f:
            self._content = f.read()

        self._analyze_vars()

    def _analyze_vars(self):
        ''' Analyze source HTML content

        :param var_pattern: pattern of variables
        '''
        for var in re.findall(self._pattern, self._content):
            self._vars[var] = ''

    def render(self, values):
        ''' Substitute values to their position '''
        # store variables value
        for value in values:
            if value in self._vars:
                self._vars[value] = values[value]

        # replace tokens in original file
        #    self._content.replace('{{ %s }}' % var, val)
        for var, val in self._vars.items():
            self._content = re.sub(r'{{ %s }}' % var, val, self._content, flags=re.MULTILINE)

    def save(self):
        ''' Write new content to the target file '''
        with open(self._target, 'w+') as f:
            f.write(self._content)


class dbWorker:
    ''' DataBase manager '''

    def __init__(self, path, log_level=logLevel.NORMAL):
        ''' DB Constructor '''
        self._path = path
        self.__db = {}
        self.__auto_save = True

        self.logger = logger(log_level)
        self._upload()

    def _upload(self):
        ''' Upload DB from the file '''
        if not os.path.isfile(self._path):
            self.logger.error('Файл БД \'{}\' не існує'.format(self._path))
            if not self.logger.approve('Створити БД'):
                self.logger.critical('Заборонена робота без БД')
                self.__auto_save = False
                exit(1)
            return

        if self.__db:
            self.logger.warning('БД вже ініціалізована')
            if not self.logger.approve('Перезаписати вміст БД'):
                self.logger.normal('БД не перезаписана')
                return

        with open(self._path, 'r+') as fp:
            # read data for backup and reset pointer
            backup_data = fp.read()
            fp.seek(0)

            # try to upload as JSON
            try:
                self.__db = json.load(fp)
            except Exception as e:
                # failure processing
                self.__auto_save = False
                self.logger.error('Помилка при підвантаженні БД')
                raise e

            # Create backup file
            with open(self._path + '.backup', 'w+') as fpb:
                fpb.write(backup_data)

            self.logger.debug('Створено резервну копію даних "%s"' % (self._path + '.backup'))

        self.logger.success('БД підвантажено')

    def save(self):
        ''' Load DB to the file '''
        with open(self._path, 'w+') as fp:
            json.dump(self.__db, fp, indent=4, ensure_ascii=False)

        self.logger.normal('БД збережено')

    def update(self, key, config):
        ''' Update DB entries

        :param key: dict of keys used to identify config point
        :param config: new config
        '''
        # keys {'date':'*', 'country': '*', 'region': '*'}
        k_date = key.get('date')
        k_cont = key.get('country')
        k_regn = key.get('region')

        if not k_date:
            self.logger.error('Ключ "date" обов\'язковий')
            return
        elif not self.__db.get(k_date):
            # create if not exist
            self.__db[k_date] = {}

        if k_cont:
            if not self.__db[k_date].get(k_cont):
                # create if not exist
                self.__db[k_date][k_cont] = {}

            if key.get('region'):
                if not self.__db[k_date][k_cont]['regions'].get(k_regn):
                    # create if not exist
                    self.__db[k_date][k_cont]['regions'][k_regn] = {}

                self.__db[k_date][k_cont]['regions'][k_regn] = config
                self.logger.debug('БД регіону {} оновлено'.format(k_regn))
                return

            self.__db[k_date][k_cont] = config
            self.logger.debug('БД країни {} оновлено'.format(k_cont))
            return

        self.__db[k_date] = config
        self.logger.debug('БД дати {} оновлено'.format(k_date))
        return

    def get(self, key):
        ''' Update DB entries

        :param key: dict of keys used to identify config point
        :param config: new config
        '''
        # keys {'date':'*', 'country': '*', 'region': '*'}
        k_date = key.get('date')
        k_cont = key.get('country')
        k_regn = key.get('region')

        if not k_date:
            self.logger.error('Ключ "date" обов\'язковий')
            return None
        elif not self.__db.get(k_date):
            return None

        if k_cont:
            if not self.__db[k_date].get(k_cont):
                return None

            if key.get('region'):
                if not self.__db[k_date][k_cont]['regions'].get(k_regn):
                    return None

                return self.__db[k_date][k_cont]['regions'][k_regn]

            return self.__db[k_date][k_cont]

        return self.__db[k_date]

    def __is_db_sync(self):
        # TODO: Check DB is sync
        return True

    def __del__(self):
        ''' DB Destructor '''
        if self.__auto_save:
            self.save()


class iCovidBase:
    ''' Base class with common functionality '''
    def __init__(self, log_level=logLevel.NORMAL):
        self.logger = logger(log_level)
        self.db = dbWorker('icovid.db', self.logger.get_lvl())

        self._vocab = {}
        self._load_vocabs()

    def _load_vocabs(self):
        vocabs = [file for file in glob.glob("*.vocab")]

        for vocab in vocabs:
            slang, dlang = os.path.basename(vocab).split('.')[0].split('_')

            # create vocabularies if not exist
            self._vocab[slang] = self._vocab.get(slang, {})
            self._vocab[slang][dlang] = self._vocab[slang].get(dlang, {})

            with open(vocab, 'r+') as fp:
                self._vocab[slang][dlang] = json.load(fp)

            self.logger.success('Словник "%s-%s" підвантажено' % (slang, dlang))

    def _web_request(self, url):
        ''' Function perform HTML page request

        :param url: URL to webpage
        :return: 'utf-8'-encoded HTML page
        '''
        html = requests.get(url).text

        return html  # .decode('utf-8')

    def _html_get_node(self, html_buffer, pattern, nid=None):
        ''' Function lookup HTML content

        :param html: WEB page HTML data
        :param pattern: regex pattern for node
        :param nid: Node ID if user want specific node
        :return: all nodes found
        '''
        tree = html.fromstring(html_buffer)
        nodes = tree.xpath(pattern)

        return nodes[nid] if nid is not None else nodes

    def __del__(self):
        for slang in self._vocab:
            for dlang in self._vocab[slang]:
                vocab = '%s_%s.vocab' % (slang, dlang)
                with open(vocab, 'w+') as fp:
                    json.dump(self._vocab[slang][dlang], fp, indent=4, ensure_ascii=False)

        self.logger.normal('Словники збережено')


class iCovid (iCovidBase):
    def __init__(self, debug=False):
        ''' Constructor '''
        super().__init__(logLevel.TRACE if debug else logLevel.NORMAL)

        # initialize FTP object
        self.ftp = FTP()
        self.ftp.set_debuglevel(0)

    def update(self):
        ''' Update latest data '''
        # update callbacks
        upd_cbs = [self._upd_ukr, self._upd_isr, self._upd_pol, self._upd_rus,
                   self._upd_hug]

        curr_date = datetime.now().strftime("%d %b %Y")

        self.logger.normal('Оновлюємо дані ..')
        for upd_cb in upd_cbs:
            data = upd_cb()
            self.db.update({'date': curr_date, 'country': data['Name']}, data)
            self.logger.success('Дані з {} оновлені'.format(data['Name']))

    def _upd_ukr(self):
        config = {'Name': 'Україна', 'Code': 'ukr', 'ViewBoxSz': '0 0 640 410',
                  'Population': 41880000, 'Area': 603628,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {}}

        config = self.__upd_ukr_total(config)
        config = self.__upd_ukr_regions(config)

        return config

    def __upd_ukr_total(self, config):
        # covid19.gov.ua
        self.logger.normal(' - Збір загальних даних з covid19.gov.ua ..')
        page = self._web_request('https://covid19.gov.ua/')

        divs = self._html_get_node(page, './/div[@class="one-field light-box info-count"]')
        if len(divs) != 4:
            self.logger.error('Неочікуване число елементів - %d' % len(divs))
            exit(1)

        for i, case in enumerate(['Tested', 'Sick', 'Recovered', 'Dead']):
            config[case] = int(divs[i].xpath('.//div')[0].text.strip().replace(' ', ''))

        return config

    def __upd_ukr_regions(self, config):
        # moz.gov.ua
        # detailed - https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/
        self.logger.normal(' - Збір даних про регіони з moz.gov.ua ..')
        page = self._web_request('https://moz.gov.ua/article/news/operativna-informacija-pro-poshirennja-koronavirusnoi-infekcii-2019-ncov-1')

        # initial regions data
        initial = ["Автономна Республіка Крим", "Вінницька область",
                   "Волинська область", "Дніпропетровська область",
                   "Донецька область", "Житомирська область",
                   "Закарпатська область", "Запорізька область",
                   "Івано-Франківська область", "Кіровоградська область",
                   "м. Київ", "м. Севастополь", "Київська область",
                   "Львівська область", "Луганська область",
                   "Миколаївська область", "Одеська область",
                   "Полтавська область", "Рівненська область",
                   "Сумська область", "Тернопільська область",
                   "Харківська область", "Херсонська область",
                   "Хмельницька область", "Чернівецька область",
                   "Черкаська область", "Чернігівська область"]
        config['Regions'] = {k: 0 for k in initial}

        regions = self._html_get_node(page, './/div[@class="editor"]//ul')[0].xpath('.//li')
        # regions = self._html_get_node(page, './/div[@class="editor"]//p')[2].text_content().split('\n')
        for region in regions:
            reg, sick = region.text.replace('\xa0', '').split(' — ')
            # reg, sick = region.replace('\xa0', '').split(' — ')
            config['Regions'][reg] = int(sick.strip().split()[0])

        return config

    def _upd_isr(self):
        config = {'Name': 'Ізраїль', 'Code': 'isr', 'ViewBoxSz': '0 0 250 800',
                  'Population': 9136000, 'Area': 20770,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {},
                  'vii': '☣️ Дані з багатьох регіонів Ізраїлю тимчасово недоступні.'}

        config = self.__upd_isr_total(config)
        config = self.__upd_isr_regions(config)

        return config

    def __upd_isr_total(self, config):
        # govextra.gov.il
        self.logger.normal(' - Збір загальних даних з govextra.gov.il ..')
        page = self._web_request('https://govextra.gov.il/ministry-of-health/corona/corona-virus/')

        testsick = self._html_get_node(page, './/div[@class="corona-xl corona-bold corona-sickmiddle"]')
        config['Tested'] = int(testsick[0].text.replace(',', ''))
        config['Sick'] = int(testsick[1].text.replace(',', ''))

        deadrec = self._html_get_node(page, './/div[@class="corona-lg corona-bold"]')
        config['Dead'] = int(deadrec[0].text.replace(',', ''))
        config['Recovered'] = int(deadrec[1].text.replace(',', ''))

        return config

    def __upd_isr_regions(self, config):
        # news.google.com
        self.logger.normal(' - Збір даних про регіони з news.google.com ..')
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F03spz')

        # initial regions data
        initial = ['Єрусалимський округ', "Центральний округ (Хамерказ)",
                   'Тель-Авівський округ', "Північний округ (Хацафон)",
                   'Південний округ (Хадаром)', "Хайфський округ (Хейфа)",
                   'Голанські Висоти', 'Палестина']
        config['Regions'] = {k: 0 for k in initial}

        # used to store data under better regions naming
        name_mapping = {"Єрусалим": "Єрусалимський округ",
                        "Хадаром": "Південний округ (Хадаром)",
                        "Північний округ": "Північний округ (Хацафон)",
                        "Хамерказ": "Центральний округ (Хамерказ)",
                        "Хефа": "Хайфський округ (Хейфа)"}

        # get regions. skip first two general nodes
        regions = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr')[2:]
        for region in regions:
            reg = region.xpath('.//th//div//span')[0].text
            reg_name = name_mapping.get(reg, reg)

            sick = region.xpath('.//td')[0].text.strip().replace('\xa0', '')
            config['Regions'][reg_name] = int(sick) if sick != '—' else 0

        # update Palestine separately
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F01k0p4')

        palestine = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr', nid=1)
        sick = palestine.xpath('.//td')[0].text.strip().replace('\xa0', '')
        config['Regions']['Палестина'] = int(sick)

        return config

    def _upd_pol(self):
        config = {'Name': 'Польща', 'Code': 'pol', 'ViewBoxSz': '0 0 650 600',
                  'Population': 38433600, 'Area': 312679,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {}}

        config = self.__upd_pol_total(config)
        config = self.__upd_pol_regions(config)

        return config

    def __upd_pol_total(self, config):
        # news.google.com
        self.logger.normal(' - Збір загальних даних з news.google.com ..')
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F05qhw')

        # manually updated value due to inability to scrap
        # this data from the network
        # source: https://twitter.com/MZ_GOV_PL
        config['Tested'] = 443506

        total_info = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr')[1]
        sick = total_info.xpath('.//td')[0].text.strip().replace('\xa0', '')
        config['Sick'] = int(sick) if sick != '—' else 0

        recv = total_info.xpath('.//td')[2].text.strip().replace('\xa0', '')
        config['Recovered'] = int(recv) if sick != '—' else 0

        dead = total_info.xpath('.//td')[3].text.strip().replace('\xa0', '')
        config['Dead'] = int(dead) if sick != '—' else 0

        return config

    def __upd_pol_regions(self, config):
        # news.google.com
        self.logger.normal(' - Збір даних про регіони з news.google.com ..')
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F05qhw')

        # initial regions data
        initial = ['Мазовецьке воєводство', 'Сілезьке воєводство',
                   'Нижньосілезьке воєводство', 'Великопольське воєводство',
                   'Лодзьке воєводство', 'Малопольське воєводство',
                   'Куявсько-Поморське воєводство', 'Поморське воєводство',
                   'Опольске воєводство', 'Західнопоморське воєводство',
                   'Підляське воєводство', 'Люблінське воєводство',
                   'Підкарпатське воєводство', 'Свентокшиське воєводство',
                   'Вармінсько-Мазурське воєводство', 'Любуське воєводство']
        config['Regions'] = {k: 0 for k in initial}

        # used to store data under better regions naming
        name_mapping = {'Мазовецьке': 'Мазовецьке воєводство',
                        'Шльонське воєводство': 'Сілезьке воєводство',
                        'Нижньосілезьке': 'Нижньосілезьке воєводство',
                        'Лодзький': 'Лодзьке воєводство',
                        'Малопольське': 'Малопольське воєводство',
                        'Куявсько-Поморське': 'Куявсько-Поморське воєводство',
                        'Поморські': 'Поморське воєводство',
                        'Опольске': 'Опольске воєводство',
                        'Заходньопоморське воєводство': 'Західнопоморське воєводство',
                        'Подкарпатське воєводство': 'Підкарпатське воєводство',
                        'Вармінсько-Мазурське': 'Вармінсько-Мазурське воєводство',
                        'Любуске': 'Любуське воєводство'}

        # get regions. skip first two general nodes
        regions = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr')[2:]
        for region in regions:
            reg = region.xpath('.//th//div//span')[0].text
            reg_name = name_mapping.get(reg, reg)

            sick = region.xpath('.//td')[0].text.strip().replace('\xa0', '')
            config['Regions'][reg_name] = int(sick) if sick != '—' else 0

        return config

    def _upd_rus(self):
        config = {'Name': 'Московія', 'Code': 'rus', 'ViewBoxSz': '0 0 1250 800',
                  'Population': 144526636, 'Area': 17098246,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {}}

        config = self.__upd_rus_total(config)
        config = self.__upd_rus_regions(config)

        return config

    def __upd_rus_total(self, config):
        # news.google.com
        self.logger.normal(' - Збір загальних даних з стопкоронавирус.рф ..')
        page = self._web_request('https://стопкоронавирус.рф/information')

        total_info = self._html_get_node(page, './/cv-stats-virus', nid=0)
        data = json.loads(total_info.attrib.get(':stats-data', '{}'))
        data['tested'] = data['tested'].replace(',', '.')

        numeric_const_pattern = '[-+]?(?:(?:\d*\.\d+)|(?:\d+\.?))(?:[Ee][+-]?\d+)?'
        rx = re.compile(numeric_const_pattern, re.VERBOSE)

        config['Tested'] = int(float(rx.findall(data['tested'])[0]) * 10**6)
        config['Sick'] = int(data.get('sick', 0).replace(' ', ''))
        config['Recovered'] = int(data.get('healed', 0).replace(' ', ''))
        config['Dead'] = int(data.get('died', 0).replace(' ', ''))
        return config

    def __upd_rus_regions(self, config):
        # news.google.com
        self.logger.normal(' - Збір даних про регіони з стопкоронавирус.рф ..')
        page = self._web_request('https://стопкоронавирус.рф/information')

        # initial regions data
        initial = ['м. Москва', 'Московська область',
                   'м. Санкт-Петербург', 'Нижньогородська область',
                   'Республіка Дагестан', 'Мурманська область',
                   'Краснодарський край', 'Тульська область',
                   'Ростовська область', 'Свердловська область',
                   'Калузька область', 'Брянська область',
                   'Республіка Татарстан', 'Рязанська область',
                   'Республіка Північна Осетія - Аланія',
                   'Ленінградська область', 'Республіка Башкортостан',
                   'Курська область', 'Тамбовська область',
                   'Володимирська область', 'Республіка Інгушетія',
                   'Кабардино-Балкарська республіка', 'Республіка Мордовія',
                   'Ямало-Ненетський авт. округ', 'Республіка Чувашія',
                   'Ярославська область', 'Красноярський край',
                   'Саратовська область', 'Новосибірська область',
                   'Ставропольський край', 'Орловська область',
                   'Челябінська область', 'Оренбурзька область',
                   'Республіка Марій Ел', 'Хабаровський край',
                   'Самарська область', 'Республіка Комі',
                   'Волгоградська область', 'Тверська область',
                   'Воронезька область', 'Приморський край',
                   'Липецька область', 'Пермський край',
                   'Кіровська область', 'Тюменська область',
                   'Чеченська Республіка', 'Ульянівська область',
                   'Пензенська область', 'Іванівська область',
                   'Смоленська область', 'Калінінградська область',
                   'Астраханська область', 'Алтайський край',
                   'Білгородська область', 'Ханти-Мансійський авт. округ',
                   'Республіка Бурятія', 'Карачаєво-Черкеська Республіка',
                   'Новгородська область', 'Республіка Саха (Якутія)',
                   'Республіка Калмикія', 'Архангельська область',
                   'Республіка Хакасія', 'Камчатський край',
                   'Удмуртська Республіка', 'Костромська область',
                   'Псковська область', 'Забайкальський край',
                   'Іркутська область', 'Вологодська область',
                   'Омська область', 'Республіка Адигея',
                   'Кемеровська область', 'Томська область',
                   'Єврейська автономна область', 'Магаданська область',
                   'Республіка Карелія', 'Амурська область',
                   'Курганська область', 'Республіка Тива (Тува)',
                   'Ненецький авт. округ', 'Сахалінська область',
                   'Чукотський авт. округ', 'Республіка Алтай']
        config['Regions'] = {k: 0 for k in initial}

        # used to store data under better regions naming
        name_mapping = {'Москва': 'м. Москва',
                        'Московская область': 'Московська область',
                        'Санкт-Петербург': "м. Санкт-Петербург",
                        'Нижегородская область': "Нижньогородська область",
                        'Республика Дагестан': "Республіка Дагестан",
                        'Мурманская область': "Мурманська область",
                        'Краснодарский край': "Краснодарський край",
                        'Тульская область': "Тульська область",
                        'Ростовская область': "Ростовська область",
                        'Свердловская область': "Свердловська область",
                        'Калужская область': "Калузька область",
                        'Брянская область': "Брянська область",
                        'Республика Татарстан': "Республіка Татарстан",
                        'Рязанская область': "Рязанська область",
                        'Республика Северная Осетия — Алания': "Республіка Північна Осетія - Аланія",
                        'Ленинградская область': "Ленінградська область",
                        'Республика Башкортостан': "Республіка Башкортостан",
                        'Курская область': "Курська область",
                        'Тамбовская область': "Тамбовська область",
                        'Владимирская область': "Володимирська область",
                        'Республика Ингушетия': "Республіка Інгушетія",
                        'Кабардино-Балкарская Республика': "Кабардино-Балкарська республіка",
                        'Республика Мордовия': "Республіка Мордовія",
                        'Ямало-Ненецкий автономный округ': "Ямало-Ненетський авт. округ",
                        'Республика Чувашия': "Республіка Чувашія",
                        'Ярославская область': "Ярославська область",
                        'Красноярский край': "Красноярський край",
                        'Саратовская область': "Саратовська область",
                        'Новосибирская область': "Новосибірська область",
                        'Ставропольский край': "Ставропольський край",
                        'Орловская область': "Орловська область",
                        'Челябинская область': "Челябінська область",
                        'Оренбургская область': "Оренбурзька область",
                        'Республика Марий Эл': "Республіка Марій Ел",
                        'Хабаровский край': "Хабаровський край",
                        'Самарская область': "Самарська область",
                        'Республика Коми': "Республіка Комі",
                        'Волгоградская область': "Волгоградська область",
                        'Тверская область': "Тверська область",
                        'Воронежская область': "Воронезька область",
                        'Приморский край': "Приморський край",
                        'Липецкая область': "Липецька область",
                        'Пермский край': "Пермський край",
                        'Кировская область': "Кіровська область",
                        'Тюменская область': "Тюменська область",
                        'Чеченская Республика': "Чеченська Республіка",
                        'Ульяновская область': "Ульянівська область",
                        'Пензенская область': "Пензенська область",
                        'Ивановская область': "Іванівська область",
                        'Смоленская область': "Смоленська область",
                        'Калининградская область': "Калінінградська область",
                        'Астраханская область': "Астраханська область",
                        'Алтайский край': "Алтайський край",
                        'Белгородская область': "Білгородська область",
                        'Ханты-Мансийский АО': "Ханти-Мансійський авт. округ",
                        'Республика Бурятия': "Республіка Бурятія",
                        'Карачаево-Черкесская Республика': "Карачаєво-Черкеська Республіка",
                        'Новгородская область': "Новгородська область",
                        'Республика Саха (Якутия)': "Республіка Саха (Якутія)",
                        'Республика Калмыкия': "Республіка Калмикія",
                        'Архангельская область': "Архангельська область",
                        'Республика Хакасия': "Республіка Хакасія",
                        'Камчатский край': "Камчатський край",
                        'Удмуртская Республика': "Удмуртська Республіка",
                        'Костромская область': "Костромська область",
                        'Псковская область': "Псковська область",
                        'Забайкальский край': "Забайкальський край",
                        'Иркутская область': "Іркутська область",
                        'Вологодская область': "Вологодська область",
                        'Омская область': "Омська область",
                        'Республика Адыгея': "Республіка Адигея",
                        'Кемеровская область': "Кемеровська область",
                        'Томская область': "Томська область",
                        'Еврейская автономная область': "Єврейська автономна область",
                        'Магаданская область': "Магаданська область",
                        'Республика Карелия': "Республіка Карелія",
                        'Амурская область': "Амурська область",
                        'Курганская область': "Курганська область",
                        'Республика Тыва': "Республіка Тива (Тува)",
                        'Ненецкий автономный округ': "Ненецький авт. округ",
                        'Сахалинская область': "Сахалінська область",
                        'Чукотский автономный округ': "Чукотський авт. округ",
                        'Республика Алтай': "Республіка Алтай"}

        # occupied regions
        occupied_regions = {'Республика Крым': ['Україна', 'Автономна Республіка Крим'],
                            'Севастополь': ['Україна', 'м. Севастополь']}

        reg_node = self._html_get_node(page, './/cv-spread-overview', nid=0)
        regions = json.loads(reg_node.attrib.get(':spread-data', '[]'))

        # get regions. skip first two general nodes
        for region in regions:
            reg = region['title'].strip()
            reg_name = name_mapping.get(reg, reg)

            if reg_name in occupied_regions:
                # special processing for occupied regions
                curr_date = date.today().strftime("%d %b %Y")
                db = self.db.get({'date': curr_date,
                                  'country': occupied_regions[reg_name][0]})
                db['Regions'][occupied_regions[reg_name][1]] = int(region['sick'])
                self.db.update({'date': curr_date,
                                'country': occupied_regions[reg_name][0]}, db)
                continue

            sick = int(region['sick'])
            config['Regions'][reg_name] = sick

        return config

    def _upd_hug(self):
        config = {'Name': 'Угорщина', 'Code': 'hug', 'ViewBoxSz': '0 0 630 400',
                  'Population': 9797561, 'Area': 93030,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {}}

        config = self.__upd_hug_total(config)
        config = self.__upd_hug_regions(config)

        return config

    def __upd_hug_total(self, config):
        # news.google.com
        self.logger.normal(' - Збір загальних даних з news.google.com ..')
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F03gj2')

        total_info = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr')[1]
        sick = total_info.xpath('.//td')[0].text.strip().replace('\xa0', '')
        config['Sick'] = int(sick) if sick != '—' else 0

        recv = total_info.xpath('.//td')[2].text.strip().replace('\xa0', '')
        config['Recovered'] = int(recv) if sick != '—' else 0

        dead = total_info.xpath('.//td')[3].text.strip().replace('\xa0', '')
        config['Dead'] = int(dead) if sick != '—' else 0

        page = self._web_request('https://koronavirus.gov.hu/')
        tested = self._html_get_node(page, './/div[@id="api-mintavetel"]')[0]
        config['Tested'] = int(tested.text.replace(' ', ''))
        return config

    def __upd_hug_regions(self, config):
        # news.google.com
        self.logger.normal(' - Збір даних про регіони з news.google.com ..')
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F03gj2')

        # initial regions data
        initial = ['Медьє Бач-Кишкун', 'Медьє Бараня',
                   'Медьє Бекеш', 'Медьє Боршод-Абауй-Земплен',
                   'Медьє Чонґрад', 'Медьє Феєр',
                   'Медьє Дьйор-Мошон-Шопрон', 'Медьє Гайду-Бігар',
                   'Медьє Гевеш', 'Медьє Яс-Надькун-Сольнок',
                   'Медьє Комаром-Естерґом', 'Медьє Ноґрад',
                   'Медьє Пешт', 'Медьє Шомодь',
                   'Медьє Саболч-Сатмар-Береґ', 'Медьє Толна',
                   'Медьє Ваш', 'Медьє Веспрем',
                   'Медьє Зала', 'м. Будапешт']
        config['Regions'] = {k: 0 for k in initial}

        # used to store data under better regions naming
        name_mapping = {'Будапешт': 'м. Будапешт',
                        'Пешт': 'Медьє Пешт',
                        'Фейер': 'Медьє Феєр',
                        'Комаром-Естерґом': 'Медьє Комаром-Естерґом',
                        'Зала': 'Медьє Зала',
                        'Чонґрад': 'Медьє Чонґрад',
                        'Дьйор-Мошон-Шопрон': 'Медьє Дьйор-Мошон-Шопрон',
                        'Боршод-Абауй-Земплєн': 'Медьє Боршод-Абауй-Земплен',
                        'Веспрем': 'Медьє Веспрем',
                        'Сабольч-Сатмар-Берег': 'Медьє Саболч-Сатмар-Береґ',
                        'Баранья': 'Медьє Бараня',
                        'Шомодь': 'Медьє Шомодь',
                        'Ноґрад': 'Медьє Ноґрад',
                        'Хайду-Біхар': 'Медьє Гайду-Бігар',
                        'Бач-Кі́шкун': 'Медьє Бач-Кишкун',
                        'Яс-Надькун-Сольнок': 'Медьє Яс-Надькун-Сольнок',
                        'Толна': 'Медьє Толна',
                        'Бекес': 'Медьє Бекеш',
                        'Хевеш': 'Медьє Гевеш',
                        'Ваш': 'Медьє Ваш'}

        # get regions. skip first two general nodes
        regions = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr')[2:]
        for region in regions:
            reg = region.xpath('.//th//div//span')[0].text
            reg_name = name_mapping.get(reg, reg)

            sick = region.xpath('.//td')[0].text.strip().replace('\xa0', '')
            config['Regions'][reg_name] = int(sick) if sick != '—' else 0

        return config

    def __str__(self):
        ''' Show COVID information '''
        # get input data
        data_today = self.db.get({'date': date.today().strftime("%d %b %Y")})
        data_yestd = self.db.get({'date': (date.today() - timedelta(days=1)).strftime("%d %b %Y")})

        # datetime object containing current date and time
        curr_date = '\n * Дані станом на {:%d %B %Y [%H:%M:%S]}\n'.format(datetime.now())
        text = self.translate('eng', 'ukr', curr_date)

        for country, cfg in data_today.items():
            # yesterday configuration
            ycfg = data_yestd.get(country, cfg)

            # sort regions
            regions = {k: v for k, v in sorted(cfg['Regions'].items(),
                                               key=lambda it: it[1],
                                               reverse=True)}

            # sort regions delta
            rd = {k: v - ycfg['Regions'].get(k, v) for k, v in cfg['Regions'].items()}
            rd_sick = {k: v for k, v in sorted(rd.items(),
                                               key=lambda it: it[1],
                                               reverse=True)}

            # country information
            text += '\n   [ %s ] ' % colour.set(colour.fg.cyan, country)
            text += 'Населення {:,} людей на {:,} км2 ({:.2f} л/км2)\n' \
                    .format(cfg['Population'], cfg['Area'],
                            cfg['Population'] / cfg['Area'])

            # total information
            text += ' .{:-<76}.\n'.format('')
            block = '   {:>10} | {:^20} | {:<+7}  {:>10} | {:^20} | {:<+7}\n'

            d_test = cfg['Tested'] - ycfg.get('Tested', cfg['Tested'])
            d_recv = cfg['Recovered'] - ycfg.get('Recovered', cfg['Recovered'])
            text += block.format(cfg['Tested'], colour.set(colour.fg.grey, 'Перевірені'), d_test,
                                 cfg['Recovered'], colour.set(colour.fg.green, 'Одужали'), d_recv)

            d_sick = cfg['Sick'] - ycfg.get('Sick', cfg['Sick'])
            d_dead = cfg['Dead'] - ycfg.get('Dead', cfg['Dead'])
            text += block.format(cfg['Sick'], colour.set(colour.fg.yellow, 'Хворі'), d_sick,
                                 cfg['Dead'], colour.set(colour.fg.red, 'Померли'), d_dead)

            # separator
            text += ' +{:-<76}+\n'.format('')

            # regions information
            if regions:
                # 5 zones coloured by unique colour
                zones = {0: colour.fg.white, 1: colour.fg.yellow,
                         2: colour.fg.orange, 3: colour.fg.lightred,
                         4: colour.fg.red}
                min_sick = min(regions.values())
                sick_step = (max(regions.values()) + 1 - min_sick) / 5

                min_rdsick = min(rd_sick.values())
                rdsick_step = (max(rd_sick.values()) + 1 - min_rdsick) / 5

                text += '   Рівні небезпеки: %s\n' % ' '.join(colour.set(zones[i], str(i)) for i in range(5))
                text += ' +{:-<76}+\n'.format('')

                for region, sick in regions.items():
                    # depending of the value, region will have its colour
                    clr = zones[(rd_sick[region] - min_rdsick) // rdsick_step]
                    ysick = colour.set(clr, '%+d' % rd_sick[region])

                    clr = zones[(sick - min_sick) // sick_step]
                    region = colour.set(clr, region) + ' '
                    text += '   {:.<68} {:<6} | {:<5}\n'.format(region, sick, ysick)

            else:
                text += '   << Немає даних по регіонах >>\n'

            text += ' \'{:-<76}\'\n'.format('')

        return text

    def translate(self, slang, dlang, msg):
        tokens_base = self._vocab.get(slang, {}).get(dlang, {})

        for token, translation in tokens_base.items():
            msg = msg.replace(token, translation)

        return msg

    def _html_report(self):
        ''' Export data to HTML web page '''
        # define templates for complex nodes
        total_tmpl = '{}<div id="total{}" title="{}" tested="{}" d_tested="{}" sick="{}" d_sick="{}" recovered="{}" d_recovered="{}" dead="{}" d_dead="{}" style="display: none;"></div>\n'
        country_tmpl = \
            '            <div class="tab">\n' \
            '                <input type="radio" name="tabgroup" id="{0}" onclick="country_changed(\'{0}\')" autocomplete="off" {1}>\n' \
            '                <label for="{0}">{2}{3}</label>\n' \
            '                <div class="tab_content">\n' \
            '                    <svg id="map" viewBox="{4}">\n' \
            '                        <g>\n' \
            '{5}\n' \
            '                        </g>\n' \
            '                    </svg>\n' \
            '                </div>\n' \
            '            </div>\n'
        region_tmpl = '{}<path title="{}" tested="{}" sick="{}" recovered="{}" dead="{}"style="fill: rgb({}, {}, {});" class="land enabled" onclick="copy_info()" d="{}"/>\n'
        vii_tmpl = '<span class="vi_info" onclick="notify(\'{}\', 15000);">☣️</span>'

        # create htmlWorker object
        html = htmlWorker('./report/report.html', './report/index.html')

        # config for rendering
        render_cfg = {}
        updated = ''
        total = ''
        regions = ''
        checked = 'checked'
        tab = '    '

        # get current date
        curr_date = date.today().strftime("%d %b %Y")

        # upload paths for regions
        with open('./report/regions.map', 'r+') as fp:
            regions_map = json.load(fp)

        # get data for current date
        today_data = self.db.get({'date': curr_date})
        yestd_data = self.db.get({'date': (date.today() - timedelta(days=1)).strftime("%d %b %Y")})

        # stage 1 - date of latest data update
        updated = self.translate('eng', 'ukr', curr_date)

        # configure default information
        default = today_data.get('Україна')
        y_default = yestd_data.get('Україна')
        total = total_tmpl.format(tab * 2, '', default['Name'],
                                  default['Tested'], default['Tested'] - y_default.get('Tested', 0),
                                  default['Sick'],   default['Sick'] - y_default.get('Sick', 0),
                                  default['Recovered'], default['Recovered'] - y_default.get('Recovered', 0),
                                  default['Dead'], default['Dead'] - y_default.get('Dead', 0))

        for country, data in today_data.items():
            y_data = yestd_data.get(country, {})
            # stage 2 - prepare total info for the country
            total += total_tmpl.format(tab * 2, '_%s' % data['Code'], data['Name'],
                                       data['Tested'], data['Tested'] - y_data.get('Tested', 0),
                                       data['Sick'], data['Sick'] - y_data.get('Sick', 0),
                                       data['Recovered'], data['Recovered'] - y_data.get('Recovered', 0),
                                       data['Dead'], data['Dead'] - y_data.get('Dead', 0))

            # stage 3 - regions data
            # max_sick = max(data['Regions'].values())
            # max_sick = sum(data['Regions'].values()) / len(data['Regions'].values())
            max_sick = 2000
            color_step = (max_sick / 256) or 1

            _regions = ''
            for region, path in regions_map[data['Name']].items():
                # get number of sick people in region
                sick = data['Regions'].get(region, '—')
                sick = sick if sick else '—'

                # stub for the future development
                test = '—'
                recv = '—'
                dead = '—'

                # calculate color
                aux_colour = int(255 - ((0 if sick == '—' else sick) / color_step))
                rgb = (255, aux_colour, aux_colour)

                _regions += region_tmpl.format(tab * 7, region, test, sick,
                                               recv, dead, *rgb, path)

            # strip redundant newline
            _regions = _regions.rstrip()

            # prepare very important information (vii)
            vii = vii_tmpl.format(data['vii']) if data.get('vii') else ''

            # form data per country
            regions += country_tmpl.format(data['Code'], checked,
                                           data['Name'], vii,
                                           data['ViewBoxSz'],
                                           _regions)
            checked = ''

        # strip redundant newline
        regions = regions.rstrip()
        total = total.rstrip()

        # prepare data for rendering
        render_cfg = {'updated': updated, 'regions': regions, 'total': total}

        # render and save
        html.render(render_cfg)
        html.save()

    def _login(self):
        ''' Get login data from the user

        :return: username and password
        '''
        try:
            username = input(' [запит даних] > ім\'я користувача: ')
            password = getpass(' [запит даних] > пароль %s: ' % username)
        except KeyboardInterrupt:
            self.logger.print('', end='\n')
            self.logger.debug('Дані користувача не надано')
            return (None, None)

        return (username, password)

    def _ftp_upload(self, srcfile):
        with open(srcfile, 'rb') as f:
            self.ftp.storbinary('STOR %s' % os.path.basename(srcfile), f, 1024)
        self.logger.debug('Файл "%s" вивантажено' % srcfile)

    def webpage_update(self, server):
        ''' Update web-page files through FTP server '''
        # generate HTML report
        self.logger.normal('Генерування веб-сторінки ..')
        self._html_report()
        self.logger.success('Веб-сторінку згенеровано')

        # run web files upload
        self.logger.normal('Оновлення веб-сторінки розпочато ..')

        # get user data
        uname, upass = self._login()
        if not (uname and upass):
            self.logger.warning('Оновлення веб-сторінки скасовано')
            return

        # setup FTP connection
        self.ftp.connect(server, 21)
        self.ftp.login(uname, upass)

        # configure copy destination
        self.ftp.cwd('/covidinfo.zzz.com.ua')

        # prepare copy list
        web_files = ['./report/index.html',
                     './report/report.css',
                     './report/report.js',
                     './report/virus.png']

        # copy files
        for wfile in web_files:
            self._ftp_upload(wfile)

        self.logger.success('Веб-сторінку "%s" оновлено' % server)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--web_update',  action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')

    args = parser.parse_args()

    covid = iCovid(debug=args.debug)
    covid.update()

    if args.web_update:
        covid.webpage_update('covidinfo.zzz.com.ua')

    print(covid)


if __name__ == '__main__':
    main()
