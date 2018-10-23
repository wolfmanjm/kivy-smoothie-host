try:
    import wx
    wx_available= True
except:
    wx_available= False
import threading
import os.path

from kivy.clock import mainthread

class NativeFileChooser():

    def is_available(self):
        return wx_available;

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
        path= self._wx_get_path()
        self._loaded(path)

    @mainthread
    def _loaded(self, path):
        if path:
            dr= os.path.dirname(path)
            if self.cb:
                self.cb(path, dr)
