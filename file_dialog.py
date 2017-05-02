from kivy.uix.floatlayout import FloatLayout
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder

import os

Builder.load_string('''
<LoadDialog>:
    BoxLayout:
        size: root.size
        pos: root.pos
        orientation: "vertical"
        FileChooserIconView:
            id: filechooser
            multiselect: False
            path: root.path
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
    path= StringProperty()

class FileDialog(FloatLayout):
    """File Dialog"""
    def __init__(self, arg):
        super(FileDialog, self).__init__()
        self.cb = arg

    def dismiss_popup(self):
        self._popup.dismiss()

    def open(self, path= None):
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup, path=path if path else os.path.expanduser("~"))
        self._popup = Popup(title="File to Print", content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        self.dismiss_popup()
        if len(filename) > 0:
            self.cb(filename[0], path)
