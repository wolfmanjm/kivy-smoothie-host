try:
    import wx
    wx_available= True
except:
    wx_available= False
import threading
import os.path
import subprocess as sp
import time

from kivy.clock import mainthread
from message_box import MessageBox

class NativeFileChooser():
    type_name= 'wx'
    def __init__(self, **kwargs):
        super(NativeFileChooser, self).__init__(**kwargs)
        self.use_wx= False
        self.use_zenity= False
        self.use_kdialog= False
        self.failed= False

        if NativeFileChooser.type_name == 'wx' and wx_available:
            self.use_wx= True
        elif NativeFileChooser.type_name == 'zenity':
            self.use_zenity= True
        elif NativeFileChooser.type_name == 'kdialog':
            self.use_kdialog= True
        else:
            raise "Unknown chooser"

    def _run_command(self, cmd):
        self._process = sp.Popen(cmd, stdout=sp.PIPE)
        while True:
            ret = self._process.poll()
            if ret is not None:
                if ret == 0:
                    out = self._process.communicate()[0].strip().decode('utf8')
                    self.selection = out
                    return self.selection
                else:
                    return None
            time.sleep(0.1)

    def _wx_get_path(self):
        app = wx.App(None)
        style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        dialog = wx.FileDialog(None, self.title, defaultDir= self.start_dir, wildcard='GCode files|*.g;*.gcode;*.nc;*.gc|All Files|*', style=style)
        if dialog.ShowModal() == wx.ID_OK:
            path = dialog.GetPath()
        else:
            path = None
        dialog.Destroy()
        return path

    def open(self, start_dir= "", title= "", cb= None):
        self.cb= cb
        self.title= title
        self.start_dir= start_dir
        threading.Thread(target=self._open_dialog).start()

    def _open_dialog(self):
        path= None
        try:
            if self.use_wx:
                path= self._wx_get_path()

            elif self.use_zenity:
                path= self._run_command(['zenity', '--title', self.title, '--file-selection', '--filename', self.start_dir+'/', '--file-filter', 'GCode files | *.g *.gcode *.nc'])

            elif self.use_kdialog:
                path= self._run_command(['kdialog', '--title', self.title, '--getopenfilename', self.start_dir, '*.g *.gcode *.nc'])
            else:
                self.failed= True

        except:
            self.failed= True

        self._loaded(path)

    @mainthread
    def _loaded(self, path):
        if self.failed:
            mb = MessageBox(text='File Chooser {} failed - try a different one'.format(NativeFileChooser.type_name))
            mb.open()
            return

        if path:
            dr= os.path.dirname(path)
            if self.cb:
                self.cb(path, dr)
