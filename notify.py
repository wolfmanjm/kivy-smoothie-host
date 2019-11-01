import smtplib
import configparser
from kivy.logger import Logger


class Notify():
    """Send an Email to notify user"""

    @staticmethod
    def send(msg):
        try:
            config = configparser.ConfigParser()
            config.read('notify.ini')
            # load user defined email settings
            user = config.get('authentication', 'user', fallback=None)
            password = config.get('authentication', 'password', fallback=None)
            server = config.get('authentication', 'server', fallback=None)
            port = config.getint('authentication', 'port', fallback=465)
            to_addr = config.get('header', 'to_address', fallback=None)
            subject = config.get('header', 'subject', fallback='Smoopi notification')

        except Exception as err:
            Logger.error('Notify: notify.ini file errors: {}'.format(err))
            return False

        if user is None:
            Logger.error('Notify: no user specified')
            return False
        if password is None:
            Logger.error('Notify: no password specified')
            return False
        if server is None:
            Logger.error('Notify: no server specified')
            return False
        if to_addr is None:
            Logger.error('Notify: no to address specified')
            return False

        body = '{}\n'.format(msg)

        email_text = """\
From: %s
To: %s
Subject: %s

%s
""" % (user, to_addr, subject, body)

        try:
            server = smtplib.SMTP_SSL(server, port)
            server.ehlo()
            server.login(user, password)
            server.sendmail(user, to_addr, email_text)
            server.close()
            return True

        except Exception as ex:
            Logger.error('Notify: Failed to send email: {}'.format(ex))
            return False
