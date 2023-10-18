# This file is part of Linecraft - Frequency response display and statistics tool
# Copyright (C) 2023 - Kerem Basaran
# https://github.com/kbasaran
__email__ = "kbasaran@gmail.com"

# Linecraft is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version.

# Linecraft is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public
# License along with Linecraft. If not, see <https://www.gnu.org/licenses/>

import os
import traceback

from PySide6 import QtWidgets as qtw
from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg

import sounddevice as sd
import numpy as np
from generictools import signal_tools
import pickle

import logging
if __name__ == "__main__":
    logger = logging.getLogger(__name__)
else:
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger()


class FloatSpinBox(qtw.QDoubleSpinBox):
    def __init__(self, name, tooltip,
                 decimals=2,
                 min_max=(0.01, 999.99),
                 ratio_to_SI=1,
                 user_data_widgets=None,
                 ):
        self._name = name
        super().__init__()
        if tooltip:
            self.setToolTip(tooltip)
        self.setStepType(qtw.QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
        self.setDecimals(decimals)
        if min_max:
            self.setRange(*min_max)
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        user_data_widgets[self._name] = self


class IntSpinBox(qtw.QSpinBox):
    def __init__(self, name, tooltip,
                 min_max=(0, 999999),
                 ratio_to_SI=1,
                 user_data_widgets=None
                 ):
        self._name = name
        super().__init__()
        if tooltip:
            self.setToolTip(tooltip)
        if min_max:
            self.setRange(*min_max)
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        user_data_widgets[self._name] = self

class CheckBox(qtw.QCheckBox):
    def __init__(self, name, tooltip,
                 user_data_widgets=None
                 ):
        self._name = name
        super().__init__()
        if tooltip:
            self.setToolTip(tooltip)
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        user_data_widgets[self._name] = self

class LineTextBox(qtw.QLineEdit):
    def __init__(self, name, tooltip, user_data_widgets=None):
        self._name = name
        super().__init__()
        if tooltip:
            self.setToolTip(tooltip)
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        user_data_widgets[self._name] = self


class SunkenLine(qtw.QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(qtw.QFrame.HLine)
        self.setFrameShadow(qtw.QFrame.Sunken)
        self.setContentsMargins(0, 10, 0, 10)


class Title(qtw.QLabel):
    def __init__(self, text:str):
        super().__init__()
        self.setText(text)
        self.setStyleSheet("font-weight: bold")
        self.setAlignment(qtg.Qt.AlignmentFlag.AlignCenter)


class PushButtonGroup(qtw.QWidget):
    def __init__(self, names: dict, tooltips: dict, vertical=False, user_data_widgets=None):
        """Both names and tooltips have the same keys: short_name's
        Values for names: text
        """
        self._buttons = dict()
        super().__init__()
        layout = qtw.QVBoxLayout(self) if vertical else qtw.QHBoxLayout(self)
        for key, val in names.items():
            name = key + "_pushbutton"
            button = qtw.QPushButton(val)
            if key in tooltips:
                button.setToolTip(tooltips[key])
            layout.addWidget(button)
            self._buttons[name] = button
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        for name, button in self._buttons.items():
            user_data_widgets[name] = button

    def buttons(self) -> dict:
        return self._buttons

class ChoiceButtonGroup(qtw.QWidget):
    def __init__(self, group_name, names: dict, tooltips: dict, vertical=False, user_data_widgets=None):
        """keys for names: integers
        values for names: text
        """
        self._name = group_name
        super().__init__()
        self.button_group = qtw.QButtonGroup()
        layout = qtw.QVBoxLayout(self) if vertical else qtw.QHBoxLayout(self)
        for key, button_name in names.items():
            button = qtw.QRadioButton(button_name)
            if key in tooltips:
                button.setToolTip(tooltips[key])
            self.button_group.addButton(button, key)
            layout.addWidget(button)
        self.button_group.buttons()[0].setChecked(True)
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        user_data_widgets[self._name] = self.button_group

    def buttons(self) -> list:
        return self.self.button_group.buttons()

class ComboBox(qtw.QComboBox):
    def __init__(self, name,
                 tooltip,
                 items: list,
                 user_data_widgets=None):
        self._name = name
        super().__init__()
        if tooltip:
            self.setToolTip(tooltip)
        for item in items:
            self.addItem(*item)  # tuple with userData, therefore *
        if user_data_widgets is not None:
            self.user_values_storage(user_data_widgets)

    def user_values_storage(self, user_data_widgets: dict):
        user_data_widgets[self._name] = self


class SubForm(qtw.QWidget):
    def __init__(self):
        super().__init__()
        self._layout = qtw.QFormLayout(self)
        

class UserForm(qtw.QWidget):
    def __init__(self):
        super().__init__()
        self._layout = qtw.QFormLayout(self)  # the argument makes already here the "setLayout" for the widget
        self._create_core_objects()

    def _create_core_objects(self):
        self._user_input_widgets = dict()

    def add_row(self, obj, description=None, into_form=None):
        if into_form:
            layout = into_form.layout()
        else:
            layout = self.layout()

        if description:
            layout.addRow(description, obj)
        else:
            layout.addRow(obj)

        if hasattr(obj, "user_values_storage"):
            obj.user_values_storage(self._user_input_widgets)

    def update_form_values(self, values_new: dict):
        no_dict_key_for_widget = set(
            [key for key in self._user_input_widgets.keys() if "_button" not in key])  # works???????????????????????
        no_widget_for_dict_key = set()
        for key, value_new in values_new.items():
            try:
                obj = self._user_input_widgets[key]

                if isinstance(obj, qtw.QComboBox):
                    assert isinstance(value_new, dict)
                    if "items" in value_new.keys():
                        obj.clear()
                        # assert all([key in value_new.keys() for key in ["items", "current_index"]])
                        for item in value_new.get("items", []):
                            obj.addItem(*item)
                    obj.setCurrentIndex(value_new["current_index"])

                elif isinstance(obj, qtw.QLineEdit):
                    assert isinstance(value_new, str)
                    obj.setText(value_new)

                elif isinstance(obj, qtw.QPushButton):
                    raise TypeError(
                        f"Don't know what to do with value_new={value_new} for button {key}.")

                elif isinstance(obj, qtw.QButtonGroup):
                    obj.button(value_new).setChecked(True)

                elif isinstance(obj, qtw.QCheckBox):
                    obj.setChecked(value_new)

                else:
                    assert type(value_new) == type(obj.value())
                    obj.setValue(value_new)

                # finally
                no_dict_key_for_widget.discard(key)

            except KeyError:
                no_widget_for_dict_key.update((key,))

        if no_widget_for_dict_key | no_dict_key_for_widget:
            raise ValueError(f"No widget(s) found for the keys: '{no_widget_for_dict_key}'\n"
                             f"No data found to update the widget(s): '{no_dict_key_for_widget}'"
                             )

    def get_form_values(self) -> dict:
        values = {}
        for key, obj in self._user_input_widgets.items():

            if "_button" in key:
                continue

            if isinstance(obj, qtw.QComboBox):
                obj_value = {"items": [], "current_index": 0}
                for i_item in range(obj.count()):
                    item_text = obj.itemText(i_item)
                    item_data = obj.itemData(i_item)
                    obj_value["items"].append((item_text, item_data))
                obj_value["current_index"] = obj.currentIndex()

            elif isinstance(obj, qtw.QLineEdit):
                obj_value = obj.text()

            elif isinstance(obj, qtw.QButtonGroup):
                obj_value = obj.checkedId()

            elif isinstance(obj, qtw.QCheckBox):
                obj_value = obj.isChecked()

            else:
                obj_value = obj.value()

            values[key] = obj_value

        logger.debug("Return of 'get_form_values")
        for val, key in values.items():
            logger.debug(val, type(val), key, type(key))

        return values


class SoundEngine(qtc.QObject):
    def __init__(self, settings):
        super().__init__()
        self.app_settings = settings
        self.verify_stream()

    def verify_stream(self):
        self.FS = sd.query_devices(device=sd.default.device, kind='output',
                                   )["default_samplerate"]
        # needs to be improved and tested for device changes!
        if not hasattr(self, "stream"):
            self.stream = sd.OutputStream(samplerate=self.FS, channels=2)
        if not self.stream.active:
            self.stream.start()

    @qtc.Slot(float, float, float)
    def beep(self, A, T, freq):
        self.verify_stream()
        t = np.arange(T * self.FS) / self.FS
        y = A * np.sin(t * 2 * np.pi * freq)
        fade_window = signal_tools.make_fade_window_n(1, 0, len(y), fade_start_end_idx=(len(y) - int(self.FS / 10), len(y)))
        y = y * fade_window
        pad = np.zeros(int(self.FS / 10))
        y = np.concatenate([y, pad])
        y = np.tile(y, self.stream.channels)
        y = y.reshape((len(y) // self.stream.channels,
                      self.stream.channels), order='F').astype(self.stream.dtype)
        y = np.ascontiguousarray(y, self.stream.dtype)
        self.stream.write(y)

    @qtc.Slot()
    def good_beep(self):
        self.beep(self.app_settings.A_beep / 2, 0.1, 587.3)

    @qtc.Slot()
    def bad_beep(self):
        self.beep(self.app_settings.A_beep, 0.1, 293.7)

    @qtc.Slot()
    def release_all(self):
        self.stream.stop(ignore_errors=True)

class ErrorHandlerDeveloper:
    def __init__(self, app):
        self.app = app
    
    def excepthook(self, etype, value, tb):
        error_msg_developer = ''.join(traceback.format_exception(etype, value, tb))
        message_box = qtw.QMessageBox(qtw.QMessageBox.Warning,
                                      "Error    :(",
                                      error_msg_developer +
                                      "\n\nThis event may be logged unless ignore is chosen.",
                                      )
        message_box.addButton(qtw.QMessageBox.Ignore)
        close_button = message_box.addButton(qtw.QMessageBox.Close)
    
        message_box.setEscapeButton(qtw.QMessageBox.Ignore)
        message_box.setDefaultButton(qtw.QMessageBox.Close)
    
        close_button.clicked.connect(logger.warning(error_msg_developer))
    
        message_box.exec()

class ErrorHandlerUser:
    def __init__(self, app):
        self.app = app
    
    def excepthook(self, etype, value, tb):
        error_msg_developer = ''.join(traceback.format_exception(etype, value, tb))
        error_info = traceback.format_exception(etype, value, tb)
        error_msg_short = error_info[-2] + "\n\n" + error_info[-1]
        message_box = qtw.QMessageBox(qtw.QMessageBox.Warning,
                                      "Error    :(",
                                      error_msg_short +
                                      "\n\nThis event may be logged unless ignore is chosen.",
                                      )
        message_box.addButton(qtw.QMessageBox.Ignore)
        close_button = message_box.addButton(qtw.QMessageBox.Close)
    
        message_box.setEscapeButton(qtw.QMessageBox.Ignore)
        message_box.setDefaultButton(qtw.QMessageBox.Close)
    
        close_button.clicked.connect(logger.warning(error_msg_developer))
    
        message_box.exec()

class LoadSaveEngine:
    """
    Data to save for the graph in general:
        Plot title: sget_title
        Plot x label: sget_xlabel
        Plot y label: sget_ylabel
        x linear/log: sget_xscale
        y linear/log: sget_yscale

    Data to save per curve item:
        Curve object in CurveAnalyze.curves
        Line2D:
            style: sget_linestyle
            draw style: sget_drawstyle
            width: sget_linewidth
            color: sget_color
        Line2D marker:
            style: sget_marker
            size: sget_markersize
            face col: sget_markerfacecolor
            edge col: sget_markeredgecolor
    """

    def collect_graph_info(self, ax):
        graph_info = {"title": ax.get_title(),
                      "xlabel": ax.get_xlabel(),
                      "ylabel": ax.get_ylabel(),
                      "xscale": ax.get_xscale(),
                      "yscale": ax.get_yscale(),
                      }
        return graph_info

    def collect_line2d_info(self, line):
        line_info = {"style": line.get_style(),
                     "drawstyle": line.get_drawstyle(),
                     "width": line.get_width(),
                     "color": line.get_color(),
                     "marker": line.get_marker(),
                     "markersize": line.get_markersize(),
                     "markerfacecolor": line.get_markerfacecolor(),
                     "markeredgecolor": line.get_markeredgecolor(),
                     }
        return line_info

    def collect_curve_info(self, curve):
        curve_info = {"visible": curve.is_visible(),
                      "identification": curve._identification,
                      "x": tuple(curve.get_x()),
                      "y": tuple(curve.get_y()),
                      }
        return curve_info

    def collect_all_info(self, ax, lines, curves):
        graph_info = self.collect_graph_info(ax)
        lines_info = []
        curves_info = []
        for line, curve in zip(lines, curves):
            lines_info.append(self.collect_line2d_info(line))
            curves_info.append(self.collect_curve_info(curve))

        package = pickle.dumps([graph_info, lines_info, curves_info], protocol=5)
        return package
