
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import BooleanProperty, ObjectProperty
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from functools import partial
from kivy.clock import Clock

import os

Builder.load_string('''
<Row>:
    value: ''
    index: 0
    ro: True
    ti: ti
    TextInput:
        id: ti
        text: root.value
        multiline: False
        readonly: root.ro
        is_focusable: not root.ro
        idx: root.index
        background_color: (.0, 0.9, .1, 1) if root.selected else (0.8, 0.8, 0.8, 1)
        on_text_validate: root.save_change(root.index, self.text)
        on_focus: root.on_focus(*args)

<TextEditor>:
    rv: rv
    BoxLayout:
        canvas:
            Color:
                rgba: 0.3, 0.3, 0.3, 1
            Rectangle:
                size: self.size
                pos: self.pos
        rv: rv
        orientation: 'vertical'
        BoxLayout:
            size_hint_y: None
            height: dp(60)
            padding: dp(8)
            spacing: dp(16)
            Button:
                text: 'Close'
                on_press: root.close()
            ToggleButton:
                text: 'Edit' if not root.editable else "Readonly"
                on_press: root.set_edit()
            Button:
                text: 'Insert before'
                on_press: root.insert(True)
                disabled: not root.editable or rv.selected_idx < 0
            Button:
                text: 'Insert after'
                on_press: root.insert(False)
                disabled: not root.editable or rv.selected_idx < 0
            Button:
                text: 'Save'
                on_press: root.save()
                disabled: not root.editable

        RecycleView:
            id: rv
            scroll_type: ['bars', 'content']
            scroll_wheel_distance: dp(114)
            bar_width: dp(10)
            viewclass: 'Row'
            selected_idx: -1
            RecycleBoxLayout:
                default_size: None, dp(32)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                #multiselect: True
                #touch_multiselect: True
''')

class Row(BoxLayout):
    selected= BooleanProperty(False)
    rv= ObjectProperty()

    def on_focus(self, i, v):
        self.selected= v
        if v:
            self.rv.selected_idx= self.index
        else:
            self.rv.selected_idx= -1

    def save_change(self, k, v):
        #print("line {} changed to {}\n".format(k, v))
        self.rv.data[k]['value']= v
        self.rv.refresh_from_data()

class TextEditor(Screen):
    editable= BooleanProperty(False)

    def open(self, fn):
        self.fn= fn
        cnt= 0
        with open(fn) as f:
            for line in f:
                self.rv.data.append({'value': line.rstrip(), 'index': cnt, 'ro': not self.editable})
                cnt += 1
        self.max_cnt= cnt
        # add dummy lines at end so we can edit the last few files without keyboard covering them
        for i in range(10):
            self.rv.data.append({'value': '', 'index': -1, 'ro': True})

        Row.rv= self.rv

    def close(self):
        self.rv.data= []
        self.manager.current = 'main'

    def save(self):
        if self.editable:
            # rename old file to .bak
            os.rename(self.fn, self.fn+'.bak')
            with open(self.fn, 'w') as f:
                for l in self.rv.data:
                    # writeout file
                    if l['index'] >= 0:
                        f.write("{}\n".format(l['value']))

    def insert(self, before):
        # now see which line is selected and insert before or after that
        i= self.rv.selected_idx
        if i < 0:
            #print("No line is selected")
            return
        if not before:
            # insert after selected line
            i= i+1

        self.rv.data.insert(i, {'value': "ENTER TEXT", 'index': i, 'ro': False})
        self.max_cnt+=1
        # we need to renumber all following lines
        for j in range(i+1, self.max_cnt):
            self.rv.data[j]['index'] = j

        self.rv.refresh_from_data()
        Clock.schedule_once(partial(self._refocus_it, i), 0.3)

    def _refocus_it(self, i, *largs):
        self.rv.view_adapter.get_visible_view(i).ti.focus= True
        Clock.schedule_once(partial(self._select_it, i))
    def _select_it(self, i, *largs):
        self.rv.view_adapter.get_visible_view(i).ti.select_all()

    def set_edit(self):
        self.editable= not self.editable
        for l in self.rv.data:
            if l['index'] >= 0:
                l['ro']= not self.editable
        self.rv.refresh_from_data()

