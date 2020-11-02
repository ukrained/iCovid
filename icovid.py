#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '2.5.0'
__release__ = '02 Nov 2020'
__author__ = 'Alex Viytiv'

# modules
import urllib.request
import urllib.parse
import requests
import argparse
import time
import json
import glob
import ssl
import re
import os

from lxml import html
from ftplib import FTP
from getpass import getpass
from datetime import datetime, date, timedelta
from utils import Colour, LogLevel, Logger
from urllib.parse import quote


# global logger object
logger = Logger(LogLevel.NORMAL)


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

    def __init__(self, path):
        ''' DB Constructor '''
        self._path = path
        self.__db = {}
        self.__auto_save = True
        self._upload()

    def _upload(self):
        ''' Upload DB from the file '''
        if not os.path.isfile(self._path):
            logger.error('Файл БД \'{}\' не існує'.format(self._path))
            if not logger.approve('Створити БД'):
                logger.critical('Заборонена робота без БД')
                self.__auto_save = False
                exit(1)
            return

        if self.__db:
            logger.warning('БД вже ініціалізована')
            if not logger.approve('Перезаписати вміст БД'):
                logger.normal('БД не перезаписана')
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
                logger.error('Помилка при підвантаженні БД')
                raise e

            # Create backup file
            with open(self._path + '.backup', 'w+') as fpb:
                fpb.write(backup_data)

            logger.debug('Створено резервну копію даних "%s"' % (self._path + '.backup'))

        logger.success('БД підвантажено')

    def save(self):
        ''' Load DB to the file '''
        with open(self._path, 'w+') as fp:
            json.dump(self.__db, fp, indent=4, ensure_ascii=False)

        logger.normal('БД збережено')

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
            logger.error('Ключ "date" обов\'язковий')
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
                logger.debug('БД регіону {} оновлено'.format(k_regn))
                return

            self.__db[k_date][k_cont] = config
            logger.debug('БД країни {} оновлено'.format(k_cont))
            return

        self.__db[k_date] = config
        logger.debug('БД дати {} оновлено'.format(k_date))
        return

    def get(self, key, default=None):
        ''' Update DB entries

        :param key: dict of keys used to identify config point
        :param config: new config
        '''
        # keys {'date':'*', 'country': '*', 'region': '*'}
        k_date = key.get('date')
        k_cont = key.get('country')
        k_regn = key.get('region')

        if not k_date:
            logger.error('Ключ "date" обов\'язковий')
            return None
        elif not self.__db.get(k_date):
            return default

        if k_cont:
            if not self.__db[k_date].get(k_cont):
                return default

            if key.get('region'):
                if not self.__db[k_date][k_cont]['regions'].get(k_regn):
                    return default

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
    def __init__(self):
        self.db = dbWorker('icovid.db')
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

            logger.success('Словник "%s-%s" підвантажено' % (slang, dlang))

    def _web_request(self, url, headers={}):
        ''' Function perform HTML page request

        :param url: URL to webpage
        :return: 'utf-8'-encoded HTML page
        '''
        try:
            html = requests.get(url, headers=headers).text
        except Exception as e:
            logger.warning('Недійсний сертифікат сервера "{}"'.format(url))
            logger.debug(str(e))
            if not logger.approve('Не перевіряти сертифікат'):
                logger.critical('Помилка отримання даних')
                self.__auto_save = False
                exit(1)

            html = requests.get(url, headers=headers, verify=False).text

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

        logger.normal('Словники збережено')


