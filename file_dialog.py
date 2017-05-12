from kivy.uix.floatlayout import FloatLayout
from kivy.properties import StringProperty, ObjectProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.uix.filechooser import FileSystemLocal
from kivy.factory import Factory

import os
from os.path import getmtime

class FileSystemLocalEx(FileSystemLocal):
    def __init__(self):
        super(FileSystemLocalEx, self).__init__()

    def getdate(self, fn):
        return getmtime(fn)

Factory.register('filesystem', cls=FileSystemLocalEx)


Builder.load_string('''
#:import Factory kivy.factory.Factory
<LoadDialog>:
    BoxLayout:
        size: root.size
        pos: root.pos
        orientation: "vertical"
        FileChooser:
            id: filechooser
            multiselect: False
            path: root.path
            title: 'File to print'
            filters: ['*.g', '*.gcode', '*.nc']
            sort_func: lambda a, b: root.sort_folders_first(sort_type.state == 'normal', reverse.state == 'down', a, b)
            file_system: Factory.filesystem()
            FileChooserIconLayout
            FileChooserListLayout

        BoxLayout:
            size_hint_y: None
            height: 30
            ToggleButton:
                text: 'list view' if self.state == 'normal' else 'icon view'
                on_state: filechooser.view_mode = 'icon' if self.state == 'normal' else 'list'

            ToggleButton:
                id: sort_type
                text: 'Sort by Date'
                on_state: filechooser._update_files()

            ToggleButton:
                id: reverse
                text: 'Newer First'
                disabled: sort_type.state == 'normal'
                on_state: filechooser._update_files()

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

    def sort_folders_first(self, b, r, files, filesystem):
        if b:
            return (sorted(f for f in files if  filesystem.is_dir(f)) +
                    sorted(f for f in files if not filesystem.is_dir(f)))
        else:
            # reverse sort by date
            return ([a[1] for a in sorted(((filesystem.getdate(f),f) for f in files), key=lambda x: x[0], reverse=r)])


class FileDialog(FloatLayout):
    """File Dialog"""
    def __init__(self):
        super(FileDialog, self).__init__()
        self.cb = None

    def dismiss_popup(self):
        self._popup.dismiss()

    def open(self, path= None, title= "File to Print", cb= None):
        self.cb= cb
        content = LoadDialog(load=self.load, cancel=self.dismiss_popup, path=path if path else os.path.expanduser("~"))
        self._popup = Popup(title=title, content=content,
                            size_hint=(0.9, 0.9))
        self._popup.open()

    def load(self, path, filename):
        self.dismiss_popup()
        if len(filename) > 0 and self.cb:
            self.cb(filename[0], path)
