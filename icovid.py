#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '1.3.4'
__release__ = '02 Jul 2020'
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

    def get_dates_list(self):
        """ Function return list of known dates

        Returns:
            list: all the known dates
        """
        return self.__db.keys()

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

    def _web_request(self, url, headers={}):
        ''' Function perform HTML page request

        :param url: URL to webpage
        :return: 'utf-8'-encoded HTML page
        '''
        html = requests.get(url, headers=headers).text

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
        upd_cbs = [self._upd_ukr, self._upd_ulv, self._upd_isr, self._upd_pol,
                   self._upd_rus, self._upd_hug, self._upd_rom]

        # slovakia - https://korona.gov.sk/en/coronavirus-covid-19-in-the-slovak-republic-in-numbers/

        curr_date = datetime.now().strftime("%d %b %Y")

        self.logger.normal('Оновлюємо дані ..')
        for upd_cb in upd_cbs:
            try:
                data = upd_cb()
                self.db.update({'date': curr_date, 'country': data['Name']}, data)
                self.logger.success('Дані з {} оновлені'.format(data['Name']))
            except Exception as e:
                self.logger.error('Помилка при оновленні даних: {}'.format(upd_cb))
                raise e
                continue

    def _upd_ukr(self):
        config = {'Name': 'Україна', 'Code': 'ukr',
                  'ViewBoxSz': '0 0 640 410', 'ViewBoxLineSz': 0.7,
                  'Population': 43762985, 'Area': 603628,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 4000, 'Regions': {}}

        config = self.__upd_ukr_total(config)
        config = self.__upd_ukr_regions(config)

        return config

    def __upd_ukr_total(self, config):
        # covid19.gov.ua
        self.logger.normal(' - Збір загальних даних з covid19.gov.ua ..')
        page = self._web_request('https://covid19.gov.ua/en/')

        divs = self._html_get_node(page, './/div[@class="one-field light-box info-count"]')
        if len(divs) != 4:
            self.logger.error('Неочікуване число елементів - %d' % len(divs))
            exit(1)

        for i, case in enumerate(['Tested', 'Sick', 'Dead', 'Recovered']):
            config[case] = int(divs[i].xpath('.//div')[0].text.strip().replace(' ', ''))

        return config

    def __upd_ukr_regions(self, config):
        # moz.gov.ua
        # detailed - https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/
        self.logger.normal(' - Збір даних про регіони з index.minfin.com.ua ..')
        page = self._web_request('https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/')

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

        # used to store data under better regions naming
        name_mapping = {"Вінницька": "Вінницька область",
                        "Волинська": "Волинська область",
                        "Дніпро­петровська": "Дніпропетровська область",
                        "Донецька": "Донецька область",
                        "Житомирська": "Житомирська область",
                        "Закарпатська": "Закарпатська область",
                        "Запорізька": "Запорізька область",
                        "Івано-Франківська": "Івано-Франківська область",
                        "Київська": "Київська область",
                        "Кірово­градська": "Кіровоградська область",
                        "Луганська": "Луганська область",
                        "Львівська": "Львівська область",
                        "Миколаївська": "Миколаївська область",
                        "Одеська": "Одеська область",
                        "Полтавська": "Полтавська область",
                        "Рівненська": "Рівненська область",
                        "Сумська": "Сумська область",
                        "Тернопільська": "Тернопільська область",
                        "Харківська": "Харківська область",
                        "Херсонська": "Херсонська область",
                        "Хмельницька": "Хмельницька область",
                        "Черкаська": "Черкаська область",
                        "Чернівецька": "Чернівецька область",
                        "Чернігівська": "Чернігівська область",
                        "м.Київ": "м. Київ"}

        rows = self._html_get_node(page, './/div[@class="compact-table expand-table"]//table//tr')
        for row in rows:
            items = row.xpath('.//td')
            if len(items) == 0:
                continue
            elif items[0].text in name_mapping:
                config['Regions'][name_mapping.get(items[0].text, items[0].text)] = int(items[1].text)

        return config

    def _upd_ulv(self):
        config = {'Name': 'Львівщина', 'Code': 'ulv',
                  'ViewBoxSz': '0 0 1300 1300', 'ViewBoxLineSz': 2,
                  'Population': 2529608, 'Area': 21833,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 500, 'Regions': {},
                  'vii': '☣️ Нажаль, немає постійного джерела даних для Львівщини.<br><br>👉 Наразі дані оновлюються вручну щоденно.'}

        config = self.__upd_ulv_total(config)
        config = self.__upd_ulv_regions(config)

        return config

    def __upd_ulv_total(self, config):
        # covid19.gov.ua
        self.logger.normal(' - Збір загальних даних з index.minfin.com.ua ..')
        page = self._web_request('https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/')

        rows = self._html_get_node(page, './/div[@class="compact-table expand-table"]//table//tr')
        for row in rows:
            items = row.xpath('.//td')
            if len(items) == 0:
                continue
            elif items[0].text == 'Львівська':
                config['Sick'] = int(items[1].text)
                config['Dead'] = int(items[3].text)
                config['Recovered'] = int(items[5].text)

        tested_links = ['https://portal.lviv.ua/news/2020/06/01/covid-19-na-lvivshchyni-karta-poshyrennia-po-rajonakh',
                        'https://portal.lviv.ua/news/2020/06/02/v-iakykh-rajonakh-lvivshchyny-najbilshe-khvorykh-na-covid-19-karta-poshyrennia',
                        'https://portal.lviv.ua/news/2020/06/03/novyj-antyrekord-lvivshchyny-za-dobu-vyiavyly-96-khvorykh-na-koronavirus',
                        'https://portal.lviv.ua/news/2020/06/04/covid-19-na-lvivshchyni-85-khvorykh-za-dobu',
                        'https://portal.lviv.ua/news/2020/06/05/koronavirusom-zarazylysia-majzhe-2000-meshkantsiv-lvivshchyny',
                        'https://portal.lviv.ua/news/2020/06/07/koronavirus-na-lvivshchyni-68-novykh-khvorykh',
                        'https://portal.lviv.ua/news/2020/06/08/na-lvivshchyni-vzhe-73-letalni-vypadky-cherez-covid-19',
                        'https://portal.lviv.ua/news/2020/06/09/covid-19-na-lvivshchyni-za-dobu-vyiavyly-49-khvorykh',
                        'https://portal.lviv.ua/news/2020/06/10/2289-vypadkiv-covid-19-na-lvivshchyni-de-najbilshe-khvorykh',
                        'https://portal.lviv.ua/news/2020/06/11/chomu-u-rajonakh-lvivshchyny-liudy-menshe-khvoriiut-na-koronavirus-poiasnennia-epidemioloha',
                        'https://portal.lviv.ua/news/2020/06/12/novi-vypadky-covid-19-na-lvivshchyni-zvidky-khvori',
                        'https://portal.lviv.ua/news/2020/06/13/koronavirusnyj-antyrekord-na-lvivshchyni-za-dobu-132-novykh-khvorykh',
                        'https://portal.lviv.ua/news/2020/06/14/za-dobu-vid-koronavirusu-na-lvivshchyni-pomer-cholovik-ta-troie-zhinok',
                        'https://portal.lviv.ua/news/2020/06/15/de-na-lvivshchyni-najbilshe-khvorykh-na-koronavirus',
                        'https://portal.lviv.ua/news/2020/06/16/lviv-nadali-lidyruie-v-oblasti-za-kilkistiu-khvorykh-na-covid-19',
                        'https://portal.lviv.ua/news/2020/06/17/3227-vypadkiv-covid-19-na-lvivshchyni-de-najbilshe-khvorykh',
                        'https://portal.lviv.ua/news/2020/06/18/koronavirus-na-lvivshchyni-karta-poshyrennia-po-rajonakh-oblasti',
                        'https://portal.lviv.ua/news/2020/06/19/na-lvivshchyni-vyiavleno-3540-vypadkiv-infikuvannia-covid-19',
                        'https://portal.lviv.ua/news/2020/06/20/koronavirus-pidkhopyly-3679-meshkantsiv-lvivshchyny',
                        'https://portal.lviv.ua/news/2020/06/21/covid-19-na-lvivshchyni-za-dobu-sotnia-novykh-vypadkiv-zvidky-khvori',
                        'https://portal.lviv.ua/news/2020/06/22/u-lvovi-vzhe-ponad-2300-liudej-zakhvorily-na-koronavirus',
                        'https://portal.lviv.ua/news/2020/06/23/4220-vypadkiv-covid-19-na-lvivshchyni-karta-poshyrennia-po-rajonakh',
                        'https://portal.lviv.ua/news/2020/06/24/koronavirus-na-lvivshchyni-pidtverdyly-u-shche-203-liudej',
                        'https://portal.lviv.ua/news/2020/06/25/koronavirus-na-lvivshchyni-karta-poshyrennia-rajonamy',
                        'https://portal.lviv.ua/news/2020/06/26/na-lvivshchyni-vyiavyly-ponad-200-novykh-vypadkiv-koronavirusu',
                        'https://portal.lviv.ua/news/2020/06/27/u-lvovi-vyiavyly-vzhe-ponad-2-5-tysiachi-khvorykh-na-covid-19',
                        'https://portal.lviv.ua/news/2020/06/28/covid-19-na-lvivshchyni-karta-poshyrennia-po-rajonakh',
                        'https://portal.lviv.ua/news/2020/06/29/koronavirus-na-lvivshchyni-115-novykh-khvorykh-oduzhaly-bilshe-700-liudej',
                        'https://portal.lviv.ua/news/2020/06/30/covid-19-na-lvivshchyni-plius-143-novykh-khvorykh',
                        'https://portal.lviv.ua/news/2020/07/01/koronavirus-na-lvivshchyni-za-dobu-143-novykh-khvorykh',
                        'https://portal.lviv.ua/news/2020/07/02/covid-19-na-lvivshchyni-za-dobu-vyiavyly-152-khvorykh']

        ''' Commented due to manual updates
        page = self._web_request(tested_links[0])
        tested_p = self._html_get_node(page, './/div[@class="article-content"]//p')[3]
        '''

        # manual update
        config['Tested'] = 33197  # int(''.join(tested_p.text.split()[7:9]))

        return config

    def __upd_ulv_regions(self, config):
        # moz.gov.ua
        # detailed - https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/
        self.logger.normal(' - Збір даних про регіони з portal.lviv.ua ..')
        #page = self._web_request(tested_links[0])

        # initial regions data
        initial = ["Бродівський район", "Буський район",
                   "Городоцький район", "Дрогобицький район",
                   "Жидачівський район", "Жовківський район",
                   "Золочівський район", "Кам'янка-Бузький район",
                   "Миколаївський район", "Мостиський район",
                   "Перемишлянський район", "Пустомитівський район",
                   "Радехівський район", "Самбірський район",
                   "Сколівський район", "Сокальський район",
                   "Старосамбірський район", "Стрийський район",
                   "Турківський район", "Яворівський район",
                   "м. Львів"]
        config['Regions'] = {k: 0 for k in initial}

        ''' Commented due to manual updates
        litems = self._html_get_node(page, './/div[@class="article-content"]//ol//li')
        for litem in litems:
            reg, sick = litem.text.replace(';', '').replace('’', '\'').split('–')[:2]
            reg = reg.strip()
            sick = int(sick.replace(',', ' ').replace('.', ' ').split()[0])

            if reg == 'м. Червоноград':
                config['Regions']['Сокальський район'] += sick

            if reg in initial:
                config['Regions'][reg] = sick
        '''

        # manual update
        config['Regions'] = {
                "Бродівський район": 56,
                "Буський район": 44,
                "Городоцький район": 170,
                "Дрогобицький район": 96,  # Борислав, Стебник, Дрогобич, Трускавець
                "Жидачівський район": 50,
                "Жовківський район": 331,
                "Золочівський район": 38,
                "Кам'янка-Бузький район": 191,
                "Миколаївський район": 160,  # Новий Розділ
                "Мостиський район": 43,
                "Перемишлянський район": 75,
                "Пустомитівський район": 570,
                "Радехівський район": 24,
                "Самбірський район": 44,  # Самбір
                "Сколівський район": 16,
                "Сокальський район": 224,  # Червоноград
                "Старосамбірський район": 7,
                "Стрийський район": 85,  # Моршин, Стрий
                "Турківський район": 42,
                "Яворівський район": 412,
                "м. Львів": 3041
            }

        return config

    def _upd_isr(self):
        config = {'Name': 'Ізраїль', 'Code': 'isr',
                  'ViewBoxSz': '0 0 250 800', 'ViewBoxLineSz': 1.0,
                  'Population': 8638917, 'Area': 20770,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 6000, 'Regions': {},
                  'vii': '☣️ Дані з регіонів Ізраїлю відсутні у відкритому доступі.<br><br>👉 Публікація останніх відкритих даних відбулась 30 квітня 2020 року.<br><br>👉 Регіональний розподіл виконаний рівномірно на основі розподілу кількості населення у регіонах.'}

        # https://data.gov.il/dataset/covid-19/resource/d07c0771-01a8-43b2-96cc-c6154e7fa9bd
        # https://data.gov.il/dataset/covid-19/resource/dcf999c1-d394-4b57-a5e0-9d014a62e046#collapse-endpoints
        # https://coronaupdates.health.gov.il/

        config = self.__upd_isr_total(config)
        config = self.__upd_isr_regions(config)

        return config

    def __upd_isr_total(self, config):
        # govextra.gov.il
        # Palestine: https://corona.ps/
        self.logger.normal(' - Збір загальних даних з worldometers.info ..')
        page = self._web_request('https://www.worldometers.info/coronavirus/')

        data = None
        countries = self._html_get_node(page, './/table[@id="main_table_countries_today"]/tbody/tr')
        for country in countries:
            nodes = country.xpath('.//td//a')

            # check if there is name of country and it is Poland
            if len(nodes) > 0 and nodes[0].text == 'Israel':
                data = country
                break

        config['Sick'] = int(country.xpath('.//td')[2].text.replace(',', ''))
        config['Dead'] = int(country.xpath('.//td')[4].text.replace(',', ''))
        config['Recovered'] = int(country.xpath('.//td')[6].text.replace(',', ''))
        config['Tested'] = int(country.xpath('.//td')[12].text.replace(',', ''))

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

        # Населення Ізраїлю
        # Єрусалим         - 1 075 900 / 8 638 917 = 12.45
        # Центральний      - 2 108 700 / 8 638 917 = 24.41
        # Тель-Авів        - 1 381 300 / 8 638 917 = 15.99
        # Північний округ  - 1 394 200 / 8 638 917 = 16.14
        # Південний округ  - 1 237 100 / 8 638 917 = 14.32
        # Хайвський округ  -   989 200 / 8 638 917 = 11.45
        # Голанські Висоти -    49 700 / 8 638 917 =  0.58
        # Палестина        -   402 817 / 8 638 917 =  4.66
        pop_per_district = {
                'Єрусалимський округ': 12.45,
                'Центральний округ (Хамерказ)': 24.41,
                'Тель-Авівський округ': 15.99,
                'Північний округ (Хацафон)': 16.14,
                'Південний округ (Хадаром)': 14.32,
                'Хайфський округ (Хейфа)': 11.45,
                'Голанські Висоти': 0.58,
                'Палестина': 4.66
            }

        config['Regions'] = {k: int(v * config['Sick'] / 100.0) for k, v in pop_per_district.items()}

        # MANUAL. DAILY.
        # This data is unavailable in public web-sites. Actual for 30 Apr 2020.
        # config['Regions'] = {
        #     'Єрусалимський округ': 2418,
        #     'Центральний округ (Хамерказ)': 1524,
        #     'Тель-Авівський округ': 483,
        #     'Північний округ (Хацафон)': 400,
        #     'Південний округ (Хадаром)': 310,
        #     'Хайфський округ (Хейфа)': 142,
        #     'Голанські Висоти': 0,
        #     'Палестина': 0
        # }

        # update Palestine separately
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F01k0p4')

        palestine = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr', nid=1)
        sick = palestine.xpath('.//td')[0].text.strip().replace('\xa0', '')
        config['Regions']['Палестина'] = int(sick)

        return config

    def _upd_pol(self):
        config = {'Name': 'Польща', 'Code': 'pol',
                  'ViewBoxSz': '0 0 650 600', 'ViewBoxLineSz': 0.8,
                  'Population': 37851327, 'Area': 312679,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 4000, 'Regions': {}}

        config = self.__upd_pol_total(config)
        config = self.__upd_pol_regions(config)

        return config

    def __upd_pol_total(self, config):
        # news.google.com
        self.logger.normal(' - Збір загальних даних з worldometers.info ..')
        page = self._web_request('https://www.worldometers.info/coronavirus/')

        data = None
        countries = self._html_get_node(page, './/table[@id="main_table_countries_today"]/tbody/tr')
        for country in countries:
            nodes = country.xpath('.//td//a')

            # check if there is name of country and it is Poland
            if len(nodes) > 0 and nodes[0].text == 'Poland':
                data = country
                break

        config['Sick'] = int(country.xpath('.//td')[2].text.replace(',', ''))
        config['Dead'] = int(country.xpath('.//td')[4].text.replace(',', ''))
        config['Recovered'] = int(country.xpath('.//td')[6].text.replace(',', ''))
        config['Tested'] = int(country.xpath('.//td')[12].text.replace(',', ''))

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
            reg = region.xpath('.//th//div//div')[0].text
            reg_name = name_mapping.get(reg, reg)

            sick = region.xpath('.//td')[0].text.strip().replace('\xa0', '')
            config['Regions'][reg_name] = int(sick) if sick != '—' else 0

        return config

    def _upd_rus(self):
        config = {'Name': 'Московія', 'Code': 'rus',
                  'ViewBoxSz': '0 0 1250 800', 'ViewBoxLineSz': 0.8,
                  'Population': 145927292, 'Area': 17098246,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 8000, 'Regions': {}}

        config = self.__upd_rus_total(config)
        config = self.__upd_rus_regions(config)

        return config

    def __upd_rus_total(self, config):
        # news.google.com
        # https://covid.ourworldindata.org/data/owid-covid-data.json
        self.logger.normal(' - Збір загальних даних з covid19.rosminzdrav.ru ..')
        page = self._web_request('https://covid19.rosminzdrav.ru/wp-json/api/mapdata/')
        data = json.loads(page)['Items']

        config['Tested'] = sum([it['Observations'] for it in data])
        config['Sick'] = sum([it['Confirmed'] for it in data])
        config['Recovered'] = sum([it['Recovered'] for it in data])
        config['Dead'] = sum([it['Deaths'] for it in data])

        return config

    def __upd_rus_regions(self, config):
        # news.google.com
        self.logger.normal(' - Збір даних про регіони з covid19.rosminzdrav.ru ..')
        page = self._web_request('https://covid19.rosminzdrav.ru/wp-json/api/mapdata/')
        data = json.loads(page)['Items']

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
                        'Дагестан': "Республіка Дагестан",
                        'Мурманская область': "Мурманська область",
                        'Краснодарский край': "Краснодарський край",
                        'Тульская область': "Тульська область",
                        'Ростовская область': "Ростовська область",
                        'Свердловская область': "Свердловська область",
                        'Калужская область': "Калузька область",
                        'Брянская область': "Брянська область",
                        'Татарстан': "Республіка Татарстан",
                        'Рязанская область': "Рязанська область",
                        'Северная Осетия': "Республіка Північна Осетія - Аланія",
                        'Ленинградская область': "Ленінградська область",
                        'Башкортостан': "Республіка Башкортостан",
                        'Курская область': "Курська область",
                        'Тамбовская область': "Тамбовська область",
                        'Владимирская область': "Володимирська область",
                        'Ингушетия': "Республіка Інгушетія",
                        'Кабардино-Балкария': "Кабардино-Балкарська республіка",
                        'Мордовия': "Республіка Мордовія",
                        'Ямало-Ненецкий автономный округ': "Ямало-Ненетський авт. округ",
                        'Чувашия': "Республіка Чувашія",
                        'Ярославская область': "Ярославська область",
                        'Красноярский край': "Красноярський край",
                        'Саратовская область': "Саратовська область",
                        'Новосибирская область': "Новосибірська область",
                        'Ставропольский край': "Ставропольський край",
                        'Орловская область': "Орловська область",
                        'Челябинская область': "Челябінська область",
                        'Оренбургская область': "Оренбурзька область",
                        'Марий Эл': "Республіка Марій Ел",
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
                        'Чечня': "Чеченська Республіка",
                        'Ульяновская область': "Ульянівська область",
                        'Пензенская область': "Пензенська область",
                        'Ивановская область': "Іванівська область",
                        'Смоленская область': "Смоленська область",
                        'Калининградская область': "Калінінградська область",
                        'Астраханская область': "Астраханська область",
                        'Алтайский край': "Алтайський край",
                        'Белгородская область': "Білгородська область",
                        'Ханты-Мансийский автономный округ — Югра': "Ханти-Мансійський авт. округ",
                        'Бурятия': "Республіка Бурятія",
                        'Карачаево-Черкесия': "Карачаєво-Черкеська Республіка",
                        'Новгородская область': "Новгородська область",
                        'Якутия': "Республіка Саха (Якутія)",
                        'Калмыкия': "Республіка Калмикія",
                        'Архангельская область': "Архангельська область",
                        'Хакасия': "Республіка Хакасія",
                        'Камчатский край': "Камчатський край",
                        'Удмуртия': "Удмуртська Республіка",
                        'Костромская область': "Костромська область",
                        'Псковская область': "Псковська область",
                        'Забайкальский край': "Забайкальський край",
                        'Иркутская область': "Іркутська область",
                        'Вологодская область': "Вологодська область",
                        'Омская область': "Омська область",
                        'Адыгея': "Республіка Адигея",
                        'Кемеровская область': "Кемеровська область",
                        'Томская область': "Томська область",
                        'Еврейская автономная область': "Єврейська автономна область",
                        'Магаданская область': "Магаданська область",
                        'Карелия': "Республіка Карелія",
                        'Амурская область': "Амурська область",
                        'Курганская область': "Курганська область",
                        'Тыва': "Республіка Тива (Тува)",
                        'Ненецкий автономный округ': "Ненецький авт. округ",
                        'Сахалинская область': "Сахалінська область",
                        'Чукотский автономный округ': "Чукотський авт. округ",
                        'Республика Алтай': "Республіка Алтай"}

        # occupied regions
        occupied_regions = {'Крым': ['Україна', 'Автономна Республіка Крим'],
                            'Севастополь': ['Україна', 'м. Севастополь']}

        for reg_data in data:
            reg = reg_data['LocationName']

            # check if region name is valid
            if reg not in name_mapping and reg not in occupied_regions:
                continue

            reg_name = name_mapping.get(reg, reg)

            if reg_name in occupied_regions:
                # special processing for occupied regions
                key = {'date': date.today().strftime("%d %b %Y"),
                       'country': occupied_regions[reg_name][0]}
                db = self.db.get(key)
                db['Regions'][occupied_regions[reg_name][1]] = reg_data['Confirmed']
                self.db.update(key, db)
                continue

            config['Regions'][reg_name] = reg_data['Confirmed']

        return config

    def _upd_hug(self):
        config = {'Name': 'Угорщина', 'Code': 'hug',
                  'ViewBoxSz': '0 0 630 400', 'ViewBoxLineSz': 0.7,
                  'Population': 9663123, 'Area': 93030,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 2000, 'Regions': {}}

        config = self.__upd_hug_total(config)
        config = self.__upd_hug_regions(config)

        return config

    def __upd_hug_total(self, config):
        # news.google.com
        self.logger.normal(' - Збір загальних даних з koronavirus.gov.hu ..')
        page = self._web_request('https://news.google.com/covid19/map?hl=uk&gl=UA&ceid=UA%3Auk&mid=%2Fm%2F03gj2')

        total_info = self._html_get_node(page, './/tbody[@class="ppcUXd"]//tr')[1]
        sick = total_info.xpath('.//td')[0].text.strip().replace('\xa0', '')
        config['Sick'] = int(sick) if sick != '—' else 0

        recv = total_info.xpath('.//td')[3].text.strip().replace('\xa0', '')
        config['Recovered'] = int(recv) if sick != '—' else 0

        dead = total_info.xpath('.//td')[4].text.strip().replace('\xa0', '')
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
            reg = region.xpath('.//th//div//div')[0].text
            reg_name = name_mapping.get(reg, reg)

            sick = region.xpath('.//td')[0].text.strip().replace('\xa0', '')
            config['Regions'][reg_name] = int(sick) if sick != '—' else 0

        return config

    def _upd_rom(self):
        config = {'Name': 'Румунія', 'Code': 'rom',
                  'ViewBoxSz': '200 350 260 450', 'ViewBoxLineSz': 0.7,
                  'Population': 19251921, 'Area': 238397,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 4000, 'Regions': {}}

        config = self.__upd_rom_total(config)
        config = self.__upd_rom_regions(config)

        return config

    def __upd_rom_total(self, config):
        # news.google.com
        self.logger.normal(' - Збір загальних даних з mae.ro ..')

        # headers required to get access to the mae.ro web-page
        hdrs = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

        # get intial page to find out final link with tested persond data
        page = self._web_request('http://www.mae.ro/node/51759', headers=hdrs)
        links = self._html_get_node(page, './/div[@class="art"]//p//a')

        # go through all available paragraphs and look for the link
        target_link = ''
        for link in links:
            if link.attrib.get('title', '').startswith('Buletin informativ'):
                target_link = 'http://www.mae.ro{}'.format(link.attrib['href'])
                break

        if target_link:
            self.logger.debug('Цільове посилання: {} ..'.format(target_link))
            # get the page with tested persons quanity
            page = self._web_request(target_link, headers=hdrs)
            paragraphs = self._html_get_node(page, './/div[@class="art"]//p')
            for p in paragraphs:
                if p.text and p.text.strip().endswith('teste.'):
                    config['Tested'] = int(p.text.split()[10].replace('.', ''))
                    break

        # get other data
        page = self._web_request('https://datelazi.ro/latestData.json')
        data = json.loads(page)['currentDayStats']

        config['Sick'] = data['numberInfected']
        config['Recovered'] = data['numberCured']
        config['Dead'] = data['numberDeceased']

        return config

    def __upd_rom_regions(self, config):
        # news.google.com
        self.logger.normal(' - Збір даних про регіони з datelazi.ro ..')
        page = self._web_request('https://datelazi.ro/latestData.json')
        data = json.loads(page)['currentDayStats']['countyInfectionsNumbers']

        # initial regions data
        initial = ['Повіт Алба', 'Повіт Арад', 'Повіт Арджеш', 'Повіт Бакеу',
                   'Повіт Бистриця-Несеуд', 'Повіт Біхор', 'Повіт Ботошань',
                   'Повіт Брашов', 'Повіт Бреїла', 'Повіт Бузеу', 'Повіт Васлуй',
                   'Повіт Вилча', 'Повіт Вранча', 'Повіт Галац', 'Повіт Горж',
                   'Повіт Джурджу', 'Повіт Димбовіца', 'Повіт Долж', 'Повіт Ілфов',
                   'Повіт Караш-Северін', 'Повіт Келераші', 'Повіт Клуж',
                   'Повіт Ковасна', 'Повіт Констанца', 'м. Бухарест',
                   'Повіт Марамуреш', 'Повіт Мехедінць', 'Повіт Муреш',
                   'Повіт Нямц', 'Повіт Олт', 'Повіт Прахова', 'Повіт Сату-Маре',
                   'Повіт Селаж', 'Повіт Сібіу', 'Повіт Сучавський',
                   'Повіт Телеорман', 'Повіт Тіміш', 'Повіт Тульча',
                   'Повіт Харгіта', 'Повіт Хунедоара', 'Повіт Яломіца',
                   'Повіт Ясси']
        config['Regions'] = {k: 0 for k in initial}

        # used to store data under better regions naming
        name_mapping = {'AB': 'Повіт Алба',
                        'AR': 'Повіт Арад',
                        'AG': 'Повіт Арджеш',
                        'BC': 'Повіт Бакеу',
                        'BN': 'Повіт Бистриця-Несеуд',
                        'BH': 'Повіт Біхор',
                        'BT': 'Повіт Ботошань',
                        'BV': 'Повіт Брашов',
                        'BR': 'Повіт Бреїла',
                        'BZ': 'Повіт Бузеу',
                        'VS': 'Повіт Васлуй',
                        'VL': 'Повіт Вилча',
                        'VN': 'Повіт Вранча',
                        'GL': 'Повіт Галац',
                        'GJ': 'Повіт Горж',
                        'GR': 'Повіт Джурджу',
                        'DB': 'Повіт Димбовіца',
                        'DJ': 'Повіт Долж',
                        'IF': 'Повіт Ілфов',
                        'CS': 'Повіт Караш-Северін',
                        'CL': 'Повіт Келераші',
                        'CJ': 'Повіт Клуж',
                        'CV': 'Повіт Ковасна',
                        'CT': 'Повіт Констанца',
                        'MM': 'Повіт Марамуреш',
                        'MH': 'Повіт Мехедінць',
                        'MS': 'Повіт Муреш',
                        'NT': 'Повіт Нямц',
                        'OT': 'Повіт Олт',
                        'PH': 'Повіт Прахова',
                        'SM': 'Повіт Сату-Маре',
                        'SJ': 'Повіт Селаж',
                        'SB': 'Повіт Сібіу',
                        'SV': 'Повіт Сучавський',
                        'TR': 'Повіт Телеорман',
                        'TM': 'Повіт Тіміш',
                        'TL': 'Повіт Тульча',
                        'HR': 'Повіт Харгіта',
                        'HD': 'Повіт Хунедоара',
                        'IL': 'Повіт Яломіца',
                        'IS': 'Повіт Ясси',
                        'B': 'м. Бухарест'}

        for region in data:
            reg_name = name_mapping.get(region, region)

            if region == '-':
                # unproceeded persons will be equally divided between regions
                unknown = data[region]
                self.logger.debug('Невідомий регіон у %d осіб' % unknown)

                # common shared number
                common = int(data[region] / len(config['Regions']))

                for r in config['Regions']:
                    if unknown == 0:
                        break

                    config['Regions'][r] += common + (1 if unknown > 0 else 0)
                    unknown -= 1

            if region not in name_mapping:
                continue

            config['Regions'][reg_name] = data[region]

        return config

    def __str__(self):
        ''' Show COVID information '''
        # get input data
        data_today = self.db.get({'date': date.today().strftime("%d %b %Y")})
        data_yestd = self.db.get({'date': (date.today() - timedelta(days=1)).strftime("%d %b %Y")})

        # datetime object containing current date and time
        curr_date = '\n * Дані станом на {:%d %b %Y [%H:%M:%S]}\n'.format(datetime.now())
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
        def make_history(country, days_to_show=14):
            """ Prepare dynamics data for chart drawing

            Args:
                country (str): Country name
                days_to_show (int, optional): Number of days to process. Defaults to 14.

            Returns:
                dict: History data
            """
            data = {'days': [], 'test': [], 'sick': [], 'recv': [], 'dead': []}

            for day in self.db.get_dates_list():
                info = self.db.get({'date': day, 'country': country})
                if not info:
                    continue

                data['days'].append('"%s"' % self.translate('eng', 'ukr', day).split()[0])
                data['test'].append('"%s"' % info['Tested'])
                data['sick'].append('"%s"' % info['Sick'])
                data['recv'].append('"%s"' % info['Recovered'])
                data['dead'].append('"%s"' % info['Dead'])

            for k, v in data.items():
                data[k] = '[%s]' % ', '.join(v[-days_to_show:])

            return data

        # define templates for complex nodes
        total_tmpl = '{}<div id="total{}" title="{}" peak="{}" tested="{}" d_tested="{}" sick="{}" d_sick="{}" recovered="{}" d_recovered="{}" dead="{}" d_dead="{}" data-days=\'{}\' data-test=\'{}\' data-sick=\'{}\' data-recv=\'{}\' data-dead=\'{}\' style="display: none;"></div>\n'
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
        region_tmpl = '{}<path title="{}" tested="{}" sick="{}" d_sick="{}" recovered="{}" dead="{}" style="fill: rgb({}, {}, {});{}" class="land enabled" onclick="copy_info()" d="{}"/>\n'
        path_style_tmpl = ' stroke:#000000; stroke-width:{}; stroke-linecap:butt; stroke-linejoin:round; stroke-opacity:1;'
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

        # prepare dynamics data
        hist = make_history('Україна', 14)

        # make default total data
        total = total_tmpl.format(tab * 2, '', default['Name'], default['Peak'],
                                  default['Tested'], default['Tested'] - y_default.get('Tested', 0),
                                  default['Sick'],   default['Sick'] - y_default.get('Sick', 0),
                                  default['Recovered'], default['Recovered'] - y_default.get('Recovered', 0),
                                  default['Dead'], default['Dead'] - y_default.get('Dead', 0),
                                  hist['days'], hist['test'], hist['sick'], hist['recv'], hist['dead'])


        for country, data in today_data.items():
            y_data = yestd_data.get(country, {})
            # prepare dynamics data
            hist = make_history(country, 14)

            # stage 2 - prepare total info for the country
            total += total_tmpl.format(tab * 2, '_%s' % data['Code'], data['Name'], data['Peak'],
                                       data['Tested'], data['Tested'] - y_data.get('Tested', 0),
                                       data['Sick'], data['Sick'] - y_data.get('Sick', 0),
                                       data['Recovered'], data['Recovered'] - y_data.get('Recovered', 0),
                                       data['Dead'], data['Dead'] - y_data.get('Dead', 0),
                                       hist['days'], hist['test'], hist['sick'], hist['recv'], hist['dead'])

            # stage 3 - regions data
            color_step = (data['Peak'] / 256) or 1
            path_style = path_style_tmpl.format(data['ViewBoxLineSz'])

            _regions = ''
            for region, path in regions_map[data['Name']].items():
                # get number of sick people in region
                sick = data['Regions'].get(region, 0)
                d_sick = sick - y_data['Regions'].get(region, sick)
                sick = sick if sick else '—'

                # stub for the future development
                test = '—'
                recv = '—'
                dead = '—'

                # calculate color
                aux_colour = int(255 - ((0 if sick == '—' else sick) / color_step))
                rgb = (255, aux_colour, aux_colour)

                _regions += region_tmpl.format(tab * 7, region, test, sick, d_sick,
                                               recv, dead, *rgb, path_style, path)

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

        # prepare product version
        version = '{} [{}]'.format(__version__, self.translate('eng', 'ukr', __release__))

        # prepare data for rendering
        render_cfg = {'updated': updated, 'regions': regions, 'total': total, 'version': version}

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
        try:
            self.ftp.connect(server, 21)
            self.ftp.login(uname, upass)
        except Exception as e:
            self.logger.error('Не вдається приєднатись до FTP-сервера')
            return

        # configure copy destination
        self.ftp.cwd('/covidinfo.zzz.com.ua')

        # prepare copy list
        web_files = ['./report/index.html',
                     './report/report.css',
                     './report/report.js',
                     './report/virus.png',
                     './report/gear.png']

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