class iCovid (iCovidBase):
    def __init__(self):
        ''' Constructor '''
        super().__init__()

        # initialize FTP object
        self.ftp = FTP()
        self.ftp.set_debuglevel(0)
        self._uname = ''
        self._upass = ''

    def update(self):
        ''' Update latest data '''
        # update callbacks
        upd_cbs = [self._upd_ukr, self._upd_ulv, self._upd_isr, self._upd_pol,
                   self._upd_rus, self._upd_hug, self._upd_rom]
        # slovakia - https://korona.gov.sk/en/coronavirus-covid-19-in-the-slovak-republic-in-numbers/

        curr_date = datetime.now().strftime("%d %b %Y")

        # run update data
        logger.normal('Оновлюємо дані ..')
        start = time.time()

        for upd_cb in upd_cbs:
            try:
                # try to update and measure duration
                upd_start = time.time()
                data = upd_cb()
                self.db.update({'date': curr_date, 'country': data['Name']}, data)
                upd_duration = time.time() - upd_start

                logger.success('Дані з %s оновлені [%fс]' % (data['Name'], upd_duration))
            except Exception as e:
                logger.error('Помилка при оновленні даних: %s' % upd_cb)
                raise e
                continue

        duration = time.time() - start
        logger.debug('Оновлення даних завершено [%fс]' % duration)

    def _upd_ukr(self):
        config = {'Name': 'Україна', 'Code': 'ukr',
                  'ViewBoxSz': '0 0 640 410', 'ViewBoxLineSz': 0.7,
                  'Population': 43762985, 'Area': 603628,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 40000, 'Description': '', 'Cure': 2,
                  'Regions': {}}

        config['Description'] = 'Розташована в Східній та частково в Центральній Європі, у південно-західній частині Східноєвропейської рівнини.<br><br>Держава-правонаступниця УНР, Гетьманщини, Королівства Руського та Київської Русі.<br><br>Найбільша за площею країна з тих, чия територія повністю лежить у Європі.'

        # cure: https://www.president.gov.ua/news/ukrayina-rozpochinaye-klinichni-doslidzhennya-preparatu-sho-60777

        config = self.__upd_ukr_total(config)
        config = self.__upd_ukr_regions(config)

        return config

    def __upd_ukr_total(self, config):
        # covid19.gov.ua
        logger.normal(' - Збір загальних даних з covid19.gov.ua ..')
        page = self._web_request('https://covid19.gov.ua/en/')

        divs = self._html_get_node(page, './/div[contains(@class, \'one-field\') and contains(@class, \'light-box\') and contains(@class, \'info-count\')]')
        if len(divs) != 4:
            logger.error('Неочікуване число елементів - %d' % len(divs))
            exit(1)

        for i, case in enumerate(['Sick', 'Recovered', 'Dead', 'Tested']):
            config[case] = int(divs[i].xpath('.//div')[0].text.strip().replace(' ', ''))

        return config

    def __upd_ukr_regions(self, config):
        # moz.gov.ua
        # detailed - https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/
        logger.normal(' - Збір даних про регіони з index.minfin.com.ua ..')
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

            if len(items) == 0 or len(items[0]) == 0:
                continue
            if items[0][0].text in name_mapping:
                config['Regions'][name_mapping.get(items[0][0].text, items[0][0].text)] = int(items[1].text)

        return config

    def _upd_ulv(self):
        config = {'Name': 'Львівщина', 'Code': 'ulv',
                  'ViewBoxSz': '0 0 1300 1300', 'ViewBoxLineSz': 2,
                  'Population': 2529608, 'Area': 21833,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 3000, 'Description': '', 'Cure': 0,
                  'Regions': {},
                  'vii': ['✔️ Автоматичне оновлення даних.<br><br>👉 З 30 жовтня оновлення даних із районів Львівщини виконується автоматично.', '✔️']}

        config['Description'] = 'Одна з трьох областей історико-культурного регіону Галичина, частини Карпатського регіону.<br><br>Одна з найрозвиненіших областей в економічному, туристичному, культурному та науковому напрямках.'

        config = self.__upd_ulv_total(config)
        config = self.__upd_ulv_regions(config)

        return config

    def __upd_ulv_total(self, config):
        # covid19.gov.ua
        logger.normal(' - Збір загальних даних з index.minfin.com.ua ..')
        page = self._web_request('https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/')

        rows = self._html_get_node(page, './/div[@class="compact-table expand-table"]//table//tr')
        for row in rows:
            items = row.xpath('.//td')
            if len(items) == 0 or len(items[0]) == 0:
                continue
            elif items[0][0].text == 'Львівська':
                config['Sick'] = int(items[1].text)
                config['Dead'] = int(items[3].text)
                config['Recovered'] = int(items[5].text)

        # headers required to get access to the mae.ro web-page
        hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0'}

        # get intial page to find out final link with tested persond data
        page = self._web_request('http://ses.lviv.ua/')
        links = self._html_get_node(page, './/div[@class="moduletable"]//ul//li//a')

        # go through all available paragraphs and look for the link
        target_link = ''
        for link in links:
            if 'Covid-19 у Львівській області станом на' in link.text:
                target_link = 'http://ses.lviv.ua' + link.attrib['href']
                break

        if target_link:
            logger.debug('Цільове посилання: {} ..'.format(target_link))
            # get the page with tested persons quanity
            page = self._web_request(target_link, headers=hdrs)
            paragraphs = self._html_get_node(page, './/div[@class="item-page news-page"]//div//p')

            for p in paragraphs:
                if p.text and 'Всього проведено' in p.text.strip():
                    config['Tested'] = int(p.text.split()[2])
                    break

        return config

    def __upd_ulv_regions(self, config):
        # moz.gov.ua
        # detailed - https://index.minfin.com.ua/ua/reference/coronavirus/ukraine/
        logger.normal(' - Збір даних про регіони з ses.lviv.ua ..')
        # page = self._web_request(tested_links[0])

        # initial regions data
        initial = ["Бродівський район", "Буський район", "Городоцький район",
                   "Дрогобицький район",  # Борислав, Стебник, Дрогобич, Трускавець
                   "Жидачівський район", "Жовківський район", "Золочівський район",
                   "Кам'янка-Бузький район", "Миколаївський район",  # Новий Розділ
                   "Мостиський район", "Перемишлянський район", "Пустомитівський район",
                   "Радехівський район", "Самбірський район",  # Самбір
                   "Сколівський район", "Сокальський район",  # Червоноград
                   "Старосамбірський район", "Стрийський район",  # Моршин, Стрий
                   "Турківський район", "Яворівський район",
                   "м. Львів"]
        config['Regions'] = {k: 0 for k in initial}

        sub_regions_mapping = {
            'Львова': 'м. Львів',
            'Борислав': 'Дрогобицький район',
            'Бродівськ': 'Бродівський район',
            'Буськ': 'Буський район',
            'Городоцьк': 'Городоцький район',
            'Дрогобицьк': 'Дрогобицький район',
            'Дрогобич': 'Дрогобицький район',
            'Стебник': 'Дрогобицький район',
            'Жидачівськ': 'Жидачівський район',
            'Жовківськ': 'Жовківський район',
            'Золочівськ': 'Золочівський район',
            'Кам’янка-Бузьк': 'Кам\'янка-Бузький район',
            'Миколаївськ': 'Миколаївський район',
            'Моршин': 'Стрийський район',
            'Мостиськ': 'Мостиський район',
            'Новий Розділ': 'Миколаївський район',
            'Перемишлянськ': 'Перемишлянський район',
            'Пустомитівськ': 'Пустомитівський район',
            'Радехівськ': 'Радехівський район',
            'Самбір': 'Самбірський район',
            'Самбірськ': 'Самбірський район',
            'Сколівськ': 'Сколівський район',
            'Сокальськ': 'Сокальський район',
            'Старосамбірськ': 'Старосамбірський район',
            'Стрий': 'Стрийський район',
            'Стрийськ': 'Стрийський район',
            'Трускавець': 'Дрогобицький район',
            'Турківськ': 'Турківський район',
            'Червоноград': 'Сокальський район',
            'Яворівськ': 'Яворівський район'
        }

        # headers required to get access to the mae.ro web-page
        hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) Gecko/20100101 Firefox/82.0'}

        # get intial page to find out final link with tested persond data
        page = self._web_request('http://ses.lviv.ua/')
        links = self._html_get_node(page, './/div[@class="moduletable"]//ul//li//a')

        # go through all available paragraphs and look for the link
        target_link = ''
        for link in links:
            if 'Covid-19 у Львівській області станом на' in link.text:
                target_link = 'http://ses.lviv.ua' + link.attrib['href']
                break

        if target_link:
            logger.debug('Цільове посилання: {} ..'.format(target_link))
            # get the page with regions sick quanity
            page = self._web_request(target_link, headers=hdrs)
            paragraphs = self._html_get_node(page, './/div[@class="item-page news-page"]//div//p')

            for p in paragraphs:
                if not p.text:
                    # no text in the paragraph
                    continue

                for k, v in sub_regions_mapping.items():
                    # look for the region in the aragraph text
                    if k in p.text:
                        local_sick = int(p.text.split('/')[0].replace('–', ' ').replace('-', ' ').split()[-1])
                        config['Regions'][v] += local_sick
                        break

        return config

    def _upd_isr(self):
        config = {'Name': 'Ізраїль', 'Code': 'isr',
                  'ViewBoxSz': '0 0 250 800', 'ViewBoxLineSz': 1.0,
                  'Population': 8638917, 'Area': 20770,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 60000, 'Description': '', 'Cure': 3,
                  'Regions': {},
                  'vii': ['☣️ Дані з регіонів Ізраїлю відсутні у відкритому доступі.<br><br>👉 Публікація останніх відкритих даних відбулась 30 квітня 2020 року.<br><br>👉 Регіональний розподіл виконаний рівномірно на основі розподілу кількості населення у регіонах.', '☣️']}

        config['Description'] = 'Розташований на східному узбережжі Середземного моря. Незалежність проголошено 14 травня 1948 року (5 іяра 5708 року).<br><br>Ізраїль є єврейською державою. Упродовж трьох тисячоліть слово «Ізраїль» позначає Землю Ізраїльську (івр. אֶרֶץ יִשְׂרָאֵל‎, Е́рец-Їсрае́ль) і весь єврейський народ.<br><br>Джерелом назви слугує Книга Буття, де Яків, син Ісаака, після боротьби з ангелом Бога отримує ім\'я Ізраїль.'

        # cure: https://www.ukrinform.ua/rubric-world/2899971-vakcina-proti-koronavirusu-oglad-svitovih-rozrobok.html
        # https://data.gov.il/dataset/covid-19/resource/d07c0771-01a8-43b2-96cc-c6154e7fa9bd
        # https://data.gov.il/dataset/covid-19/resource/dcf999c1-d394-4b57-a5e0-9d014a62e046#collapse-endpoints
        # https://coronaupdates.health.gov.il/

        config = self.__upd_isr_total(config)
        config = self.__upd_isr_regions(config)

        return config

    def __upd_isr_total(self, config):
        # govextra.gov.il
        # Palestine: https://corona.ps/
        logger.normal(' - Збір загальних даних з worldometers.info ..')
        page = self._web_request('https://www.worldometers.info/coronavirus/')

        countries = self._html_get_node(page, './/table[@id="main_table_countries_today"]/tbody/tr')
        for country in countries:
            nodes = country.xpath('.//td//a')

            # check if there is name of country and it is Israel
            if len(nodes) > 0 and nodes[0].text == 'Israel':
                break

        config['Sick'] = int(country.xpath('.//td')[2].text.replace(',', ''))
        config['Dead'] = int(country.xpath('.//td')[4].text.replace(',', ''))
        config['Recovered'] = int(country.xpath('.//td')[6].text.replace(',', ''))
        config['Tested'] = int(country.xpath('.//td')[12].text.replace(',', ''))

        return config

    def __upd_isr_regions(self, config):
        # news.google.com
        logger.normal(' - Збір даних про регіони з news.google.com ..')
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
                  'Peak': 40000, 'Description': '', 'Cure': 1,
                  'Regions': {}}

        config['Description'] = 'Держава в Центральній Європі. За даними перепису населення, що відбувся у 2015 році, у країні проживало понад 38,5 мільйонів осіб.<br><br>Польща є п&apos;ятою за кількістю населення країною ЄС, дев&apos;ятою в Європі за площею та восьмою за населенням. Близько 61 % населення проживає в містах.'

        # cure: https://www.ukrinform.ua/rubric-world/2899971-vakcina-proti-koronavirusu-oglad-svitovih-rozrobok.html

        config = self.__upd_pol_total(config)
        config = self.__upd_pol_regions(config)

        return config

    def __upd_pol_total(self, config):
        # news.google.com
        logger.normal(' - Збір загальних даних з worldometers.info ..')
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
        logger.normal(' - Збір даних про регіони з www.gov.pl ..')
        page = self._web_request('https://www.gov.pl/web/koronawirus/wykaz-zarazen-koronawirusem-sars-cov-2')

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
        name_mapping = {'mazowieckie': 'Мазовецьке воєводство',
                        'śląskie': 'Сілезьке воєводство',
                        'dolnośląskie': 'Нижньосілезьке воєводство',
                        'łódzkie': 'Лодзьке воєводство',
                        'małopolskie': 'Малопольське воєводство',
                        'kujawsko-pomorskie': 'Куявсько-Поморське воєводство',
                        'pomorskie': 'Поморське воєводство',
                        'opolskie': 'Опольске воєводство',
                        'zachodniopomorskie': 'Західнопоморське воєводство',
                        'podkarpackie': 'Підкарпатське воєводство',
                        'warmińsko-mazurskie': 'Вармінсько-Мазурське воєводство',
                        'lubuskie': 'Любуське воєводство',
                        'świętokrzyskie': 'Свентокшиське воєводство',
                        'wielkopolskie': 'Великопольське воєводство',
                        'podlaskie': 'Підляське воєводство',
                        'lubelskie': 'Люблінське воєводство'}

        # get regions. skip first two general nodes
        regs_data = json.loads(self._html_get_node(page, './/pre[@id="registerData"]')[0].text)['data']
        regions = [row.split(';') for row in regs_data.split('\n') if len(row.split(';')) > 1][2:]
        for region in regions:
            reg = region[0]
            reg_name = name_mapping.get(reg, reg)

            sick = int(region[1].replace(' ', ''))
            config['Regions'][reg_name] = int(sick) if sick != '—' else 0

        return config

    def _upd_rus(self):
        config = {'Name': 'Московія', 'Code': 'rus',
                  'ViewBoxSz': '0 0 1250 800', 'ViewBoxLineSz': 0.8,
                  'Population': 145927292, 'Area': 17098246,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Peak': 30000, 'Description': '', 'Cure': 3,
                  'Regions': {}}

        config['Description'] = 'Федеративна республіка у північній Євразії. Початки державності відносять до періоду Русі — середньовічної держави із центром в Києві, під час розпаду якої, її північно-східні провінції перейшли під владу Золотої Орди, а пізніше стали основою майбутньої Московської держави.<br><br>У березні 2014 року здійснила військову агресію проти України, анексувавши Крим та Севастополь. Веде гібридну війну на Донбасі з метою окупації України.'

        # cure: https://www.aa.com.tr/en/latest-on-coronavirus-outbreak/russia-to-hold-phase-3-of-covid-19-vaccine-trial-abroad/1912694

        config = self.__upd_rus_total(config)
        config = self.__upd_rus_regions(config)

        return config

    def __upd_rus_total(self, config):
        # news.google.com
        # https://covid.ourworldindata.org/data/owid-covid-data.json
        logger.normal(' - Збір загальних даних з covid19.rosminzdrav.ru ..')
        page = self._web_request('https://covid19.rosminzdrav.ru/wp-json/api/mapdata/')
        data = json.loads(page)['Items']

        # config['Tested'] = sum([it['Observations'] for it in data])
        config['Sick'] = sum([it['Confirmed'] for it in data])
        config['Recovered'] = sum([it['Recovered'] for it in data])
        config['Dead'] = sum([it['Deaths'] for it in data])

        page = self._web_request('https://www.worldometers.info/coronavirus/')

        countries = self._html_get_node(page, './/table[@id="main_table_countries_today"]/tbody/tr')
        for country in countries:
            nodes = country.xpath('.//td//a')

            # check if there is name of country and it is Russia
            if len(nodes) > 0 and nodes[0].text == 'Russia':
                break

        config['Tested'] = int(country.xpath('.//td')[12].text.replace(',', ''))

        return config

    def __upd_rus_regions(self, config):
        # news.google.com
        logger.normal(' - Збір даних про регіони з covid19.rosminzdrav.ru ..')
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
                  'Peak': 10000, 'Description': '', 'Cure': 2,
                  'Regions': {}}

        config['Description'] = 'Держава в центральній Європі. Державна мова — угорська, що є найбільш уживаною уральською мовою у світі.<br><br>Територія сучасної Угорщини століттями була заселена цілою низкою народів, включаючи кельтів, римлян, германських племен, гунів, західних слов&apos;ян та аварів. Країна має економіку з високим рівнем доходу.'

        # cure: https://www.cfr.org/backgrounder/what-world-doing-create-covid-19-vaccine
        # cure: https://hungarytoday.hu/avigan-drug-against-covid-19-to-be-tested-in-hungary/
        # cure: https://dailynewshungary.com/hungarian-discovery-might-bring-a-breakthrough-in-curing-covid-19/

        config = self.__upd_hug_total(config)
        config = self.__upd_hug_regions(config)

        return config

    def __upd_hug_total(self, config):
        # news.google.com
        logger.normal(' - Збір загальних даних з koronavirus.gov.hu ..')
        page = self._web_request('https://koronavirus.gov.hu/')

        recv_pest = self._html_get_node(page, './/div[@id="api-gyogyult-pest"]')[0]
        recv_videk = self._html_get_node(page, './/div[@id="api-gyogyult-videk"]')[0]
        config['Recovered'] = int(recv_pest.text.replace(' ', '')) + int(recv_videk.text.replace(' ', ''))

        sick_pest = self._html_get_node(page, './/div[@id="api-fertozott-pest"]')[0]
        sick_videk = self._html_get_node(page, './/div[@id="api-fertozott-videk"]')[0]
        quarantine = self._html_get_node(page, './/div[@id="api-karantenban"]')[0]
        config['Sick'] = int(sick_pest.text.replace(' ', '')) + int(sick_videk.text.replace(' ', '')) + int(quarantine.text.replace(' ', '')) + config['Recovered']

        dead_pest = self._html_get_node(page, './/div[@id="api-elhunyt-pest"]')[0]
        dead_videk = self._html_get_node(page, './/div[@id="api-elhunyt-videk"]')[0]
        config['Dead'] = int(dead_pest.text.replace(' ', '')) + int(dead_videk.text.replace(' ', ''))

        tested = self._html_get_node(page, './/div[@id="api-mintavetel"]')[0]
        config['Tested'] = int(tested.text.replace(' ', ''))
        return config

    def __upd_hug_regions(self, config):
        # news.google.com
        logger.normal(' - Збір даних про регіони з news.google.com ..')
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
                  'Peak': 10000, 'Description': '', 'Cure': 1,
                  'Regions': {}}

        config['Description'] = 'Держава на перехресті східної, центральної та південно-східної Європи.<br><br>Назва Romania походить від лат. romanus, що означає &quot;громадянин Риму&quot;. Перше відоме вживання цього звернення датується XVI ст. італійськими гуманістами, що подорожували Трансільванією, Богданією та Волощиною.<br><br>Переважна більшість населення самоідентифікують, як православні християнами і є носіями румунської мови.'

        # cure: https://www.romania-insider.com/romania-european-system-coronavirus-vaccine

        config = self.__upd_rom_total(config)
        config = self.__upd_rom_regions(config)

        return config

    def __upd_rom_total(self, config):
        # news.google.com
        logger.normal(' - Збір загальних даних з mae.ro ..')

        # headers required to get access to the mae.ro web-page
        hdrs = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

        # get intial page to find out final link with tested persond data
        page = self._web_request('https://stirioficiale.ro/informatii', headers=hdrs)
        links = self._html_get_node(page, './/div[@class="flex-1 px-8 py-5"]//h1//a')

        # go through all available paragraphs and look for the link
        target_link = ''
        for link in links:
            if 'BULETIN DE PRESĂ' in link.text:
                target_link = link.attrib['href']
                break

        if target_link:
            logger.debug('Цільове посилання: {} ..'.format(target_link))
            # get the page with tested persons quanity
            page = self._web_request(target_link, headers=hdrs)
            paragraphs = self._html_get_node(page, './/div[@class="my-8 break-words rich-text"]//p')
            for p in paragraphs:
                if p.text and 'au fost prelucrate' in p.text.strip():
                    config['Tested'] = int(p.text.split()[10].replace('.', ''))
                    break

        # get other data
        page = self._web_request('https://datelazi.ro/latestData.json')
        #page = self._web_request('https://di5ds1eotmbx1.cloudfront.net/latestData.json')

        data = json.loads(page)['currentDayStats']

        config['Sick'] = data['numberInfected']
        config['Recovered'] = data['numberCured']
        config['Dead'] = data['numberDeceased']

        return config

    def __upd_rom_regions(self, config):
        # news.google.com
        logger.normal(' - Збір даних про регіони з datelazi.ro ..')
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
                logger.debug('Невідомий регіон у %d осіб' % unknown)

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
        data_yestd = self.db.get({'date': (date.today() - timedelta(days=1)).strftime("%d %b %Y")}, data_today)

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
            text += '\n   [ %s ] ' % Colour.set(Colour.fg.cyan, country)
            text += 'Населення {:,} людей на {:,} км2 ({:.2f} л/км2)\n' \
                    .format(cfg['Population'], cfg['Area'],
                            cfg['Population'] / cfg['Area'])

            # total information
            text += ' .{:-<76}.\n'.format('')
            block = '   {:>10} | {:^20} | {:<+7}  {:>10} | {:^20} | {:<+7}\n'

            d_test = cfg['Tested'] - ycfg.get('Tested', cfg['Tested'])
            d_recv = cfg['Recovered'] - ycfg.get('Recovered', cfg['Recovered'])
            text += block.format(cfg['Tested'], Colour.set(Colour.fg.grey, 'Перевірені'), d_test,
                                 cfg['Recovered'], Colour.set(Colour.fg.green, 'Одужали'), d_recv)

            d_sick = cfg['Sick'] - ycfg.get('Sick', cfg['Sick'])
            d_dead = cfg['Dead'] - ycfg.get('Dead', cfg['Dead'])
            text += block.format(cfg['Sick'], Colour.set(Colour.fg.yellow, 'Хворі'), d_sick,
                                 cfg['Dead'], Colour.set(Colour.fg.red, 'Померли'), d_dead)

            # separator
            text += ' +{:-<76}+\n'.format('')

            # regions information
            if regions:
                # 5 zones Coloured by unique Colour
                zones = {0: Colour.fg.white, 1: Colour.fg.yellow,
                         2: Colour.fg.orange, 3: Colour.fg.lightred,
                         4: Colour.fg.red}
                min_sick = min(regions.values())
                sick_step = (max(regions.values()) + 1 - min_sick) / 5

                min_rdsick = min(rd_sick.values())
                rdsick_step = (max(rd_sick.values()) + 1 - min_rdsick) / 5

                text += '   Рівні небезпеки: %s\n' % ' '.join(Colour.set(zones[i], str(i)) for i in range(5))
                text += ' +{:-<76}+\n'.format('')

                for region, sick in regions.items():
                    # depending of the value, region will have its Colour
                    clr = zones[(rd_sick[region] - min_rdsick) // rdsick_step]
                    ysick = Colour.set(clr, '%+d' % rd_sick[region])

                    clr = zones[(sick - min_sick) // sick_step]
                    region = Colour.set(clr, region) + ' '
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

        def make_data_regs(country, today, yestd):
            """ Function build data regs attribute

            Args:
                country (str): name of the country
                today (str): today`s date
                yestd (str): yesterday`s date

            Returns:
                str: data-regs attribute
            """
            data_regs = []
            data_reg_tmpl = '"{}", "{}", "{}", "{}", "{}"'

            today_data = self.db.get({'date': today, 'country': country})
            yestd_data = self.db.get({'date': yestd, 'country': country}, today_data)

            for region in today_data['Regions']:
                sick = today_data['Regions'].get(region, 0)
                d_sick = sick - yestd_data['Regions'].get(region, sick)
                data_regs.append([region, sick, d_sick])
                #data_regs.append(data_reg_tmpl.format(region, sick, d_sick))

            # 5 zones Coloured by unique Colour
            danger_color = "dtrr_danger{}"
            min_sick = min([it[1] for it in data_regs])
            sick_step = (max([it[1] for it in data_regs]) + 1 - min_sick) / 5

            min_dsick = min([it[2] for it in data_regs])
            dsick_step = (max([it[2] for it in data_regs]) + 1 - min_dsick) / 5

            for reg in data_regs:
                # depending of the value, region will have its Colour
                sick = danger_color.format(int((reg[1] - min_sick) // sick_step))
                reg.append(sick)
                delta_sick = danger_color.format(int((reg[2] - min_dsick) // dsick_step))
                reg.append(delta_sick)

            # sort regions by number of sick and format
            data_regs = [data_reg_tmpl.format(*x) for x in sorted(data_regs, key=lambda x: int(x[1]), reverse=True)]

            return '[{}]'.format(','.join(data_regs)).replace('\'', '&apos;')

        # define templates for complex nodes
        total_tmpl = '{}<div id="total{}" title="{}" peak="{}" popl="{}" area="{}" dens="{}" desc="{}" cure="{}" data-regs=\'{}\' tested="{}" d_tested="{}" sick="{}" d_sick="{}" recovered="{}" d_recovered="{}" dead="{}" d_dead="{}" data-days=\'{}\' data-test=\'{}\' data-sick=\'{}\' data-recv=\'{}\' data-dead=\'{}\' style="display: none;"></div>\n'
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
        vii_tmpl = '<span class="vi_info" onclick="notify(\'{}\', 15000);">{}</span>'

        # create htmlWorker object
        html = htmlWorker('./report/report.html', './report/index.html')

        # config for rendering
        render_cfg = {}
        updated = ''
        total = ''
        regions = ''
        checked = 'checked'
        tab = '    '

        # get current and yesterday dates
        curr_date = date.today().strftime("%d %b %Y")
        yest_date = (date.today() - timedelta(days=1)).strftime("%d %b %Y")

        # upload paths for regions
        with open('./report/regions.map', 'r+') as fp:
            regions_map = json.load(fp)

        # get data for current date
        today_data = self.db.get({'date': curr_date})
        yestd_data = self.db.get({'date': yest_date}, today_data)

        # stage 1 - date of latest data update
        updated = self.translate('eng', 'ukr', curr_date)

        # configure default information
        default = today_data.get('Україна')
        y_default = yestd_data.get('Україна')

        # prepare dynamics data
        hist = make_history('Україна', 14)

        # make default total data
        total = total_tmpl.format(tab * 2, '', default['Name'], default['Peak'],
                                  '{:,}'.format(default['Population']),
                                  '{:,}'.format(default['Area']),
                                  '{:.2f}'.format(default['Population'] / default['Area']),
                                  default['Description'], default['Cure'],
                                  make_data_regs(default['Name'], curr_date, yest_date),
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
                                       '{:,}'.format(data['Population']),
                                       '{:,}'.format(data['Area']),
                                       '{:.2f}'.format(data['Population'] / data['Area']),
                                       data['Description'], data['Cure'],
                                       make_data_regs(data['Name'], curr_date, yest_date),
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
                aux_Colour = int(255 - ((0 if sick == '—' else sick) / color_step))
                rgb = (255, aux_Colour, aux_Colour)

                _regions += region_tmpl.format(tab * 7, region, test, sick, d_sick,
                                               recv, dead, *rgb, path_style, path)

            # strip redundant newline
            _regions = _regions.rstrip()

            # prepare very important information (vii)
            vii = vii_tmpl.format(*data['vii']) if data.get('vii') else ''

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
            logger.print('', end='\n')
            logger.debug('Дані користувача не надано')
            return (None, None)

        return (username, password)

    def _ftp_upload(self, srcfile):
        def ftp_path(orig_path):
            return orig_path.replace('./report/', '')

        # upload the file via STOR command
        start = time.time()
        with open(srcfile, 'rb') as f:
            self.ftp.storbinary('STOR %s' % ftp_path(srcfile), f, 1024)
        duration = time.time() - start

        logger.debug('Файл "%s" вивантажено [%fс]' % (srcfile, duration))

    def webpage_update(self, server):
        ''' Update web-page files through FTP server '''
        # generate HTML report
        logger.normal('Генерування веб-сторінки ..')
        self._html_report()
        logger.success('Веб-сторінку згенеровано')

        # run web files upload
        logger.normal('Оновлення веб-сторінки розпочато ..')

        # check if user entered login and password earlier
        if not (self._uname and self._upass):
            # there is no all information, so request a new one from the user
            self._uname, self._upass = self._login()
            if not (self._uname and self._upass):
                logger.warning('Оновлення веб-сторінки скасовано')
                return
        else:
            logger.normal('Автоматичне використання попередніх логіну та паролю')

        # setup FTP connection
        start = time.time()
        try:
            self.ftp.connect(server, 21)
            self.ftp.login(self._uname, self._upass)
        except Exception as e:
            logger.error('Не вдається приєднатись до FTP-сервера')
            return

        # configure copy destination
        self.ftp.cwd('/covidinfo.zzz.com.ua')

        # prepare copy list
        web_files = ['./report/index.html',
                     './report/css/report.css',
                     './report/js/report.js',
                     './report/js/chart.min.js',
                     './report/js/jquery.min.js',
                     './report/images/gear.png',
                     './report/images/virus.png',
                     './report/images/eugenii.png',
                     './report/images/oleksandr.png',
                     './report/images/vyrij_logo.png',
                     './report/flags/flag_default.jpg',
                     './report/flags/flag_ukr.jpg',
                     './report/flags/flag_ulv.jpg',
                     './report/flags/flag_isr.jpg',
                     './report/flags/flag_pol.jpg',
                     './report/flags/flag_rus.jpg',
                     './report/flags/flag_hug.jpg',
                     './report/flags/flag_rom.jpg']

        duration = time.time() - start
        logger.normal('Приєднано до FTP-сервера [%fс]' % duration)

        # copy files
        logger.normal('Починаємо надсилання файлів ...', end='\r')
        start = time.time()
        for i, wfile in enumerate(web_files, 1):
            self._ftp_upload(wfile)
            logger.normal('Наділано на сервер {} з {} файлів ...'.format(i, len(web_files)), end='\r' if wfile != web_files[-1] else '\n')
        duration = time.time() - start

        logger.success('Веб-сторінку "%s" оновлено [%fс]' % (server, duration))


def help():
    """ Function prints help to the user """
    # sections separator
    separator = ' {0:-^80}\n'.format('')

    # prepare program head
    head = '  {}{{}}[version {} | {}]\n'.format(__title__, __version__, __release__)
    head = separator + head.format(' ' * (82 - len(head))) + separator

    body = '  This tool provides information regarding COVID-19 disease spread. Here you can\n' + \
           '  get different kinds of information about territories, countires, number of the\n' + \
           '  performed tests, spreading coefficients and so on.\n' + \
           '\n' + \
           '  CLI tool provides you standard set of needed information. The simplest way to\n' + \
           '  get the information is to run this tool:\n' + \
           '      ./icovid.py\n' + \
           '\n' + \
           '  To get some debug information, run tool with \'-d\' option:\n' + \
           '      ./icovid.py [-d|--debug]\n' + \
           '\n' + \
           '  To update a web page, run tool with \'-w\' option:\n' + \
           '      ./icovid.py [-w|--web_update]\n' + \
           '\n' + \
           '  To get help, run tool with \'-h\' option:\n' + \
           '      ./icovid.py [-h|--help]\n' + \
           '\n'

    foot = separator + \
           '  For better usage experience visit our website: www.covidinfo.zzz.com.ua\n' + \
           '  Your questions or proposals you can send to: sviytiv@gmail.com\n' + \
           separator

    text = head + body + foot
    print(text)


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-w', '--web_update',  action='store_true')
    parser.add_argument('-s', '--server', action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-h', '--help', action='store_true')

    args = parser.parse_args()


    if args.help:
        if args.debug or args.web_update:
            parser.error('You are not allowed to use help with other options.')

        help()

    else:
        logger.set_lvl(LogLevel.DEBUG if args.debug else LogLevel.NORMAL)
        covid = iCovid()

        while True:
            try:
                covid.update()
                print(covid)

                if args.web_update:
                    covid.webpage_update('covidinfo.zzz.com.ua')

                logger.success('Дані на сервері оновлено {:%d-%b-%Y %H:%M:%S}'.format(datetime.now()))

            except Exception as e:
                # oops... something unexpectedly failed
                logger.error('Не вдалось оновити дані на сервері {:%d-%b-%Y %H:%M:%S}'.format(datetime.now()))
                print(e)

            if not args.server:
                # exit if user not enabled server mode
                break
            else:
                # time of pause before next request in seconds
                period = 3600

                # print delay till next request
                period_h = int(period / 3600)
                period_m = int((period - period_h * 3600) / 60)
                period_s = int(period - period_h * 3600 - period_m * 60)
                logger.normal('Наступний запит через {}г {}хв {}с'.format(period_h, period_m, period_s))

                time.sleep(period)


if __name__ == '__main__':
    main()
