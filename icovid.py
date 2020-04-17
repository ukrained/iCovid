#!/usr/bin/python3

# metadata
__title__ = 'iCovid Monitoring Utility'
__version__ = '0.1.0[a]'
__release__ = '17 Apr 2020'
__author__ = 'Oleksandr Viytiv'

# modules
import urllib.request
import urllib.parse
import re

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

    def html_get_node(self, html, pattern, nid=None):
        ''' Function lookup HTML content

        :param html: WEB page HTML data
        :param pattern: regex pattern for node
        :param nid: Node ID if user want specific node
        :return: all nodes found
        '''
        nodes = re.findall(r'<p>(.*?)</p>', str(html))

        # for item in paragraphs:
        #    text = 'Block:\n{}\n'.format(item)
        #    print(text)
        return nodes[nid] if nid else nodes


class iCovid (iCovidBase):
    def __init__(self):
        ''' Constructor '''
        super().__init__()
        self.config = {'country': 'Україна', 'popl': 41880000, 'area': 603628,
                       'tested': 47096, 'sick': 4662, 'recovered': 246, 'dead': 125,
                       'regions': {}}

    def update(self):
        ''' Update latest data '''
        # 'oblasti': 'https://moz.gov.ua/article/news/operativna-informacija-pro-poshirennja-koronavirusnoi-infekcii-2019-ncov-',
        # 'zagalom': 'https://covid19.gov.ua/'
        pass

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

        text = '\n'
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
            zone_colour = {0: colour.NORMAL, 1: colour.fg.yellow,
                           2: colour.fg.orange, 3: colour.fg.lightred,
                           4: colour.fg.red}

            line = ''
            for i, key in enumerate(regions):
                # depending of the value, region will have its colour
                clr = zone_colour[(regions[key] - min_cases) // zone_step]
                line += '  {:.<40} [{}]'.format(self.logger.encolour(clr, key) + ' ',
                                                regions[key])
                if i % 2:
                    text += line + '\n'
                    line = ''
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
    print(covid)


if __name__ == '__main__':
    main()
