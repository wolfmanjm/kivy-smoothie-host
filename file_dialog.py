from kivy.uix.floatlayout import FloatLayout
from kivy.properties import ListProperty, StringProperty, ObjectProperty, BooleanProperty
from kivy.uix.popup import Popup
from kivy.lang import Builder
from kivy.uix.filechooser import FileSystemLocal, FileSystemAbstract
from kivy.factory import Factory

import os
from os.path import getmtime


class FileSystemLocalEx(FileSystemLocal):
    def __init__(self):
        super(FileSystemLocalEx, self).__init__()

    def getdate(self, fn):
        return getmtime(fn)


Factory.register('filesystem', cls=FileSystemLocalEx)


class FileSystemSDCard(FileSystemAbstract):
    '''
        Implementation of :class:`FileSystemAbstract` for sdcard files.

        We need to read the SDCard directory in full then populate this with a call to open(files)
        where files is a dict with { filename: {'size': nnn, 'isdir': False}, ..., }

        As there appears no way to do a non blocking file system that is remote and is fetched a line at a time.

        Also because if this we can only show one directory, so we show the root /sd/ only.

        If there were a way to delay listdir and make a remote call get the results then return the listdir we could allow
        traversal.

        The only other way is to read the entire sdcard directory tree into the dict, which is not really a practical option.
    '''

    def __init__(self, **kwargs):
        super(FileSystemSDCard, self).__init__(**kwargs)
        self._files = None

    def open(self, files):
        ''' files is a dict with { filename: {size: nnn, isdir: False}, ..., } '''
        self._files = files

    def listdir(self, fn):
        if self._files is None:
            return []

        return self._files.keys()

    def getsize(self, fn):
        if self._files is None:
            return 0

        return self._files[fn]['size']

    def getdate(self, fn):
        if self._files is None:
            return 0

        # sd does not have date at the moment
        return 0

    def is_hidden(self, fn):
        return False

    def is_dir(self, fn):
        if self._files is None:
            return False

        if fn == '/' or fn == '../':
            return True

        return self._files[fn]['isdir']


Factory.register('filesystemsd', cls=FileSystemSDCard)

Builder.load_string('''
#:import Factory kivy.factory.Factory
<LoadDialog>:
    BoxLayout:
        size: root.size
        pos: root.pos
        orientation: "vertical"

        Label:
            size_hint: None, None
            size: self.texture_size[0], 40
            text: filechooser.path

        FileChooser:
            id: filechooser
            multiselect: False
            dirselect: True # Because otherwise touch screen is broken
            path: root.path
            filter_dirs: not root.show_dirs
            filters: root.filters
            sort_func: lambda a, b: root.sort_folders_first(sort_type.state == 'normal', reverse.state == 'down', a, b)
            file_system: root.filesystem
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
                disabled: not (filechooser.selection and filechooser.selection[0] and not root.filesystem.is_dir(filechooser.selection[0]))
                on_release: root.load(filechooser.path, filechooser.selection)
''')


class LoadDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)
    path = StringProperty()
    filters = ListProperty()
    filesystem = ObjectProperty()
    show_dirs = BooleanProperty(True)

    def sort_folders_first(self, b, r, files, filesystem):
        if b:
            return (sorted(f for f in files if filesystem.is_dir(f)) +
                    sorted(f for f in files if not filesystem.is_dir(f)))
        else:
            # reverse sort by date
            return ([a[1] for a in sorted(((filesystem.getdate(f), f) for f in files), key=lambda x: x[0], reverse=r)])


class FileDialog(FloatLayout):
    """File Dialog"""
    def __init__(self):
        super(FileDialog, self).__init__()
        self.cb = None

    def dismiss_popup(self):
        self._popup.dismiss()

    def open(self, path=None, title="File to Run", filters=['*.g', '*.gcode', '*.nc', '*.gc', '*.ngc'], file_list=None, cb=None):

        self.cb = cb

        if file_list is not None:
            # print("{}: {}".format(title, file_list))
            fs = Factory.filesystemsd()
            fs.open(file_list)
            path = '/sd/'
            show_dirs = False
        else:
            fs = Factory.filesystem()
            show_dirs = True

        content = LoadDialog(load=self._load, cancel=self.dismiss_popup, path=path if path else os.path.expanduser("~"), filesystem=fs, show_dirs=show_dirs, filters=filters)

        self._popup = Popup(title=title, content=content, size_hint=(0.9, 0.9), auto_dismiss=False)
        self._popup.open()

    def _load(self, path, filename):
        self.dismiss_popup()
        if len(filename) > 0 and self.cb:
            self.cb(filename[0], path)
