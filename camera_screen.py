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

    def start(self, url):
        self.url = url
        self.quit = False
        self.t = threading.Thread(target=self._read_stream)
        self.t.start()

    def stop(self):
        self.quit = True
        self.t.join()

    def _read_stream(self):
        try:
            stream = urllib.request.urlopen(self.url)
        except Exception as err:
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
        url = App.get_running_app().camera_url
        self.ids.viewer.start(url)

    def stop(self):
        self.ids.viewer.stop()
