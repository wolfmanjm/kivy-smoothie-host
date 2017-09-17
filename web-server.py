import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import logging
from kivy.logger import Logger
import traceback

class RequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write("progress: ETA 01:01:00 50%".encode("utf-8"))
        # TODO query comms for linecnt and say if printing or not and what the progress is

    def do_POST(self):
        # Doesn't do anything with posted data
        self._set_headers()
        self.wfile.write("not handled".encode("utf-8"))


class ProgressServer(object):

    def start(self, port):
        self.myServer = HTTPServer(("", port), RequestHandler)
        Logger.info("ProgressServer: Web Server Starting - %s:%s" % ("", port))

        try:
    	    self.myServer.serve_forever()
        except:
            Logger.warn('ProgressServer: Exception: {}'.format(traceback.format_exc()))
        finally:
            self.myServer.server_close()
            Logger.info("ProgressServer: Web Server Stopping - %s:%s" % ("", port))

if __name__ == "__main__":

    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
    s= ProgressServer()
    s.start(8000)

