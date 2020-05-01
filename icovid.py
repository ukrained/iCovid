#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '0.4.7[a]'
__release__ = '24 Apr 2020'
__author__ = 'Oleksandr Viytiv'

# modules
import urllib.request
import urllib.parse
import argparse
import json
import re
import os

from lxml import html
from ftplib import FTP
from getpass import getpass
from datetime import datetime, date, timedelta
from utils import colour, logLevel, logger


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

    def _web_request(self, url):
        ''' Function perform HTML page request

        :param url: URL to webpage
        :return: 'utf-8'-encoded HTML page
        '''
        with urllib.request.urlopen(urllib.request.Request(url)) as response:
            html = response.read()

        return html.decode('utf-8')

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


class iCovid (iCovidBase):
    def __init__(self, debug=False):
        ''' Constructor '''
        super().__init__(logLevel.TRACE if debug else logLevel.NORMAL)

        # initialize FTP object
        self.ftp = FTP()
        self.ftp.set_debuglevel(0)

    def update(self, countries):
        ''' Update latest data '''
        # update callbacks
        upd_cbs = {'ukr': self._upd_ukr,
                   'isr': self._upd_isr}

        curr_date = datetime.now().strftime("%d %b %Y")

        self.logger.normal('Оновлюємо дані ..')
        for country in countries:
            if country in upd_cbs:
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

        regions_node = self._html_get_node(page, './/div[@class="editor"]//ul', nid=0)
        regions = regions_node.xpath('.//li')
        for region in regions:
            reg, cases = region.text.split(' — ')
            config['Regions'][reg] = int(cases.strip().split()[0])

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
        self.logger.normal(' - Збір загальних даних з govextra.gov.il ..')
        page = self._web_request('https://govextra.gov.il/ministry-of-health/corona/corona-virus/')

        total = self._html_get_node(page, './/div[@class="corona-xl corona-bold corona-sickmiddle"]', nid=0)
        config['Sick'] = int(total.text.replace(',', ''))

        deadrec = self._html_get_node(page, './/div[@class="corona-lg corona-bold"]')
        config['Dead'] = int(deadrec[0].text.replace(',', ''))
        config['Recovered'] = int(deadrec[1].text.replace(',', ''))

        return config

    def __upd_isr_regions(self, config):
        #
        self.logger.normal(' - Збір даних про регіони ..')
        # page = self._web_request('')
        return config

    def __str__(self):
        ''' Show COVID information '''
        # get input data
        data_today = self.db.get({'date': date.today().strftime("%d %b %Y")})
        data_yestd = self.db.get({'date': (date.today() - timedelta(days=1)).strftime("%d %b %Y")})

        # datetime object containing current date and time
        text = '\n * Дані станом на {:%d %B %Y [%H:%M:%S]}\n'.format(datetime.now())

        for country, cfg in data_today.items():
            # yesterday configuration
            ycfg = data_yestd[country]

            # sort regions
            regions = {k: v for k, v in sorted(cfg['Regions'].items(),
                                               key=lambda it: it[1],
                                               reverse=True)}

            # sort regions delta
            rd = {k: v - ycfg['Regions'][k] for k, v in cfg['Regions'].items()}
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
            block = '   {:>10} | {:^20} | {:<+6}  {:>10} | {:^20} | {:<+6}\n'

            d_test = cfg['Tested'] - ycfg['Tested']
            d_recv = cfg['Recovered'] - ycfg['Recovered']
            text += block.format(cfg['Tested'], colour.set(colour.fg.grey, 'Перевірені'), d_test,
                                 cfg['Recovered'], colour.set(colour.fg.green, 'Одужали'), d_recv)

            d_sick = cfg['Sick'] - ycfg['Sick']
            d_dead = cfg['Dead'] - ycfg['Dead']
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
                    text += '   {:.<70} {:<5} | {:<5}\n'.format(region, sick, ysick)

            else:
                text += '   << Немає даних по регіонах >>\n'

            text += ' \'{:-<76}\'\n'.format('')

        return text

    def _html_report(self):
        ''' Export data to HTML web page '''
        html = htmlWorker('./report/report.html', './report/index.html')
        curr_date = date.today().strftime("%d %b %Y")
        ukr_today = self.db.get({'date': curr_date})['Україна']
        render_cfg = {}

        # upload paths for regions
        with open('./report/regions.map', 'r+') as fp:
            regions_map = json.load(fp)

        # total info
        # <div id="total" title="Україна" tested="77752" sick="7647" recovered="601" dead="193" style="display: none;"></div>
        total_tmpl = '<div id="total" title="{}" tested="{}" sick="{}" recovered="{}" dead="{}" style="display: none;"></div>'
        total = total_tmpl.format('Україна',
                                  ukr_today['Tested'], ukr_today['Sick'],
                                  ukr_today['Recovered'], ukr_today['Dead'])

        render_cfg['total'] = total

        # updated info
        # <p id="toptitle">📆 станом на 24 квітня 2020 року</p>
        upd_tmpl = '<p id="toptitle">📆 станом на {} року</p>'
        updated = upd_tmpl.format(curr_date)

        render_cfg['updated'] = updated

        # regions info
        # <path id="UA-01" title="м.Київ" tested="—" sick="1122" recovered="—" dead="—" style="fill: rgb(255, 126, 126);" class="land enabled" d="M291.42,101.4L291.62,104.23L293.29,105.74L293.29,105.74L293.48,107.55L292.13,109.37L290.2,110.27L288.65,109.27L287.49,109.77L287.75,116.31L286.85,117.31L284.85,115.4L283.75,110.68L281.24,109.87L280.4,107.35L278.86,106.95L278.41,104.93L275.83,105.13L274.22,106.34L275.06,101.7L275.06,101.7L276.6,99.88L276.6,99.88L277.83,99.48L276.47,97.25L281.56,97.45L284.59,100.69L289.04,99.78L291.49,97.55L293.94,98.77L293.94,100.18L291.74,100.79L291.74,100.79z"/>
        regs_tmpl = '<path title="{}" tested="—" sick="{}" recovered="—" dead="—" style="fill: rgb({}, {}, {});" class="land enabled" d="{}"/>\n'
        max_sick = max(ukr_today['Regions'].values())
        step_sick = max_sick / 256

        regions = ''
        for region, path in regions_map['Україна'].items():
            sick = ukr_today['Regions'].get(region, '—')
            nsick = 0 if sick == '—' else sick
            rgb = (255, int(255 - (nsick / step_sick)), int(255 - (nsick / step_sick)))
            regions += regs_tmpl.format(region, sick, *rgb, path)

        render_cfg['regions'] = regions

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
                     './report/map_ukr.svg',
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
    covid.update(['ukr', 'isr'])

    if args.web_update:
        covid.webpage_update('covidinfo.zzz.com.ua')

    print(covid)


if __name__ == '__main__':
    main()
