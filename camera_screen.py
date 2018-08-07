from kivy.app import App
from kivy.uix.image import AsyncImage
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import StringProperty
from kivy.uix.image import Image
from kivy.core.image import Image as CoreImage
from collections import deque
from kivy.logger import Logger, LOG_LEVELS
import io
import urllib.request
import threading

Builder.load_string('''
<MjpegViewer>:
    #url: 'http://192.168.1.72:8080/?action=stream'
    url: 'http://localhost:8080/?action=stream'

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

    url = StringProperty()

    def start(self):
        self.quit = False
        self._thread = threading.Thread(target=self.read_stream)
        self._thread.daemon = True
        self._thread.start()
        self._image_lock = threading.Lock()
        self._image_buffer = None
        self.read_queue= Clock.schedule_interval(self.update_image, 0.2)

    def stop(self):
        self.read_queue.cancel()
        self.quit = True
        self._thread.join()

    def read_stream(self):
        try:
            stream = urllib.request.urlopen(self.url)
        except Exception as err:
            self.quit= True
            Logger.error("MjpegViewer: Failed to open url: {} - error: {}".format(self.url, err))

        bytes = b''
        while not self.quit:
            bytes += stream.read(1024)
            a = bytes.find(b'\xff\xd8')
            b = bytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = bytes[a:b + 2]
                bytes = bytes[b + 2:]

                data = io.BytesIO(jpg)
                im = CoreImage(data,
                               ext="jpeg",
                               nocache=True)
                with self._image_lock:
                    self._image_buffer = im

    def update_image(self, *args):
        if self.quit:
            return

        im = None
        with self._image_lock:
            im = self._image_buffer
            self._image_buffer = None
        if im is not None:
            self.texture = im.texture
            self.texture_size = im.texture.size


class CameraScreen(Screen):

    def start(self):
        self.ids.viewer.start()

    def stop(self):
        self.ids.viewer.stop()
