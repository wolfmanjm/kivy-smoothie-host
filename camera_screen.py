from kivy.app import App
from kivy.uix.image import AsyncImage
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock, mainthread
from kivy.properties import StringProperty
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from kivy.logger import Logger, LOG_LEVELS
import io
import urllib.request
import threading
import time

Builder.load_string('''
<MjpegViewer>:

<CameraScreen>:
    on_enter: self.start()
    on_leave: self.stop()
    BoxLayout:
        orientation: 'vertical'
        MjpegViewer:
            id: viewer
        Button:
            size_hint_y: None
            height: 40
            text: 'Back'
            on_press: root.manager.current= 'main'
''')


class MjpegViewer(Image):

    def start(self):
        app = App.get_running_app()
        self.url = app.camera_url
        self.realm = app.config.get('Web', 'camera_realm', fallback=None)
        self.user = app.config.get('Web', 'camera_user', fallback=None)
        self.pw = app.config.get('Web', 'camera_password', fallback=None)
        self.singleshot = app.config.getboolean('Web', 'camera_singleshot', fallback=False)
        self.quit = False
        self.t = threading.Thread(target=self._read_stream)
        self.t.start()

    def stop(self):
        self.quit = True
        self.t.join()

    def _read_stream(self):
        try:
            if self.realm and self.user and self.pw:
                auth_handler = urllib.request.HTTPBasicAuthHandler()
                auth_handler.add_password(realm=self.realm, uri=self.url, user=self.user, passwd=self.pw)
                opener = urllib.request.build_opener(auth_handler)
                urllib.request.install_opener(opener)

            stream = urllib.request.urlopen(self.url)

        except Exception as err:
            if hasattr(err, 'code') and err.code == 401:
                Logger.error("MjpegViewer: url: {} - requires authentication: {}".format(self.url, err.headers['www-authenticate']))

            self.quit = True
            Logger.error("MjpegViewer: Failed to open url: {} - error: {}".format(self.url, err))
            return None

        Logger.info("MjpegViewer: started thread")

        bytes = b''
        while not self.quit:
            try:
                # read in stream until we get the entire frame
                bytes += stream.read(1024)
                a = bytes.find(b'\xff\xd8')
                b = bytes.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = bytes[a:b + 2]
                    bytes = bytes[b + 2:]

                    data = io.BytesIO(jpg)
                    im = CoreImage(data, ext="jpeg", nocache=True)
                    self.update_image(im)

                    if self.singleshot:
                        # camera only supplies a snapshot not a stream
                        time.sleep(0.2)
                        stream = urllib.request.urlopen(self.url)
                        bytes = b''

            except Exception as err:
                Logger.error("MjpegViewer: Failed to read_queue url: {} - error: {}".format(self.url, err))
                return None

        Logger.info("MjpegViewer: ending thread")

    @mainthread
    def update_image(self, im):
        if self.quit:
            return

        if im is not None:
            self.texture = im.texture
            self.texture_size = im.texture.size


class CameraScreen(Screen):
    def start(self):
        self.ids.viewer.start()

    def stop(self):
        self.ids.viewer.stop()
