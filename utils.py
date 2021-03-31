# metadata
__title__ = 'Common Utils Library'
__version__ = '0.8.0[b]'
__release__ = '02 Nov 2020'
__author__ = 'Alex Viytiv'

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class Font:
    ''' Font class '''
    NORMAL = '\033[0m'      # return normal font style
    BOLD = '\033[01m'       # make text bold
    DISABLE = '\033[02m'    # ???
    UNDERLINE = '\033[04m'  # underline text
    BLINK = '\033[05m'      # blinking text
    REVERSE = '\033[07m'    # ???
    STRIKE = '\033[09m'     # put strikeline over the text
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
        return clr + str(msg) + Font.NORMAL


class LogLevel:
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
    colour = {CRITICAL: Font.bg.red,
              ERROR: Font.fg.red,
              WARNING: Font.fg.orange,
              SUCCESS: Font.fg.green,
              NORMAL: Font.fg.yellow,
              DEBUG: Font.fg.blue,
              TRACE: Font.fg.lightcyan}


class Logger:
    ''' Logger object provide logging subsystem '''
    def __init__(self, lvl):
        ''' Constructor

        :param gllvl: Global Logging Level
        '''
        self._gllvl = lvl
        self._is_user_active = True

    def set_lvl(self, lvl):
        ''' Configure logging level

        :param lvl: desired user logging level
        '''
        if lvl not in LogLevel.token:
            # desired log level is not valid
            return False

        self._gllvl = lvl
        return True

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

        if lvl > self._gllvl or lvl < LogLevel.CRITICAL:
            # invalid log level
            return

        prefix = '[%s%s%s] ' % (LogLevel.colour[lvl], LogLevel.token[lvl],
                                Font.NORMAL)

        print(('' if raw else prefix) + str(msg), end=end)

    def critical(self, msg, end='.\n'):
        ''' Print critical level log '''
        self.log(LogLevel.CRITICAL, msg, end=end)

    def error(self, msg, end='.\n'):
        ''' Print error level log '''
        self.log(LogLevel.ERROR, msg, end=end)

    def warning(self, msg, end='.\n'):
        ''' Print warning level log '''
        self.log(LogLevel.WARNING, msg, end=end)

    def success(self, msg, end='.\n'):
        ''' Print success level log '''
        self.log(LogLevel.SUCCESS, msg, end=end)

    def normal(self, msg, end='.\n'):
        ''' Print normal level log '''
        self.log(LogLevel.NORMAL, msg, end=end)

    def debug(self, msg, end='.\n'):
        ''' Print debug level log '''
        self.log(LogLevel.DEBUG, msg, end=end)

    def trace(self, msg, end='.\n'):
        ''' Print trace level log '''
        self.log(LogLevel.TRACE, msg, end=end)

    def approve(self, msg, default=False):
        ''' Get user approve

        :param msg: user message
        :return: TRUE if approved, FALSE otherwise
        '''
        if not self._is_user_active:
            # send default reply if there is no user
            self.normal('Ввімкнено режим "Без користувача". Виконується дія за умовчанням')
            return default

        resp = input('> {}? [{}/{}] '.format(msg,
                                             'Y' if default else 'y',
                                             'n' if default else 'N'))
        if resp in ['y', 'ye', 'yes']:
            return True
        elif resp in ['n', 'no']:
            return False

        self.warning('Недійсна відповідь "{}". Дія за умовчанням [{}]'.format(resp, default))
        return default

    def userless_mode(self, enable):
        """ Function is used to activate in logger userless mode """
        self._is_user_active = False if enable else True
        self.normal('Режим "Без користувача" {}'.format('ввімкнено' if enable else 'вимкнено'))


class Email:
    """ Object used to store email data """
    def __init__(self, to_email, subject, msg, is_html=True):
        self.message = MIMEMultipart('alternative')
        self.message['To'] = to_email
        self.message['Subject'] = subject

        # Add HTML/plain-text parts to MIMEMultipart message
        # The email client will try to render the last part first
        self.message.attach(MIMEText(msg, 'html' if is_html else 'plain'))

    def get_to(self):
        return self.message['To']

    def get_message(self):
        return self.message.as_string()
