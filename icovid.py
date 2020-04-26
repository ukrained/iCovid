#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '0.4.7[a]'
__release__ = '24 Apr 2020'
__author__ = 'Oleksandr Viytiv'

# modules
import urllib.request
import urllib.parse
import json
import re
import os

from lxml import html
from datetime import datetime
from utils import colour, logLevel, logger


class dbWorker:
    ''' Interface for interfactions with DataBase '''
    ''' DB Structure
    {
        '22.04.2020': {
            'Ukraine': {
                'Population': 41880000,
                'Area': 603628,
                'Tested': 0,
                'Regions': {
                    'Lviv': {}
                }
            }
        }
    }
    '''

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
            self.__db = json.load(fp)

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
                self.logger.debug('Регіон {} оновлено'.format(k_regn))
                return

            self.__db[k_date][k_cont] = config
            self.logger.debug('Країну {} оновлено'.format(k_cont))
            return

        self.__db[k_date] = config
        self.logger.debug('Дату {} оновлено'.format(k_date))
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

    def web_request(self, url):
        ''' Function perform HTML page request

        :param url: URL to webpage
        :return: 'utf-8'-encoded HTML page
        '''
        with urllib.request.urlopen(urllib.request.Request(url)) as response:
            html = response.read()

        return html.decode('utf-8')

    def html_get_node(self, html_buffer, pattern, nid=None):
        ''' Function lookup HTML content

        :param html: WEB page HTML data
        :param pattern: regex pattern for node
        :param nid: Node ID if user want specific node
        :return: all nodes found
        '''
        tree = html.fromstring(html_buffer)
        nodes = tree.xpath(pattern)

        return nodes[nid] if nid is not None else nodes


