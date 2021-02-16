import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import logging
import traceback
import threading
import socket

logger = logging.getLogger()

main_page = '''
<html>
<body>
<h1>Smoopi status page</h1>

<div id="statusDiv">
<iframe src="status" height="64" width="800">
</iframe>
</div>

<br/>

<iframe src="camera" height="500" width="800">
</iframe>

</body>
</html>
'''


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        logger.warn('ProgressServer: get_ip failed with: {}'.format(traceback.format_exc()))
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
            if self.path == '/status':
                status = MyRequestHandler.m_app.status
                if MyRequestHandler.m_app.main_window.is_printing:
                    eta = MyRequestHandler.m_app.main_window.eta
                    file = MyRequestHandler.m_app.gcode_file
                    wpos = MyRequestHandler.m_app.wpos
                    self.wfile.write("<html>\r\n".encode("utf-8"))
                    self.wfile.write('<head><meta http-equiv="refresh" content="5"></head><body>\r\n'.encode("utf-8"))

                    self.wfile.write("{} - Z: {}, {}, File: {}".format(status, wpos[2], eta, file).encode("utf-8"))
                    self.wfile.write("</body></html>\r\n".encode("utf-8"))
                else:
                    self.wfile.write("{} - Not Running".format(status).encode("utf-8"))

            elif self.path == '/camera':
                self.wfile.write("<html><body>\r\n".encode("utf-8"))
                if MyRequestHandler.m_app.is_show_camera:
                    camurl = MyRequestHandler.m_app.camera_url
                    if "localhost" in camurl:
                        # we need to replace localhost with actual ip so remote browsers can get it
                        camurl = camurl.replace("localhost", MyRequestHandler.m_ip)
                    self.wfile.write('\r\n<center><img src="{}" /></center>\r\n'.format(camurl).encode("utf-8"))
                else:
                    self.wfile.write('camera not enabled'.encode("utf-8"))
                self.wfile.write("</body></html>\r\n".encode("utf-8"))

            else:
                self.wfile.write(main_page.encode("utf-8"))

        def do_POST(self):
            # Doesn't do anything with posted data
            self._set_headers()
            self.wfile.write("not handled".encode("utf-8"))

        def log_message(self, format, *args):
            return

    return MyRequestHandler


class ProgressServer(object):
    def start(self, app, port):
        self.port = port
        self.app = app
        self.myServer = None
        self.t = threading.Thread(target=self._start)
        self.t.start()

    def _start(self):
        ip = get_ip()
        logger.info("ProgressServer: IP address is: {}".format(ip))
        RequestHandlerClass = make_request_handler_class(self.app, ip)
        self.myServer = HTTPServer(("", self.port), RequestHandlerClass)
        logger.info("ProgressServer: Web Server Starting - %s:%s" % ("", self.port))

        try:
            self.myServer.serve_forever()
        except Exception:
            logger.warn('ProgressServer: Exception: {}'.format(traceback.format_exc()))
        finally:
            self.myServer.server_close()
            logger.info("ProgressServer: Web Server Stopping - %s:%s" % ("", self.port))
            self.myServer = None

    def stop(self):
        if self.myServer:
            self.myServer.shutdown()
            self.t.join()


if __name__ == "__main__":
    class MainWindow(object):
        """docstring for MainWindow"""
        def __init__(self):
            super(MainWindow, self).__init__()
            self.is_printing = False

    class MyApp(object):
        """docstring for MyApp"""
        def __init__(self):
            super(MyApp, self).__init__()
            self.status = "Not Connected"
            self.is_show_camera = False
            self.main_window = MainWindow()
            self.camera_url = 'http://camipaddress:port'
            # self.camera_realm = 'CameraServer'
            # self.camera_user = 'user'
            # self.camera_password = 'pw'
            # self.camera_singleshot = 1

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    s = ProgressServer()
    s.start(MyApp(), 8000)
