# metadata
__title__ = 'Common Utils Library'
__version__ = '0.6.9[b]'
__release__ = '17 Aug 2020'
__author__ = 'Alex Viytiv'


class colour:
    ''' Colour class '''
    NORMAL = '\033[0m'      # return normal font style
    BOLD = '\033[01m'       # make text bold
    DISABLE = '\033[02m'    # ???
    UNDERLINE = '\033[04m'  # underline text
    BLINK = '\033[05m'      # blinking text
    REVERSE = '\033[07m'    # ???
    STRIKE = '\033[09m'     # put strikeline over text
    INVISIBLE = '\033[08m'  # ???

    # foreground colours
    class fg:
        black = '\033[30m'
        grey = '\033[90m'
        red = '\033[31m'
        green = '\033[32m'
        blue = '\033[34m'
        cyan = '\033[36m'
        orange = '\033[33m'
        yellow = '\033[93m'
        purple = '\033[35m'
        pink = '\033[95m'
        white = '\033[37m'
        lightred = '\033[91m'
        lightgreen = '\033[92m'
        lightblue = '\033[94m'
        lightcyan = '\033[96m'

    # background colours
    class bg:
        black = '\033[40m'
        red = '\033[41m'
        green = '\033[42m'
        blue = '\033[44m'
        cyan = '\033[46m'
        orange = '\033[43m'
        purple = '\033[45m'
        white = '\033[47m'

    def set(clr, msg):
        ''' Colorize message into '''
        return clr + str(msg) + colour.NORMAL


class logLevel:
    ''' Logging level class '''
    CRITICAL = 0  # component, subsystem crash
    ERROR = 1     # unexpected flow behaviour
    WARNING = 2   # suspicious flow behaviour
    SUCCESS = 3   # successful operation
    NORMAL = 4    # usual log message for user
    DEBUG = 5     # message contain development info
    TRACE = 6     # any trash you want

    # string to describe log level
    token = {CRITICAL: 'КРИТИЧНО',
             ERROR: 'ПОМИЛКА',
             WARNING: 'Увага',
             SUCCESS: 'Успіх',
             NORMAL: 'норма',
             DEBUG: 'зневадження',
             TRACE: 'відстеження'}

    # color for each log level
    colour = {CRITICAL: colour.bg.red,
              ERROR: colour.fg.red,
              WARNING: colour.fg.orange,
              SUCCESS: colour.fg.green,
              NORMAL: colour.fg.yellow,
              DEBUG: colour.fg.blue,
              TRACE: colour.fg.lightcyan}


class logger:
    ''' Logger object provide logging subsystem '''
    def __init__(self, gllvl):
        ''' Constructor

        :param gllvl: Global Logging Level
        '''
        self._gllvl = gllvl

    def get_lvl(self):
        return self._gllvl

    def print(self, msg, end='.\n'):
        ''' Print user message anyway

        :param msg: message itself
        :param end: message end sequence
        '''
        print(msg, end=end)

    def log(self, lvl, msg, raw=False, end='.\n'):
        ''' Print log message

        :param lvl: user-defined log level of message
        :param msg: message itself
        :param raw: flag to disable msg postformatting
        :param end: message end sequence
        '''

        if lvl > self._gllvl or lvl < logLevel.CRITICAL:
            # invalid log level
            return

        prefix = '[%s%s%s] ' % (logLevel.colour[lvl], logLevel.token[lvl],
                                colour.NORMAL)

        print(('' if raw else prefix) + str(msg), end=end)

    def critical(self, msg, end='.\n'):
        ''' Print critical level log '''
        self.log(logLevel.CRITICAL, msg, end=end)

    def error(self, msg, end='.\n'):
        ''' Print error level log '''
        self.log(logLevel.ERROR, msg, end=end)

    def warning(self, msg, end='.\n'):
        ''' Print warning level log '''
        self.log(logLevel.WARNING, msg, end=end)

    def success(self, msg, end='.\n'):
        ''' Print success level log '''
        self.log(logLevel.SUCCESS, msg, end=end)

    def normal(self, msg, end='.\n'):
        ''' Print normal level log '''
        self.log(logLevel.NORMAL, msg, end=end)

    def debug(self, msg, end='.\n'):
        ''' Print debug level log '''
        self.log(logLevel.DEBUG, msg, end=end)

    def trace(self, msg, end='.\n'):
        ''' Print trace level log '''
        self.log(logLevel.TRACE, msg, end=end)

    def approve(self, msg, default=False):
        ''' Get user approve

        :param msg: user message
        :return: TRUE if approved, FALSE otherwise
        '''
        resp = input('> {}? [{}/{}] '.format(msg,
                                             'Y' if default else 'y',
                                             'n' if default else 'N'))
        if resp in ['y', 'ye', 'yes']:
            return True
        elif resp in ['n', 'no']:
            return False

        self.warning('Недійсна відповідь "{}". Дія за умовчанням [{}]'.format(resp, default))
        return default