class iCovid (iCovidBase):
    def __init__(self):
        ''' Constructor '''
        super().__init__(logLevel.NORMAL)
        self._updated = 0

    def update(self, countries):
        ''' Update latest data '''
        # update callbacks
        upd_cbs = {'ukr': self._upd_ukr,
                   'isr': self._upd_isr}

        self._updated = datetime.now()
        curr_date = self._updated.strftime("%d %b %Y")

        for country in countries:
            if country in upd_cbs:
                self.logger.normal('Оновлюємо дані про %s ..' % country)
                name, cfg = upd_cbs[country]()
                self.db.update({'date': curr_date, 'country': name}, cfg)
                self.logger.success('Дані з {} оновлені'.format(name))

    def _upd_ukr(self):
        config = {'Population': 41880000, 'Area': 603628,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {}}

        config = self.__upd_ukr_total(config)
        config = self.__upd_ukr_regions(config)

        return 'Україна', config

    def __upd_ukr_total(self, config):
        # covid19.gov.ua
        self.logger.normal(' - Збір загальних даних ..')
        page = self.web_request('https://covid19.gov.ua/')

        divs = self.html_get_node(page, './/div[@class="one-field light-box info-count"]')
        if len(divs) != 4:
            self.logger.error('Not expected number of nodes - %d' % len(divs))
            exit(1)

        for i, case in enumerate(['Tested', 'Sick', 'Recovered', 'Dead']):
            config[case] = divs[i].xpath('.//div')[0].text.strip()

        self.logger.trace(' + Загальні дані оновлено')
        return config

    def __upd_ukr_regions(self, config):
        # moz.gov.ua
        self.logger.normal(' - Збір даних про регіони ..')
        page = self.web_request('https://moz.gov.ua/article/news/operativna-informacija-pro-poshirennja-koronavirusnoi-infekcii-2019-ncov-1')

        regions_node = self.html_get_node(page, './/div[@class="editor"]//ul', nid=0)
        regions = regions_node.xpath('.//li')
        for region in regions:
            reg, cases = region.text.split(' — ')
            config['Regions'][reg] = int(cases.strip().split()[0])

        self.logger.trace(' + Дані про регіони оновлено')
        return config

    def _upd_isr(self):
        config = {'Population': 9136000, 'Area': 20770,
                  'Tested': 0, 'Sick': 0, 'Recovered': 0, 'Dead': 0,
                  'Regions': {}}

        config = self.__upd_isr_total(config)
        config = self.__upd_isr_regions(config)

        return 'Ізраїль', config

    def __upd_isr_total(self, config):
        # govextra.gov.il
        self.logger.normal(' - Збір загальних даних ..')
        page = self.web_request('https://govextra.gov.il/ministry-of-health/corona/corona-virus/')

        total = self.html_get_node(page, './/div[@class="corona-xl corona-bold corona-sickmiddle"]', nid=0)
        config['Sick'] = total.text

        deadrec = self.html_get_node(page, './/div[@class="corona-lg corona-bold"]')
        config['Dead'] = deadrec[0].text
        config['Recovered'] = deadrec[1].text

        self.logger.trace(' + Загальні дані оновлено')
        return config

    def __upd_isr_regions(self, config):
        # moz.gov.ua
        self.logger.normal(' - Збір даних про регіони ..')
        #page = self.web_request('https://moz.gov.ua/article/news/operativna-informacija-pro-poshirennja-koronavirusnoi-infekcii-2019-ncov-')

        self.logger.trace(' + Дані про регіони оновлено')
        return config

    def __str__(self):
        ''' Show COVID information '''
        # get input data
        curr_date = self._updated.strftime("%d %b %Y")
        countries = self.db.get({'date': curr_date})

        # datetime object containing current date and time
        text = '\n * Дані станом на {:%d %B %Y [%H:%M:%S]}\n'.format(self._updated)

        for country, cfg in countries.items():
            # sort regions
            regions = {k: v for k, v in sorted(cfg['Regions'].items(),
                                               key=lambda it: it[1],
                                               reverse=True)}

            # total information
            text += '\n   [ %s ] ' % self.logger.encolour(colour.fg.cyan, country)
            text += '  %s %s' % (cfg['Tested'], self.logger.encolour(colour.fg.grey, 'Перевірені'))
            text += '  %s %s' % (cfg['Sick'], self.logger.encolour(colour.fg.yellow, 'Хворі'))
            text += '  %s %s' % (cfg['Recovered'], self.logger.encolour(colour.fg.green, 'Одужали'))
            text += '  %s %s\n' % (cfg['Dead'], self.logger.encolour(colour.fg.red, 'Померли'))
            text += ' .{:-<76}.\n'.format('')

            # regions information
            if regions:
                min_cases = min(regions.values())
                zone_step = (max(regions.values()) + 1 - min_cases) / 5
                zone_colour = {0: colour.fg.white, 1: colour.fg.yellow,
                               2: colour.fg.orange, 3: colour.fg.lightred,
                               4: colour.fg.red}

                text += '   Рівні небезпеки: %s\n' % ' '.join(self.logger.encolour(zone_colour[i], str(i)) for i in range(5))
                text += ' +{:-<76}+\n'.format('')

                for region, sick in regions.items():
                    # depending of the value, region will have its colour
                    clr = zone_colour[(sick - min_cases) // zone_step]
                    text += '   {:.<70} {:<6}\n'.format(self.logger.encolour(clr, region) + ' ',
                                                        '[' + str(sick) + ']')

            else:
                text += '   << Немає даних по регіонах >>\n'

            text += ' +{:-<76}+\n'.format('')

            # country information
            text += '   Населення {:,} людей на {:,} км2 ({:.2f} л/км2)\n' \
                    .format(cfg['Population'], cfg['Area'],
                            cfg['Population'] / cfg['Area'])
            text += ' \'{:-<76}\'\n'.format('')

        return text

    def html_report(self):
        ''' Export data to HTML web page '''
        # TODO: future feature
        pass


def main():
    covid = iCovid()
    covid.update(['ukr', 'isr'])
    print(covid)


if __name__ == '__main__':
    main()
