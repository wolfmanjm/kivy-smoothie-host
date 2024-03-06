import kivy

from kivy.app import App
from kivy.logger import Logger
from kivy.uix.stacklayout import StackLayout
from kivy.config import ConfigParser
from kivy.clock import Clock, mainthread
from kivy.factory import Factory
from multi_input_box import MultiInputBox
from confirm_box import ConfirmBox

import configparser
from functools import partial
import subprocess
import threading
#import select
import selectors
import re
import os

'''
user defined macros are configurable and stored in a configuration file called macros.ini or
macros-cnc.ini if in cnc mode
format is:-
button name = command to send
'''


class MacrosWidget(StackLayout):
    """adds macro buttons"""
    def __init__(self, **kwargs):
        super(MacrosWidget, self).__init__(**kwargs)
        self.app = App.get_running_app()
        # we do this so the kv defined buttons are loaded first
        Clock.schedule_once(self._load_user_buttons)
        self.toggle_buttons = {}
        self.debug = False

    def _handle_toggle(self, name, v):
        t = self.toggle_buttons.get(name, None)
        if t is None:
            Logger.error("MacrosWidget: no toggle button named: {}".format(name))
            return

        if t[4].state == 'normal':
            t[4].text = t[0]
            self.send(t[3])  # NOTE the button already toggled so the states are reversed
        else:
            t[4].text = t[1]
            self.send(t[2])

    def reload(self):
        self.toggle_buttons = {}
        for mb in self.walk(restrict=True):
            if hasattr(mb, 'ud') and mb.ud:
                self.remove_widget(mb)

        self._load_user_buttons()

    def _load_user_buttons(self, *args):
        # load user defined macros
        if self.app.is_cnc:
            self.macro_file = '{}/macros-cnc.ini'.format(self.app.running_directory)
            if not (os.path.isfile(self.macro_file) and os.access(self.macro_file, os.R_OK)):
                self.macro_file = '{}/macros.ini'.format(self.app.running_directory)

        else:
            self.macro_file = '{}/macros.ini'.format(self.app.running_directory)

        if not (os.path.isfile(self.macro_file) and os.access(self.macro_file, os.R_OK)):
            Logger.info("MacrosWidget: no user defined macros file to load")
            return

        try:
            config = configparser.ConfigParser()
            config.read(self.macro_file)

            # add toggle button handling switch states
            for section in config.sections():
                if section.startswith('toggle button '):
                    name = config.get(section, 'name', fallback=None)
                    poll = config.getboolean(section, 'poll', fallback=False)
                    lon = config.get(section, 'label on', fallback=None)
                    loff = config.get(section, 'label off', fallback=None)
                    cmd_on = config.get(section, 'command on', fallback=None)
                    cmd_off = config.get(section, 'command off', fallback=None)
                    default = config.get(section, 'default', fallback="off")
                    if name is None or lon is None or loff is None or cmd_on is None or cmd_off is None:
                        Logger.error("MacrosWidget: config error - {} is invalid".format(section))
                        continue

                    tbtn = Factory.MacroToggleButton()
                    if default == "on":
                        tbtn.state = "down"
                        tbtn.text = loff
                    else:
                        tbtn.text = lon

                    self.toggle_buttons[name] = (lon, loff, cmd_on, cmd_off, tbtn, poll)
                    tbtn.bind(on_press=partial(self._handle_toggle, name))
                    tbtn.ud = True
                    self.add_widget(tbtn)

                elif section.startswith('script '):
                    name = config.get(section, 'name', fallback=None)
                    script = config.get(section, 'exec', fallback=None)
                    args = config.get(section, 'args', fallback=None)
                    io = config.getboolean(section, 'io', fallback=False)
                    self.debug = config.getboolean(section, 'debug', fallback=False)
                    btn = Factory.MacroButton()
                    btn.text = name
                    btn.background_color = (1, 1, 0, 1)
                    btn.bind(on_press=partial(self.exec_script, script, io, args))
                    btn.ud = True
                    self.add_widget(btn)

                elif section.startswith('toolscript '):
                    name = config.get(section, 'name', fallback=None)
                    script = config.get(section, 'exec', fallback=None)
                    args = config.get(section, 'args', fallback=None)
                    btn = Factory.MacroButton()
                    btn.text = name
                    btn.background_color = (1, 0, 1, 1)
                    btn.bind(on_press=partial(self.exec_toolscript, script, args))
                    btn.ud = True
                    self.add_widget(btn)

            # add simple macro buttons (with optional prompts)
            for (key, v) in config.items('macro buttons'):
                btn = Factory.MacroButton()
                btn.text = key
                btn.bind(on_press=partial(self.send, v))
                btn.ud = True
                self.add_widget(btn)

        except Exception as err:
            Logger.warning('MacrosWidget: WARNING - exception parsing config file: {}'.format(err))

    def new_macro(self):
        o = MultiInputBox(title='Add Macro')
        o.setOptions(['Name', 'Command'], self._new_macro)
        o.open()

    def _new_macro(self, opts):
        if opts and opts['Name'] and opts['Command']:
            btn = Factory.MacroButton()
            btn.text = opts['Name']
            btn.bind(on_press=partial(self.send, opts['Command']))
            btn.ud = True
            self.add_widget(btn)
            # write it to macros.ini
            try:
                config = configparser.ConfigParser()
                config.read(self.macro_file)
                if not config.has_section("macro buttons"):
                    config.add_section("macro buttons")
                config.set("macro buttons", opts['Name'], opts['Command'])
                with open(self.macro_file, 'w') as configfile:
                    config.write(configfile)

                Logger.info('MacrosWidget: added macro button {}'.format(opts['Name']))

            except Exception as err:
                Logger.error('MacrosWidget: ERROR - exception writing config file: {}'.format(err))

    def update_buttons(self):
        # check the state of the toggle macro buttons that have poll set, called when we switch to the macro window
        # we send the new $S command so it gets processed immediately despite being busy
        cmd = "$S"
        for name in self.toggle_buttons:
            if self.toggle_buttons[name][5]:  # if poll is set
                cmd += " "
                cmd += name

        if len(cmd) <= 3:
            cmd = ""
        else:
            cmd += "\n"

        return cmd

    @mainthread
    def switch_response(self, name, value):
        # check response and compare state with current state and toggle to match state if necessary
        t = self.toggle_buttons.get(name, None)
        if t is None:
            Logger.error("MacrosWidget: switch_response no toggle button named: {}".format(name))
            return

        if value == '0' and t[4].state != 'normal':
            t[4].state = 'normal'
            t[4].text = t[0]
        elif value == '1' and t[4].state == 'normal':
            t[4].state = 'down'
            t[4].text = t[1]

    def _substitute_args(self, m, arg):
        """ substitute {?prompt}) with prompted value """

        # get arguments to prompt for
        v = [x[2:-1] for x in m]

        mb = MultiInputBox(title="Arguments for {}".format(arg))
        mb.setOptions(v, partial(self._do_substitute_exec, m, arg))
        mb.open()

    def _do_substitute_exec(self, m, arg, opts):
        for i in m:
            v = opts[i[2:-1]]
            if v:
                arg = arg.replace(i, v)
            else:
                self.app.main_window.async_display("ERROR: argument missing for {}".format(i))
                return

        self.app.comms.write('{}\n'.format(arg))

    def _send_file(self, fn):
        try:
            with open(fn) as f:
                for line in f:
                    # FIXME maybe need to do ping pong?
                    self.app.comms.write('{}'.format(line))

        except Exception:
            self.app.main_window.async_display("ERROR: File not found: {}".format(fn))

    def send(self, cmd, *args):
        # if first character is ? then make sure it is ok to continue
        if cmd.startswith('?'):
            cb = ConfirmBox(text=cmd[1:], cb=partial(self.send, cmd[1:]))
            cb.open()
            return

        # if first character is @ then execute contents of the following file name
        if cmd.startswith('@'):
            self._send_file(cmd[1:])
            return

        # look for {?prompt}) and substitute entered value if found
        m = re.findall(r'\{\?[^}]+\}', cmd)
        if m:
            self._substitute_args(m, cmd)
        else:
            # plain command just send it
            self.app.comms.write('{}\n'.format(cmd))

    def exec_toolscript(self, cmd, params, *args):
        if params is not None:
            ll = params.split(',')
            mb = MultiInputBox(title='Arguments')
            mb.setOptions(ll, partial(self._exec_toolscript_params, cmd))
            mb.open()

        else:
            self._exec_toolscript(cmd)

    def _exec_toolscript_params(self, cmd, opts):
        for x in opts:
            cmd += " " + x + " " + opts[x]

        self._exec_toolscript(cmd)

    def _exec_toolscript(self, cmd):
        # add any tool scripts here
        if cmd.startswith("find_center"):
            self.app.tool_scripts.find_center()

        elif cmd.startswith("set_rpm"):
            if "RPM " in cmd:
                try:
                    p = cmd.find('RPM')
                    p += 4
                    r = cmd[p:]
                    self.app.tool_scripts.set_rpm(float(r))
                except Exception as e:
                    Logger.error(f"MacrosWidget: set_rpm exception {e}")
            else:
                self.app.main_window.async_display('RPM argument is required')

        else:
            Logger.error(f"MacrosWidget: {cmd} is not a tool script")

    def exec_script(self, cmd, io, params, *args):
        if params is not None:
            ll = params.split(',')
            mb = MultiInputBox(title='Arguments')
            mb.setOptions(ll, partial(self._exec_script_params, cmd, io))
            mb.open()

        else:
            self._exec_script(cmd, io)

    def _exec_script_params(self, cmd, io, opts):
        for x in opts:
            cmd += " " + x + " " + opts[x]

        self._exec_script(cmd, io)

    def _exec_script(self, cmd, io):
        # TODO should add substituted args as in macro buttons

        if '{file}' in cmd:
            # replace {file} with a selected file name
            f = Factory.filechooser()
            f.open(self.app.main_window.last_path, cb=partial(self._exec_script_substitute_file_name, cmd, io))

        else:
            # needs to be run in a thread
            t = threading.Thread(target=self._script_thread, daemon=True, args=(cmd, io,))
            t.start()

    def _exec_script_substitute_file_name(self, cmd, io, file_path, dir_path):
        if file_path and cmd:
            cmd = cmd.replace("{file}", file_path)
            # needs to be run in a thread
            t = threading.Thread(target=self._script_thread, daemon=True, args=(cmd, io,))
            t.start()

    def _send_it(self, p, x):
        p.stdin.write(f"{x}\n")

    def _script_thread(self, cmd, io):
        try:
            if io:
                if not self.app.is_connected:
                    Logger.error('MacrosWidget:  Not connected')
                    self.app.main_window.async_display('> not connected')
                    io = False
                    return

                repeating = False
                if cmd.startswith('-'):
                    # repeating output on same line
                    repeating = True
                    cmd = cmd[1:]

                # I/O is piped to/from smoothie
                self.app.main_window.async_display(f"> running script: {cmd}")
                Logger.info(f"running script: {cmd}")
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True, bufsize=1)
                self.app.comms.redirect_incoming(lambda x: self._send_it(p, x))

                sel = selectors.DefaultSelector()
                sel.register(p.stdout, selectors.EVENT_READ)
                sel.register(p.stderr, selectors.EVENT_READ)

                ok = True
                while ok:
                    for key, _ in sel.select(0):
                        data = key.fileobj.readline()
                        if not data:
                            ok = False
                            break
                        if key.fileobj is p.stdout:
                            if not repeating and self.debug:
                                self.app.main_window.async_display("<<< script: {}".format(data.rstrip()))
                            self.app.comms.write(f'{data}')

                        else:  # stderr
                            if repeating:
                                self.app.main_window.async_display('{}\r'.format(data.rstrip()))
                            else:
                                self.app.main_window.async_display('>>> script: {}'.format(data.rstrip()))
                                Logger.info(f'script: {data.rstrip()}')

                sel.close()
                self.app.main_window.async_display('> script complete')

            else:
                # just display results
                self.app.main_window.async_display("> {}".format(cmd))
                p = subprocess.Popen(cmd, shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # , encoding='latin1'
                result, err = p.communicate()
                for ll in result.splitlines():
                    self.app.main_window.async_display(ll)
                for ll in err.splitlines():
                    self.app.main_window.async_display(ll)
                if p.returncode != 0:
                    self.app.main_window.async_display("return code: {}".format(p.returncode))

        except Exception as err:
            Logger.error('MacrosWidget: script exception: {}'.format(err))
            self.app.main_window.async_display('>>> script exception, see log')

        finally:
            if io and self.app.is_connected:
                self.app.comms.redirect_incoming(None)
