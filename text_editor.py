
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import BooleanProperty
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from functools import partial
from kivy.clock import Clock

Builder.load_string('''
<SelectableBox>:
    value: ''
    index: 0
    ro: True
    ti: ti
    TextInput:
        id: ti
        text: root.value
        multiline: False
        readonly: root.ro
        idx: root.index
        background_color: (.0, 0.9, .1, 1) if root.selected else (0.8, 0.8, 0.8, 1)
        on_text_validate: root.parent.parent.parent.parent.save_change(root.index, self.text)

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
                text: 'Editable' if root.editable else "Readonly"
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
            viewclass: 'SelectableBox'
            selected_idx: -1
            SelectableRecycleBoxLayout:
                default_size: None, dp(32)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                #multiselect: True
                #touch_multiselect: True
''')

class SelectableRecycleBoxLayout(FocusBehavior, LayoutSelectionBehavior,
                                 RecycleBoxLayout):
    ''' Adds selection and focus behaviour to the view. '''

class SelectableBox(RecycleDataViewBehavior, BoxLayout):
    ''' Add selection support to the Label '''
    index = None
    selected = BooleanProperty(False)

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        return super(SelectableBox, self).refresh_view_attrs(
            rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        super(SelectableBox, self).on_touch_down(touch)
        if self.collide_point(*touch.pos):
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to the selection of items in the view. '''
        self.selected = is_selected
        if is_selected:
            #print("selection changed to {0}".format(rv.data[index]))
            rv.selected_idx = index
        else:
            #print("selection removed for {0}".format(rv.data[index]))
            rv.selected_idx = -1

class TextEditor(Screen):
    editable= BooleanProperty(False)

    def open(self, fn):
        cnt= 0
        with open(fn) as f:
            for line in f:
                self.rv.data.append({'value': line.rstrip(), 'index': cnt, 'ro': True})
                cnt += 1

    def close(self):
        self.rv.data= []
        self.manager.current = 'main'

    def save(self):
        if self.editable:
            # rename old file to .bak
            for l in self.rv.data:
                # writeout file
                print(l)

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
        # we need to renumber all following lines
        cnt= len(self.rv.data)
        for j in range(i+1, cnt):
            self.rv.data[j]['index'] = j

    #     self.rv.refresh_from_data()
    #     Clock.schedule_once(partial(self._refocus_it, i))

    # def _refocus_it(self, i, *largs):
    #     print("set focus to index {}".format(i))
    #     self.rv.view_adapter.get_visible_view(i).ti.focus= True
    #     self.rv.view_adapter.get_visible_view(i).ti.select_all()

    def set_edit(self):
        self.editable= not self.editable
        for l in self.rv.data:
            l['ro']= not self.editable
        self.rv.refresh_from_data()

    def save_change(self, k, v):
        #print("line {} changed to {}\n".format(k, v))
        if self.editable:
            self.rv.data[k]['value']= v
            self.rv.refresh_from_data()
