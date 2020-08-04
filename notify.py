import smtplib
import configparser
import logging
import threading


class Notify():
    """Send an Email to notify user"""
    def send(self, msg):
        self.logger = logging.getLogger()
        self.msg = msg
        threading.Thread(target=self._send).start()

    def _send(self):
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
            self.logger.error('Notify: notify.ini file errors: {}'.format(err))
            return False

        if user is None:
            self.logger.error('Notify: no user specified')
            return False
        if password is None:
            self.logger.error('Notify: no password specified')
            return False
        if server is None:
            self.logger.error('Notify: no server specified')
            return False
        if to_addr is None:
            self.logger.error('Notify: no to address specified')
            return False

        body = '{}\n'.format(self.msg)

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
            self.logger.error('Notify: Failed to send email: {}'.format(ex))
            return False


if __name__ == '__main__':
    notify = Notify()
    print("Sending...")
    notify.send("test message")
    print("...Sent")
