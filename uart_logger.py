import serial
import threading

from kivy.logger import Logger


class UartLogger():
    def __init__(self, arg):
        super(UartLogger, self).__init__()
        self.port = arg
        self.cb = None

    def open(self, cb):
        try:
            self.ser = serial.Serial(self.port, baudrate=115200)
            self.ser.flushInput()
        except Exception as e:
            Logger.error("UartLogger: Failed to open uart: {}".format(e))
            return False

        self.cb = cb
        self.comms_thread = threading.Thread(target=self._async_read, daemon=True)
        self.comms_thread.start()

        return True

    def _async_read(self):
        while True:
            try:
                ser_bytes = self.ser.readline()
                decoded_bytes = ser_bytes.decode("utf-8")
                if self.cb is not None:
                    self.cb(decoded_bytes)

            except Exception:
                pass
