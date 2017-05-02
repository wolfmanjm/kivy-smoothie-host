from kivy.uix.floatlayout import FloatLayout
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder

import os

Builder.load_string('''
#:import os os
<LoadDialog>:
    BoxLayout:
        size: root.size
        pos: root.pos
        orientation: "vertical"
        FileChooserIconView:
            id: filechooser
            multiselect: False
            path: os.path.expanduser("~")
            title: 'File to print'
            filters: ['*.g', '*.gcode', '*.nc']

        BoxLayout:
            size_hint_y: None
            height: 30
            Button:
                text: "Cancel"
                on_release: root.cancel()

            Button:
                text: "Load"
                on_release: root.load(filechooser.path, filechooser.selection)
''')

class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

class FileDialog(FloatLayout):
    """File Dialog"""

    def __init__(self, arg):
        super(FileDialog, self).__init__()
        self.cb = arg

    def dismiss_popup(self):
        self._popup.dismiss()

    def open(self):
        file_path= None
        directory= None
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup)
        self._popup = Popup(title="File to Print", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        self.dismiss_popup()
        if len(filename) > 0:
            self.cb(filename[0], path)
