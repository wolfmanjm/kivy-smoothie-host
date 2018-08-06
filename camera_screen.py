from kivy.app import App
from kivy.uix.image import AsyncImage
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.properties import StringProperty

Builder.load_string('''
<CameraScreen>:
    on_enter: self.start_timer()
    on_leave: self.stop_timer()
    BoxLayout:
        orientation: 'vertical'

        AsyncImage:
            id: ai
            size_hint: 0.8, 0.8
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            mipmap: True
            source: root.url
            nocache: True

        Button:
            size_hint_y: None
            height: 40
            text: 'Back'
            on_press: root.manager.current= 'main'
''')


class CameraScreen(Screen):
    url= StringProperty()
    def _do_refresh(self, d):
        try:
            self.ids.ai.reload()
        except:
            self.clk.cancel()

    def start_timer(self):
        self.url= 'http://192.168.1.11:8000/?action=snapshot' #'http://localhost:8080/?action=snapshot'
        self.clk= Clock.schedule_interval(self._do_refresh, 1)

    def stop_timer(self):
        self.clk.cancel()
        self.clk= None
