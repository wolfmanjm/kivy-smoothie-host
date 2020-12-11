from kivy.uix.scatter import Scatter
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.logger import Logger, LOG_LEVELS
from kivy.graphics import Color, Line, Scale, Translate, PopMatrix, PushMatrix, Rectangle
from kivy.graphics import InstructionGroup
from kivy.properties import NumericProperty, BooleanProperty, ListProperty
from kivy.graphics.transformation import Matrix
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.clock import Clock, mainthread
from kivy.core.text import Label as CoreLabel
from message_box import MessageBox

import logging
import sys
import re
import math
import time
import threading
import traceback

Builder.load_string('''
<GcodeViewerScreen>:
    on_enter: self.loading()
    on_leave: self.clear()
    BoxLayout:
        orientation: 'vertical'
        Label:
            text: "{} size: {}x{}".format(app.gcode_file, root.bounds[0], root.bounds[1])
            size_hint_y: None
            height: self.texture_size[1]

        BoxLayout:
            canvas.before:
                Color:
                    rgb: 0.5, 0.5, 0.5, 0.5
                Rectangle:
                    size: self.size
            id: view_window
            pos_hint: {'top': 1}
            Scatter:
                id: surface
                on_transform_with_touch: root.moved(*args)
                do_collide_after_children: True
                do_rotation: False
                canvas.before:
                    ScissorPush:
                        # without this we can see the scatter underneath the buttons in the rest of the window
                        x: self.parent.pos[0]
                        y: self.parent.pos[1]
                        width: self.parent.width
                        height: self.parent.height

                    Color:
                        rgb: (1, 1, 1, 1) if root.valid else (0,0,0,1)
                    Rectangle:
                        size: self.size

                canvas.after:
                    ScissorPop:

        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: 40
            Label:
                canvas.before:
                    Color:
                        rgb: 0, 1, 0, 1
                    Rectangle:
                        size: self.size
                id: z_value
                text: 'Z{}'.format(round(root.current_z, 1))
                size_hint_x: None
                width: self.texture_size[0]
            Button:
                text: 'First Layer'
                disabled: root.twod_mode
                on_press: root.clear(); root.loading()
            Button:
                text: 'Prev Layer'
                disabled: root.twod_mode or len(root.layers) <= 2
                on_press: root.prev_layer()
            Button:
                text: 'Next Layer'
                disabled: root.twod_mode
                on_press: root.next_layer()
            Spinner:
                text_autoupdate: True
                values: ('3D', '2D', 'Laser') if not app.is_cnc else ('2D', 'Laser', '3D')
                on_text: root.set_type(self.text)

            ToggleButton:
                id: select_mode_but
                text: 'Select'
                on_press: root.select(self.state == 'down')

            Button:
                text: 'Set WPOS'
                disabled: not root.select_mode
                on_press: root.set_wcs()
            Button:
                text: 'Move to'
                disabled: not root.select_mode
                on_press: root.move_gantry()
            Button:
                text: 'Run'
                disabled: not app.is_connected
                on_press: root.do_print()
            Button:
                text: 'Back'
                on_press: root.manager.current = 'main'
''')

XY = 0
XZ = 1
CNC_accuracy = 0.001


