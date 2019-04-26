from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
import time

Builder.load_string('''
<SpindleCamera>:
    BoxLayout:
        orientation: 'vertical'
        canvas.after:
            Color:
                rgb: 1, 0, 0
            Line:
                points: [self.center_x, 0, self.center_x, self.height]
                width: 1
                cap: 'none'
                joint: 'none'
            Line:
                points: [0, self.center_y, self.width, self.center_y]
                width: 1
                cap: 'none'
                joint: 'none'
            Line:
                circle:
                    (self.center_x, self.center_y, 20)

        camera: camera
        Camera:
            id: camera
            resolution: (640, 480)
            play: False
''')


class SpindleCamera(Screen):
    def capture(self):
        '''
        Function to capture the images and give them the names
        according to their captured time and date.
        '''
        camera = self.ids['camera']
        timestr = time.strftime("%Y%m%d_%H%M%S")
        camera.export_to_png("IMG_{}.png".format(timestr))


if __name__ == '__main__':

    Builder.load_string('''
<StartScreen>:
    BoxLayout:
        ToggleButton:
            id: play_but
            text: 'Play'
            on_press: app.play()
            size_hint_y: None
            height: '48dp'
        Button:
            text: 'Capture'
            size_hint_y: None
            height: '48dp'
            on_press: app.capture()
''')

    class StartScreen(Screen):
        pass

    class TestCamera(App):

        def build(self):
            # Window.size = (800, 480)
            self.sc = SpindleCamera(name='spindle camera')
            self.scr = StartScreen(name='main')
            self.sm = ScreenManager()
            self.sm.add_widget(self.scr)
            self.sm.add_widget(self.sc)

            return self.sm

        def play(self):
            self.sc.ids['camera'].play = self.scr.ids['play_but'].state != 'normal'
            self.sm.current = 'spindle camera'

        def capture(self):
            self.sc.capture()

    TestCamera().run()
