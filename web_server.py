import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import logging
from kivy.logger import Logger
import traceback
import threading
import socket


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        Logger.warn('ProgressServer: get_ip failed with: {}'.format(traceback.format_exc()))
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def make_request_handler_class(app, ip):
    class MyRequestHandler(BaseHTTPRequestHandler):
        m_app = app
        m_ip = ip

        def _set_headers(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

        def do_GET(self):
            self._set_headers()
            # TODO query comms for linecnt and say if printing or not and what the progress is
            status = MyRequestHandler.m_app.status
            if MyRequestHandler.m_app.main_window.is_printing:
                eta = MyRequestHandler.m_app.main_window.eta
                file = MyRequestHandler.m_app.gcode_file
                self.wfile.write('<head><meta http-equiv="refresh" content="5"></head>\r\n'.encode("utf-8"))
                self.wfile.write("{} - ETA: {}, File: {}".format(status, eta, file).encode("utf-8"))
            else:
                self.wfile.write("{} - Not Running".format(status).encode("utf-8"))

            if MyRequestHandler.m_app.is_show_camera:
                self.wfile.write('\r\n<hr><center><img src="http://{}:8080/?action=stream" /></center>\r\n'.format(MyRequestHandler.m_ip).encode("utf-8"))

        def do_POST(self):
            # Doesn't do anything with posted data
            self._set_headers()
            self.wfile.write("not handled".encode("utf-8"))

    return MyRequestHandler


class ProgressServer(object):
    def start(self, app, port):
        self.port = port
        self.app = app
        t = threading.Thread(target=self._start)
        t.start()

    def _start(self):
        ip = get_ip()
        Logger.info("ProgressServer: IP address is: {}".format(ip))
        RequestHandlerClass = make_request_handler_class(self.app, ip)
        self.myServer = HTTPServer(("", self.port), RequestHandlerClass)
        Logger.info("ProgressServer: Web Server Starting - %s:%s" % ("", self.port))

        try:
            self.myServer.serve_forever()
        except Exception:
            Logger.warn('ProgressServer: Exception: {}'.format(traceback.format_exc()))
        finally:
            self.myServer.server_close()
            Logger.info("ProgressServer: Web Server Stopping - %s:%s" % ("", self.port))
            self.myServer = None

    def stop(self):
        if self.myServer:
            self.myServer.shutdown()


if __name__ == "__main__":

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    s = ProgressServer()
    s.start(8000)