class GcodeViewerScreen(Screen):
    current_z = NumericProperty(0)
    select_mode = BooleanProperty(False)
    twod_mode = BooleanProperty(False)
    laser_mode = BooleanProperty(False)
    valid = BooleanProperty(False)
    bounds = ListProperty([0, 0])
    layers = ListProperty([0])

    def __init__(self, comms=None, **kwargs):
        super(GcodeViewerScreen, self).__init__(**kwargs)
        self.app = App.get_running_app()
        self.last_file_pos = None
        self.canv = InstructionGroup()
        self.bind(pos=self._redraw, size=self._redraw)
        self.tx = 0
        self.ty = 0
        self.scale = 1.0
        self.comms = comms
        self.twod_mode = self.app.is_cnc
        self.rval = 0.0

    def loading(self):
        self.valid = False
        self.li = Image(source='img/image-loading.gif')
        self.add_widget(self.li)
        self.ids.surface.canvas.remove(self.canv)
        threading.Thread(target=self._load_file).start()

    @mainthread
    def _loaded(self, ok):
        if not ok:
            # print(traceback.format_exc())
            mb = MessageBox(text='File not found: {}'.format(self.app.gcode_file))
            mb.open()
            self.manager.current = 'main'

        Logger.debug("GcodeViewerScreen: in _loaded. ok: {}".format(self._loaded_ok))
        self.remove_widget(self.li)
        self.li = None
        self.ids.surface.canvas.add(self.canv)
        self.valid = self._loaded_ok
        if self._loaded_ok:
            # not sure why we need to do this
            self.ids.surface.top = Window.height
            if self.app.is_connected:
                self.app.bind(wpos=self.update_tool)

    def _load_file(self):
        self._loaded_ok = False
        try:
            self.parse_gcode_file(self.app.gcode_file, True)
        except Exception:
            self._loaded(False)
        else:
            self._loaded(True)

    def _redraw(self, instance, value):
        self.ids.surface.canvas.remove(self.canv)
        self.ids.surface.canvas.add(self.canv)

    def clear(self):
        self.app.unbind(wpos=self.update_tool)

        if self.li:
            self.remove_widget(self.li)
            self.li = None

        if self.select_mode:
            self.stop_cursor(0, 0)
            self.select_mode = False
            self.ids.select_mode_but.state = 'normal'

        self.valid = False
        self.is_visible = False
        self.canv.clear()
        self.ids.surface.canvas.remove(self.canv)
        self.layers = [0]

        # reset scale and translation
        m = Matrix()
        m.identity()
        self.ids.surface.transform = m
        # not sure why we need to do this
        self.ids.surface.top = Window.height

    def next_layer(self):
        self.loading()

    def prev_layer(self):
        if len(self.layers) > 2:
            self.layers.pop()
            self.layers.pop()
            self.loading()

    def do_print(self):
        self.app.main_window._start_print()

    # ----------------------------------------------------------------------
    # Return center x,y,z,r for arc motions 2,3 and set self.rval
    # Cribbed from bCNC
    # ----------------------------------------------------------------------

    def motionCenter(self, gcode, plane, xyz_cur, xyz_val, ival, jval, kval=0.0):
        if self.rval > 0.0:
            if plane == XY:
                x = xyz_cur[0]
                y = xyz_cur[1]
                xv = xyz_val[0]
                yv = xyz_val[1]
            elif plane == XZ:
                x = xyz_cur[0]
                y = xyz_cur[2]
                xv = xyz_val[0]
                yv = xyz_val[2]
            else:
                x = xyz_cur[1]
                y = xyz_cur[2]
                xv = xyz_val[1]
                yv = xyz_val[2]

            ABx = xv - x
            ABy = yv - y
            Cx = 0.5 * (x + xv)
            Cy = 0.5 * (y + yv)
            AB = math.sqrt(ABx**2 + ABy**2)
            try:
                OC = math.sqrt(self.rval**2 - AB**2 / 4.0)
            except Exception:
                OC = 0.0

            if gcode == 2:
                OC = -OC  # CW
            if AB != 0.0:
                return Cx - OC * ABy / AB, Cy + OC * ABx / AB
            else:
                # Error!!!
                return x, y
        else:
            # Center
            xc = xyz_cur[0] + ival
            yc = xyz_cur[1] + jval
            zc = xyz_cur[2] + kval
            self.rval = math.sqrt(ival**2 + jval**2 + kval**2)

            if plane == XY:
                return xc, yc
            elif plane == XZ:
                return xc, zc
            else:
                return yc, zc

    extract_gcode = re.compile(r"(G|X|Y|Z|I|J|K|E|S)(-?\d*\.?\d*\.?)")

    def parse_gcode_file(self, fn, one_layer=False):
        # open file parse gcode and draw
        Logger.debug("GcodeViewerScreen: parsing file {}". format(fn))
        lastpos = [self.app.wpos[0], self.app.wpos[1], None]  # XYZ, set to initial tool position
        last_layer_z = None
        lastdeltaz = None
        laste = 0
        lasts = 1
        last_gcode = -1
        points = []
        max_x = float('nan')
        max_y = float('nan')
        min_x = float('nan')
        min_y = float('nan')
        has_e = False
        plane = XY
        rel_move = False
        self.is_visible = True
        if self.laser_mode:
            self.twod_mode = True  # laser mode implies 2D mode

        # reset scale and translation
        m = Matrix()
        m.identity()
        self.ids.surface.transform = m

        # remove all instructions from canvas
        self.canv.clear()

        self.canv.add(PushMatrix())
        modal_g = 0
        cnt = 0

        x = lastpos[0]
        y = lastpos[1]
        z = lastpos[2]

        with open(fn) as f:
            # jump to last read position
            f.seek(self.layers[-1])
            # print('Jumped to layer position: {}'.format(f.tell()))

            got_layer = False
            while not got_layer:
                last_file_pos = f.tell()  # save the start of this line

                ln = f.readline()
                if not ln:
                    break
                Logger.debug("GcodeViewerScreen: {}".format(ln))

                cnt += 1
                ln = ln.strip()
                if not ln:
                    continue
                if ln.startswith(';') or ln.startswith('#'):
                    continue
                if ln.startswith('('):
                    continue
                p = ln.find(';')
                if p >= 0:
                    ln = ln[:p]
                matches = self.extract_gcode.findall(ln)

                # this handles multiple G codes on one line
                gcodes = []
                d = {}
                for m in matches:
                    # print(m)
                    if m[0] == 'G' and 'G' in d:
                        # we have another G code on the same line
                        gcodes.append(d)
                        d = {}
                    d[m[0]] = float(m[1])

                gcodes.append(d)

                for d in gcodes:
                    if not d:
                        continue

                    Logger.debug("GcodeViewerScreen: d={}".format(d))

                    # handle modal commands
                    if 'G' not in d and ('X' in d or 'Y' in d or 'Z' in d or 'S' in d):
                        d['G'] = modal_g

                    gcode = int(d['G'])

                    # G92 E0 resets E
                    if 'G' in d and gcode == 92 and 'E' in d:
                        laste = float(d['E'])
                        has_e = True

                    if 'G' in d and (gcode == 91 or gcode == 90):
                        rel_move = gcode == 91

                    # only deal with G0/1/2/3
                    if gcode > 3:
                        continue

                    modal_g = gcode

                    # see if it is 3d printing (ie has an E axis on a G1)
                    if not has_e and ('E' in d and 'G' in d and gcode == 1):
                        has_e = True

                    if rel_move:
                        x += 0 if 'X' not in d else float(d['X'])
                        y += 0 if 'Y' not in d else float(d['Y'])
                        if z is not None:
                            z += 0 if 'Z' not in d else float(d['Z'])

                    else:
                        x = lastpos[0] if 'X' not in d else float(d['X'])
                        y = lastpos[1] if 'Y' not in d else float(d['Y'])
                        z = lastpos[2] if 'Z' not in d else float(d['Z'])

                    i = 0.0 if 'I' not in d else float(d['I'])
                    j = 0.0 if 'J' not in d else float(d['J'])
                    self.rval = 0.0 if 'R' not in d else float(d['R'])

                    e = laste if 'E' not in d else float(d['E'])
                    s = lasts if 'S' not in d else float(d['S'])

                    if not self.twod_mode:
                        # handle layers (when Z changes)
                        if last_layer_z is None:
                            # start of first layer
                            last_layer_z = z

                        elif z != last_layer_z:
                            # possible new layer
                            if z < last_layer_z:
                                # this may have been preceded by a z lift or an initial setting of Z
                                # replace last one with this one as it is probably the start of the layer
                                self.layers[-1] = last_file_pos
                                Logger.debug('Replaced position: {} for layer: {}'.format(self.layers[-1], len(self.layers)))
                                last_layer_z = z

                            else:
                                last_layer_z = z
                                # remember the start of this line
                                self.layers.append(last_file_pos)
                                Logger.debug('Saved position: {} for layer: {}'.format(self.layers[-1], len(self.layers)))
                                # we are done with the layer, process it
                                got_layer = True
                                break

                        if z is not None:
                            self.current_z = z

                    Logger.debug("GcodeViewerScreen: x= {}, y= {}, z= {}, s= {}".format(x, y, z, s))

                    # find bounding box
                    if math.isnan(min_x) or x < min_x:
                        min_x = x
                    if math.isnan(min_y) or y < min_y:
                        min_y = y
                    if math.isnan(max_x) or x > max_x:
                        max_x = x
                    if math.isnan(max_y) or y > max_y:
                        max_y = y

                    # accumulating vertices is more efficient but we need to flush them at some point
                    # Here we flush them if we encounter a new G code like G3 following G1
                    if last_gcode != gcode:
                        # flush vertices
                        if points:
                            self.canv.add(Color(0, 0, 0))
                            self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                            points = []

                    last_gcode = gcode

                    # in slicer generated files there is no G0 so we need a way to know when to draw, so if there is an E then draw else don't
                    if gcode == 0:
                        # print("move to: {}, {}, {}".format(x, y, z))
                        # draw moves in dashed red
                        self.canv.add(Color(1, 0, 0))
                        self.canv.add(Line(points=[lastpos[0], lastpos[1], x, y], width=1, dash_offset=1, cap='none', joint='none'))

                    elif gcode == 1:
                        if ('X' in d or 'Y' in d):
                            if self.laser_mode and s <= 0.01:
                                # do not draw non cutting lines
                                if points:
                                    # draw accumulated points upto this point
                                    self.canv.add(Color(0, 0, 0))
                                    self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                                    points = []

                            # for 3d printers (has_e) only draw if there is an E
                            elif not has_e or 'E' in d:
                                # if a CNC gcode file or there is an E in the G1 (3d printing)
                                # print("draw to: {}, {}, {}".format(x, y, z))
                                # collect points but don't draw them yet
                                if len(points) < 2:
                                    points.append(lastpos[0])
                                    points.append(lastpos[1])

                                points.append(x)
                                points.append(y)

                            else:
                                # a G1 with no E, treat as G0 and draw moves in red
                                # print("move to: {}, {}, {}".format(x, y, z))
                                if points:
                                    # draw accumulated points upto this point
                                    self.canv.add(Color(0, 0, 0))
                                    self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                                    points = []
                                # now draw the move in red
                                self.canv.add(Color(1, 0, 0))
                                self.canv.add(Line(points=[lastpos[0], lastpos[1], x, y], width=1, cap='none', joint='none'))

                        else:
                            # A G1 with no X or Y, maybe E only move (retract) or Z move (layer change)
                            if points:
                                # draw accumulated points upto this point
                                self.canv.add(Color(0, 0, 0))
                                self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                                points = []

                    elif gcode in [2, 3]:  # CW=2,CCW=3 circle
                        # code cribbed from bCNC
                        xyz = []
                        xyz.append((lastpos[0], lastpos[1], lastpos[2]))
                        uc, vc = self.motionCenter(gcode, plane, lastpos, [x, y, z], i, j)

                        if plane == XY:
                            u0 = lastpos[0]
                            v0 = lastpos[1]
                            w0 = lastpos[2]
                            u1 = x
                            v1 = y
                            w1 = z
                        elif plane == XZ:
                            u0 = lastpos[0]
                            v0 = lastpos[2]
                            w0 = lastpos[1]
                            u1 = x
                            v1 = z
                            w1 = y
                            gcode = 5 - gcode  # flip 2-3 when XZ plane is used
                        else:
                            u0 = lastpos[1]
                            v0 = lastpos[2]
                            w0 = lastpos[0]
                            u1 = y
                            v1 = z
                            w1 = x
                        phi0 = math.atan2(v0 - vc, u0 - uc)
                        phi1 = math.atan2(v1 - vc, u1 - uc)
                        try:
                            sagitta = 1.0 - CNC_accuracy / self.rval
                        except ZeroDivisionError:
                            sagitta = 0.0
                        if sagitta > 0.0:
                            df = 2.0 * math.acos(sagitta)
                            df = min(df, math.pi / 4.0)
                        else:
                            df = math.pi / 4.0

                        if gcode == 2:
                            if phi1 >= phi0 - 1e-10:
                                phi1 -= 2.0 * math.pi
                            ws = (w1 - w0) / (phi1 - phi0)
                            phi = phi0 - df
                            while phi > phi1:
                                u = uc + self.rval * math.cos(phi)
                                v = vc + self.rval * math.sin(phi)
                                w = w0 + (phi - phi0) * ws
                                phi -= df
                                if plane == XY:
                                    xyz.append((u, v, w))
                                elif plane == XZ:
                                    xyz.append((u, w, v))
                                else:
                                    xyz.append((w, u, v))
                        else:
                            if phi1 <= phi0 + 1e-10:
                                phi1 += 2.0 * math.pi
                            ws = (w1 - w0) / (phi1 - phi0)
                            phi = phi0 + df
                            while phi < phi1:
                                u = uc + self.rval * math.cos(phi)
                                v = vc + self.rval * math.sin(phi)
                                w = w0 + (phi - phi0) * ws
                                phi += df
                                if plane == XY:
                                    xyz.append((u, v, w))
                                elif plane == XZ:
                                    xyz.append((u, w, v))
                                else:
                                    xyz.append((w, u, v))

                        xyz.append((x, y, z))
                        # plot the points
                        points = []
                        for t in xyz:
                            x1, y1, z1 = t
                            points.append(x1)
                            points.append(y1)
                            max_x = max(x1, max_x)
                            min_x = min(x1, min_x)
                            max_y = max(y1, max_y)
                            min_y = min(y1, min_y)

                        self.canv.add(Color(0, 0, 0))
                        self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
                        points = []

                    # always remember last position
                    lastpos = [x, y, z]
                    laste = e
                    lasts = s

                if max_x == min_x and max_y == min_y:
                    got_layer = False
                    Logger.debug("GcodeViewerScreen: no geometry found try next line")

        if not self.twod_mode and last_layer_z is None:
            # we hit the end of file before finding the layer we want
            Logger.info("GcodeViewerScreen: no layer found - last layer was at {}".format(lastpos[2]))
            return

        # flush any points not yet drawn
        if points:
            # draw accumulated points upto this point
            self.canv.add(Color(0, 0, 0))
            self.canv.add(Line(points=points, width=1, cap='none', joint='none'))
            points = []

        # center the drawing and scale it
        dx = max_x - min_x
        dy = max_y - min_y
        if dx == 0 or dy == 0:
            Logger.warning("GcodeViewerScreen: size is bad, maybe need 2D mode")
            return

        self.bounds = [dx, dy]

        dx += 4
        dy += 4
        Logger.debug("GcodeViewerScreen: dx= {}, dy= {}".format(dx, dy))

        # add in the translation to center object
        self.tx = -min_x - dx / 2
        self.ty = -min_y - dy / 2
        self.canv.insert(1, Translate(self.tx, self.ty))
        Logger.debug("GcodeViewerScreen: tx= {}, ty= {}".format(self.tx, self.ty))

        # scale the drawing to fit the screen
        if abs(dx) > abs(dy):
            scale = self.ids.surface.width / abs(dx)
            if abs(dy) * scale > self.ids.surface.height:
                scale *= self.ids.surface.height / (abs(dy) * scale)
        else:
            scale = self.ids.surface.height / abs(dy)
            if abs(dx) * scale > self.ids.surface.width:
                scale *= self.ids.surface.width / (abs(dx) * scale)

        Logger.debug("GcodeViewerScreen: scale= {}".format(scale))
        self.scale = scale
        self.canv.insert(1, Scale(scale))
        # translate to center of canvas
        self.offs = self.ids.surface.center
        self.canv.insert(1, Translate(self.ids.surface.center[0], self.ids.surface.center[1]))
        Logger.debug("GcodeViewerScreen: cx= {}, cy= {}".format(self.ids.surface.center[0], self.ids.surface.center[1]))
        Logger.debug("GcodeViewerScreen: sx= {}, sy= {}".format(self.ids.surface.size[0], self.ids.surface.size[1]))

        # axis Markers
        self.canv.add(Color(0, 1, 0, mode='rgb'))
        self.canv.add(Line(points=[0, -10, 0, self.ids.surface.height / scale], width=1, cap='none', joint='none'))
        self.canv.add(Line(points=[-10, 0, self.ids.surface.width / scale, 0], width=1, cap='none', joint='none'))

        # center of extents marker
        cex = (max_x + min_x) / 2
        cey = (max_y + min_y) / 2
        cer = (5.0 / self.ids.surface.scale) / scale
        self.canv.add(Color(1, 0, 0, mode='rgb'))
        self.canv.add(Line(circle=(cex, cey, cer)))
        self.canv.add(Line(points=[cex - cer, cey, cex + cer, cey], width=1, cap='none', joint='none'))
        self.canv.add(Line(points=[cex, cey - cer, cex, cey + cer], width=1, cap='none', joint='none'))

        # tool position marker
        if self.app.is_connected:
            x = self.app.wpos[0]
            y = self.app.wpos[1]
            r = (10.0 / self.ids.surface.scale) / scale
            self.canv.add(Color(1, 0, 0, mode='rgb', group="tool"))
            self.canv.add(Line(circle=(x, y, r), group="tool"))

        # self.canv.add(Rectangle(pos=(x, y-r/2), size=(1/scale, r), group="tool"))
        # self.canv.add(Rectangle(pos=(x-r/2, y), size=(r, 1/scale), group="tool"))

        self.canv.add(PopMatrix())
        self._loaded_ok = True
        Logger.debug("GcodeViewerScreen: done loading")
        Logger.debug("GcodeViewerScreen: bounds {}x{}".format(self.bounds[0], self.bounds[1]))

    def update_tool(self, i, v):
        if not self.is_visible or not self.app.is_connected:
            return

        # follow the tool path
        # self.canv.remove_group("tool")
        x = v[0]
        y = v[1]
        r = (10.0 / self.ids.surface.scale) / self.scale
        g = self.canv.get_group("tool")
        if g:
            g[2].circle = (x, y, r)
            # g[4].pos= x, y-r/2
            # g[6].pos= x-r/2, y

    def transform_to_wpos(self, posx, posy):
        ''' convert touch coords to local scatter widget coords, relative to lower bottom corner '''
        pos = self.ids.surface.to_widget(posx, posy)
        # convert to original model coordinates (mm), need to take into account scale and translate
        wpos = ((pos[0] - self.offs[0]) / self.scale - self.tx, (pos[1] - self.offs[1]) / self.scale - self.ty)
        return wpos

    def transform_to_spos(self, posx, posy):
        ''' inverse transform of model coordinates to scatter coordinates '''
        pos = ((((posx + self.tx) * self.scale) + self.offs[0]), (((posy + self.ty) * self.scale) + self.offs[1]))
        spos = self.ids.surface.to_window(*pos)
        # print("pos= {}, spos= {}".format(pos, spos))
        return spos

    def moved(self, w, touch):
        # we scaled or moved the scatter so need to reposition cursor
        # TODO it would be nice if the cursor stayed where it was relative to the model during a move or scale
        # NOTE right now we can't move or scale while cursor is on
        # if self.select_mode:
        #     x, y= (self.crossx[0].pos[0], self.crossx[1].pos[1])
        #     self.stop_cursor(x, y)
        #     self.start_cursor(x, y)

        # hide tool marker
        self.canv.remove_group('tool')

    def start_cursor(self, x, y):
        tx, ty = self.transform_to_wpos(x, y)
        label = CoreLabel(text="{:1.2f},{:1.2f}".format(tx, ty))
        label.refresh()
        texture = label.texture
        px, py = (x, y)
        with self.ids.surface.canvas.after:
            Color(0, 0, 1, mode='rgb', group='cursor_group')
            self.crossx = [
                Rectangle(pos=(px, 0), size=(1, self.height), group='cursor_group'),
                Rectangle(pos=(0, py), size=(self.width, 1), group='cursor_group'),
                Line(circle=(px, py, 20), group='cursor_group'),
                Rectangle(texture=texture, pos=(px - texture.size[0] / 2, py - 40), size=texture.size, group='cursor_group')
            ]

    def move_cursor_by(self, dx, dy):
        x, y = (self.crossx[0].pos[0] + dx, self.crossx[1].pos[1] + dy)

        self.crossx[0].pos = x, 0
        self.crossx[1].pos = 0, y
        self.crossx[2].circle = (x, y, 20)
        tx, ty = self.transform_to_wpos(x, y)
        label = CoreLabel(text="{:1.2f},{:1.2f}".format(tx, ty))
        label.refresh()
        texture = label.texture
        self.crossx[3].texture = texture
        self.crossx[3].pos = x - texture.size[0] / 2, y - 40

    def stop_cursor(self, x=0, y=0):
        self.ids.surface.canvas.after.remove_group('cursor_group')
        self.crossx = None

    def on_touch_down(self, touch):
        # print(self.ids.surface.bbox)
        if self.ids.view_window.collide_point(touch.x, touch.y):
            # if within the scatter window
            if self.select_mode:
                touch.grab(self)
                return True

            elif touch.is_mouse_scrolling:
                # Allow mouse scroll wheel to zoom in/out
                if touch.button == 'scrolldown':
                    # zoom in
                    if self.ids.surface.scale < 100:
                        rescale = 1.1
                        self.ids.surface.apply_transform(Matrix().scale(rescale, rescale, rescale), post_multiply=True, anchor=self.ids.surface.to_widget(*touch.pos))

                elif touch.button == 'scrollup':
                    # zoom out
                    if self.ids.surface.scale > 0.01:
                        rescale = 0.8
                        self.ids.surface.apply_transform(Matrix().scale(rescale, rescale, rescale), post_multiply=True, anchor=self.ids.surface.to_widget(*touch.pos))

                self.moved(None, touch)
                return True

        return super(GcodeViewerScreen, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.select_mode:
            if touch.grab_current is not self:
                return False

            dx = touch.dpos[0]
            dy = touch.dpos[1]
            self.move_cursor_by(dx, dy)
            return True

        else:
            return super(GcodeViewerScreen, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            return True

        return super(GcodeViewerScreen, self).on_touch_up(touch)

    def select(self, on):
        if not on and self.select_mode:
            self.stop_cursor()
            self.select_mode = False
        elif on and not self.select_mode:
            x, y = self.center
            self.start_cursor(x, y)
            self.select_mode = True

    def move_gantry(self):
        if not self.select_mode:
            return

        self.select_mode = False
        self.ids.select_mode_but.state = 'normal'

        # convert to original model coordinates (mm), need to take into account scale and translate
        x, y = (self.crossx[0].pos[0], self.crossx[1].pos[1])
        self.stop_cursor(x, y)
        wpos = self.transform_to_wpos(x, y)

        if self.comms:
            self.comms.write('G0 X{:1.2f} Y{:1.2f}\n'.format(wpos[0], wpos[1]))
        else:
            print('Move Gantry to: {:1.2f}, {:1.2f}'.format(wpos[0], wpos[1]))
            print('G0 X{:1.2f} Y{:1.2f}'.format(wpos[0], wpos[1]))

    def set_wcs(self):
        if not self.select_mode:
            return

        self.select_mode = False
        self.ids.select_mode_but.state = 'normal'

        # convert to original model coordinates (mm), need to take into account scale and translate
        x, y = (self.crossx[0].pos[0], self.crossx[1].pos[1])
        self.stop_cursor(x, y)
        wpos = self.transform_to_wpos(x, y)
        if self.comms:
            self.comms.write('G10 L20 P0 X{:1.2f} Y{:1.2f}\n'.format(wpos[0], wpos[1]))
        else:
            print('Set WCS to: {:1.2f}, {:1.2f}'.format(wpos[0], wpos[1]))
            print('G10 L20 P0 X{:1.2f} Y{:1.2f}'.format(wpos[0], wpos[1]))

    def set_type(self, t):
        if t == '3D':
            self.twod_mode = False
            self.laser_mode = False
        elif t == '2D':
            self.twod_mode = True
            self.laser_mode = False
        elif t == 'Laser':
            self.twod_mode = True
            self.laser_mode = True

        self.loading()


if __name__ == '__main__':

    Builder.load_string('''
<StartScreen>:
    Button:
        text: 'Quit'
        on_press: app.stop()
<ExitScreen>:
    on_enter: app.stop()
''')

    class StartScreen(Screen):
        pass

    class ExitScreen(Screen):
        pass

    class GcodeViewerApp(App):
        is_cnc = BooleanProperty(False)
        is_connected = BooleanProperty(False)
        is_desktop = NumericProperty(3)
        wpos = ListProperty([0, 0, 0])

        def __init__(self, **kwargs):
            super(GcodeViewerApp, self).__init__(**kwargs)
            if len(sys.argv) > 1:
                self.gcode_file = sys.argv[1]
                if not self.gcode_file.endswith('.gcode'):
                    self.is_cnc = True
            else:
                self.gcode_file = 'test.gcode'  # 'circle-test.g'

        def build(self):
            Window.size = (1024, 768)
            self.sm = ScreenManager()
            self.sm.add_widget(StartScreen(name='start'))
            self.sm.add_widget(GcodeViewerScreen(name='gcode'))
            self.sm.add_widget(ExitScreen(name='main'))
            self.sm.current = 'gcode'

            level = LOG_LEVELS.get('debug') if len(sys.argv) > 2 else LOG_LEVELS.get('info')
            Logger.setLevel(level=level)
            logging.getLogger().setLevel(level)
            return self.sm

    GcodeViewerApp().run()
