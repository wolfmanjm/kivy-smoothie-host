import kivy

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder
from kivy.core.window import Window

import subprocess
import configparser

Builder.load_string('''
<CalcButt@Button>
    on_press: self.parent.parent.parent.do_action(self.text)
    font_size: sp(30)
<CalcScreen>:
    display: entry

    GridLayout:
        rows: 7
        padding: 2
        spacing: 4
        BoxLayout:
            TextInput:
                id: entry
                multiline: False
                on_text_validate: root.handle_input(self.text)
                readonly: True
                is_focusable: False
                use_bubble: False
                use_handles: False
                font_size: sp(30)
            Button:
                size_hint_x: None
                width: dp(100)
                text: '<-'
                font_size: sp(30)
                on_press: entry.text = entry.text[:-1]
            Button:
                size_hint_x: None
                width: dp(100)
                text: 'Clr'
                font_size: sp(30)
                on_press: entry.text = ""

        BoxLayout:
            CalcButt:
                text: '1'
            CalcButt:
                text: '2'
            CalcButt:
                text: '3'
            CalcButt:
                text: '+'

        BoxLayout:
            CalcButt:
                text: '4'
            CalcButt:
                text: '5'
            CalcButt:
                text: '6'
            CalcButt:
                text: '-'

        BoxLayout:
            CalcButt:
                text: '7'
            CalcButt:
                text: '8'
            CalcButt:
                text: '9'
            CalcButt:
                text: '/'

        BoxLayout:
            CalcButt:
                text: '_'
            CalcButt:
                text: '0'
            CalcButt:
                text: '.'
            CalcButt:
                text: '*'

        BoxLayout:
            Button:
                text: 'Off'
                font_size: sp(30)
                on_press: root.manager.current = 'main'
            CalcButt:
                text: 'Space'
            CalcButt:
                text: 'Space'
            CalcButt:
                text: '='
 ''')


class CalcScreen(Screen):
    def __init__(self, **kwargs):
        super(CalcScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        config = configparser.ConfigParser()
        config.read('smoothiehost.ini')
        self.backend = config.get('General', 'calc_backend', fallback="dc")

    def _add_line_to_log(self, s):
        self.app.main_window.display(s)

    def do_action(self, key):
        if key == '=':
            res = self._do_calc(self.display.text)
            self.display.text = res
        elif key == 'Space':
            self.display.text += " "
        elif key == '_' and self.backend != "dc":
            self.display.text += "-"
        else:
            self.display.text += key

    def _do_calc(self, txt):
        self.app.main_window.display(">>> {}".format(txt))
        # send to unix shell
        try:
            if self.backend == 'dc':
                p = subprocess.Popen("dc", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                result, err = p.communicate(timeout=5, input="10 k {} p".format(txt))
            elif self.backend == 'bc':
                p = subprocess.Popen("bc", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                result, err = p.communicate(timeout=5, input="scale=10; {}\n".format(txt))
            else:
                result = "{}".format(eval(txt))
                self.app.main_window.display("<<< {}".format(result))
                return result

            if p.returncode == 0:
                self.app.main_window.display("<<< {}".format(result))
                return " ".join(result.splitlines())

        except subprocess.TimeoutExpired:
            p.kill()
            self.app.main_window.display('<<< calculator timed out')

        except Exception as err:
            self.app.main_window.display('<<< calculator error: {}'.format(err))

        return "Error"


if __name__ == '__main__':

    Builder.load_string('''
<ExitScreen>:
    on_enter: app.stop()
''')

    class ExitScreen(Screen):
        pass

    class MainWindow:
        def display(self, x):
            print(x)

    class CalcApp(App):
        def __init__(self, **kwargs):
            super(CalcApp, self).__init__(**kwargs)
            self.main_window = MainWindow()

        def build(self):
            Window.size = (800, 600)
            self.sm = ScreenManager()
            self.sm.add_widget(CalcScreen(name='calculator'))
            self.sm.add_widget(ExitScreen(name='main'))
            self.sm.current = 'calculator'
            return self.sm

    CalcApp().run()
