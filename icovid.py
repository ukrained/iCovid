#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '0.1.4[a]'
__release__ = '17 Apr 2020'
__author__ = 'Oleksandr Viytiv'

# modules
import urllib.request
import urllib.parse
import re

from lxml import html
from datetime import datetime
from utils import colour, logLevel, logger


class iCovidBase:
    ''' Base class with common functionality '''
    def __init__(self):
        self.logger = logger(logLevel.NORMAL)

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
        super().__init__()
        self.config = {'country': 'Україна', 'popl': 41880000, 'area': 603628,
                       'tested': 0, 'sick': 0, 'recovered': 0, 'dead': 0,
                       'regions': {}}
        self._updated = 0

    def update(self):
        ''' Update latest data '''
        self.logger.normal('Оновлення даних ..')

        self.__update_total()
        self.__update_regions()

        self.logger.success('Оновлення виконано')
        self._updated = datetime.now()

    def __update_total(self):
        # covid19.gov.ua
        self.logger.normal('Збір загальних даних ..')
        page = self.web_request('https://covid19.gov.ua/')

        divs = self.html_get_node(page, './/div[@class="one-field light-box info-count"]')
        if len(divs) != 4:
            self.logger.error('Not expected number of nodes - %d' % len(divs))
            exit(1)

        for i, case in enumerate(['tested', 'sick', 'recovered', 'dead']):
            self.config[case] = divs[i].xpath('.//div')[0].text.strip()

        self.logger.success('Загальні дані оновлено')

    def __update_regions(self):
        # moz.gov.ua
        self.logger.normal('Збір даних про регіони ..')
        page = self.web_request('https://moz.gov.ua/article/news/operativna-informacija-pro-poshirennja-koronavirusnoi-infekcii-2019-ncov-')

        regns = self.html_get_node(page, './/div[@class="editor"]//ul', nid=0)
        for region in regns:
            reg, cases = region.text.split(' — ')
            self.config['regions'][reg] = int(cases.strip().split()[0])

        self.logger.success('Інформацію про регіони оновлено')

    def __str__(self):
        ''' Show COVID information '''
        # get input data
        country = self.config.get('country', 'unknown')
        popl = self.config.get('popl', 0)
        area = self.config.get('area', 0)
        dens = popl / area
        tested = self.config.get('tested', '?')
        sick = self.config.get('sick', '?')
        recovered = self.config.get('recovered', '?')
        dead = self.config.get('dead', '?')
        regions = self.config.get('regions', {})

        # datetime object containing current date and time
        text = ' * Дані станом на {:%d %B %Y [%H:%M:%S]}\n\n'.format(self._updated)

        # total information
        text += '   [ %s ] ' % self.logger.encolour(colour.fg.cyan, country)
        text += '  %s %s' % (tested,
                             self.logger.encolour(colour.fg.grey, 'Перевірені'))
        text += '  %s %s' % (sick,
                             self.logger.encolour(colour.fg.yellow, 'Хворі'))
        text += '  %s %s' % (recovered,
                             self.logger.encolour(colour.fg.green, 'Одужали'))
        text += '  %s %s\n' % (dead,
                               self.logger.encolour(colour.fg.red, 'Померли'))
        text += ' .{:-<76}.\n'.format('')

        # country information
        text += '   {:,} людей на {:,} км2 ({:.2f} л/км2)\n'.format(popl, area, dens)
        text += ' +{:-<76}+\n'.format('')

        # regions information
        if regions:
            min_cases = min(regions.values())
            zone_step = (max(regions.values()) + 1 - min_cases) / 5
            zone_colour = {0: colour.fg.white, 1: colour.fg.yellow,
                           2: colour.fg.orange, 3: colour.fg.lightred,
                           4: colour.fg.red}

            line = ' '
            for i, key in enumerate(regions):
                # depending of the value, region will have its colour
                clr = zone_colour[(regions[key] - min_cases) // zone_step]
                line += '  {:.<38} {:<6}'.format(self.logger.encolour(clr, key) + ' ',
                                                 '[' + str(regions[key]) + ']')
                if i % 2:
                    text += line + '\n'
                    line = ' '
            text += (line + '\n') if line else ''  # in case of odd regions
        else:
            text += '  << Немає даних по регіонах >>\n'

        text += ' \'{:-<76}\'\n'.format('')

        return text

    def export(self):
        ''' Export to some file type: PDF, PNG etc. '''
        # TODO: future feature
        pass


def main():
    covid = iCovid()
    covid.update()
    print(covid)


if __name__ == '__main__':
    main()
