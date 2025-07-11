# Linecraft - Frequency response display and statistics tool
# Copyright (C) 2025 - Kerem Basaran
# https://github.com/kbasaran
__email__ = "kbasaran@gmail.com"

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from difflib import SequenceMatcher
from dataclasses import dataclass, fields
from copy import copy, deepcopy

# from matplotlib.backends.qt_compat import QtWidgets as qtw
from PySide6 import QtWidgets as qtw
from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg

from generictools.graphing_widget import MatplotlibWidget
# https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_qt_sgskip.html

from generictools import signal_tools
import generictools.personalized_widgets as pwi
import pyperclip  # must install xclip on Linux together with this!!
from functools import partial
import matplotlib as mpl
from tabulate import tabulate
from io import StringIO
import pickle
import logging
import time

app_definitions = {"app_name": "Linecraft",
                   "version": "0.3.3",
                   # "version": "Test build " + today.strftime("%Y.%m.%d"),
                   "description": "Linecraft - Frequency response plotting and statistics",
                   "copyright": "Copyright (C) 2025 Kerem Basaran",
                   "icon_path": str(Path("./logo/icon.ico")),
                   "author": "Kerem Basaran",
                   "author_short": "kbasaran",
                   "email": "kbasaran@gmail.com",
                   "website": "https://github.com/kbasaran",
                   }


@dataclass
class Settings:
    global logger
    app_name: str = app_definitions["app_name"]
    author: str = app_definitions["author"]
    author_short: str = app_definitions["author_short"]
    version: str = app_definitions["version"]

    last_used_folder: str = str(Path.home())

    A_beep: float = 0.25
    show_legend: bool = True
    max_legend_size: int = 7
    import_ppo: int = 96
    export_ppo: int = 96
    matplotlib_style: str = "ggplot"
    interpolate_must_contain_hz: int = 1000
    graph_grids: str = "Major and minor"

    processing_selected_tab: int = 0

    mean_selected: bool = False
    median_selected: bool = True

    smoothing_type: str = "Butterworth 8th, log spaced"
    smoothing_resolution_ppo: int = 96
    smoothing_bandwidth: int = 6

    outlier_fence_iqr: float = 10.
    outlier_check_start_freq: int = 20
    outlier_check_end_freq: int = 20_000
    outlier_action: str = "None"

    sum_selected: bool = True
    diff_selected: bool = True

    average_calc_f_start: float = 20
    average_calc_f_end: float = 20_000

    add_gain_value: float = 0

    processing_interpolation_ppo: int = 96

    best_fit_calculation_resolution_ppo: int = 24
    best_fit_critical_range_start_freq: int = 200
    best_fit_critical_range_end_freq: int = 5000
    best_fit_critical_range_weight: int = 1

    import_table_no_line_headers: int = 1
    import_table_no_columns: int = 1
    import_table_layout_type: str = "Headers are frequencies, indexes are names"
    import_table_delimiter: str = "Tab"
    import_table_decimal_separator: str = ". (dot)"

    def __post_init__(self):
        settings_storage_title = (self.app_name
                                  + " v"
                                  + (".".join(self.version.split(".")[:2])
                                     if "." in self.version
                                     else "???"
                                     )
                                  )
        self.settings_sys = qtc.QSettings(
            self.author_short, settings_storage_title)
        self.read_all_from_registry()
        self._field_types = {field.name: field.type for field in fields(self)}
        
    def update(self, attr_name, new_val):
        # Update a given setting
        # Check type of new_val first
        expected_type = self._field_types[attr_name]
        if type(new_val) != expected_type:
            raise TypeError(f"Incorrect data type received for setting '{attr_name}'. Expected type: {expected_type}. Received type/value: {type(new_val)}/{new_val}.")
        setattr(self, attr_name, new_val)
        self.settings_sys.setValue(attr_name, getattr(self, attr_name))

    def write_all_to_registry(self):
        for field in fields(self):
            value = getattr(self, field.name)

            # convert tuples to list for Qt compatibility
            value = list(value) if isinstance(value, tuple) else value

            self.settings_sys.setValue(field.name, value)

    def read_all_from_registry(self):
        for field in fields(self):
            try:
                value_raw = self.settings_sys.value(field.name, field.default)
                value = field.type(value_raw)
            except (TypeError, ValueError):
                value = field.default

            setattr(self, field.name, value)

    def as_dict(self):  # better use asdict method from dataclasses instead of this
        # return the settings as a dict
        settings = {}
        for field in fields(self):
            settings[field.name] = getattr(self, field.name)
        return settings

    def __repr__(self):
        return str(self.as_dict())

# Guide for special comments
# https://docs.spyder-ide.org/current/panes/outline.html


def find_longest_match_in_name(names: list) -> str:
    """
    https://stackoverflow.com/questions/58585052/find-most-common-substring-in-a-list-of-strings
    https://www.adamsmith.haus/python/docs/difflib.SequenceMatcher.get_matching_blocks

    Parameters
    ----------
    names : list
        A list of names, each one a string.

    Returns
    -------
    max_occurring_substring : str
        The piece of string that accurs most commonly in the received list of names.

    """
    substring_counts = {}
    names_list = list(names)
    for i in range(0, len(names)):
        for j in range(i+1, len(names)):
            string1 = str(names_list[i])
            string2 = str(names_list[j])
            match = SequenceMatcher(None, string1, string2).find_longest_match(
                0, len(string1), 0, len(string2))
            matching_substring = string1[match.a:match.a+match.size]
            if (matching_substring not in substring_counts):
                substring_counts[matching_substring] = 1
            else:
                substring_counts[matching_substring] += 1

    # max() looks at the output of get method
    max_occurring_key = max(substring_counts, key=substring_counts.get)

    for char in " - - ":
        max_occurring_key = max_occurring_key.strip(char)

    return max_occurring_key


class CurveAnalyze(qtw.QMainWindow):
    global settings, app_definitions, logger

    signal_good_beep = qtc.Signal()
    signal_bad_beep = qtc.Signal()
    signal_user_settings_changed = qtc.Signal()
    signal_table_import_successful = qtc.Signal()
    signal_table_import_fail = qtc.Signal()
    signal_table_import_busy = qtc.Signal()

    # ---- Signals to the graph
    # signal_update_figure_request = qtc.Signal(object)  # failed to pass all the args and kwargs
    # in an elegant way
    # it is in fact a dict but PySide6 has a bug for passing dict
    signal_update_labels_request = qtc.Signal(object)
    signal_reset_colors_request = qtc.Signal()
    signal_remove_curves_request = qtc.Signal(list)
    # signal_update_visibility_request = qtc.Signal(object)  # it is in fact a dict but PySide6 has a bug for passing dict
    # it is in fact a dict but PySide6 has a bug for passing dict
    signal_reposition_curves_request = qtc.Signal(object)
    signal_flash_curve_request = qtc.Signal(int)
    signal_toggle_reference_curve_request = qtc.Signal(
        object)  # it is a list or a NoneType
    # signal_add_line_request = qtc.Signal(list, object)  # failed to pass all the args and kwargs
    # in an elegant way

    def __init__(self):
        super().__init__()
        self.setWindowTitle(" - ".join(
            (app_definitions["app_name"],
             app_definitions["version"])
            ))
        self._create_core_objects()
        self._create_menu_bar()
        self._create_widgets()
        self._place_widgets()
        self._make_connections()

    def keyPressEvent(self, keyEvent):
        # overwriting method that was inherited from class
        # Sequence names: https://doc.qt.io/qtforpython-6/PySide6/QtGui/QKeySequence.html
        # Strange that F2 is not available as 'Rename'
        if keyEvent.matches(qtg.QKeySequence.Delete):
            self.remove_curves()
        if keyEvent.matches(qtg.QKeySequence.Cancel):
            self.qlistwidget_for_curves.setCurrentRow(-1)

    def _create_core_objects(self):
        # a dictionary of QWidgets that users interact with
        self._interactable_widgets = dict()
        # frequency response curves. THIS IS THE SINGLE SOURCE OF TRUTH FOR CURVE DATA.
        self.curves = []

    def _create_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        add_action = file_menu.addAction(
            "Add state to current..", self.pick_a_file_and_add_state_from_it)
        save_action = file_menu.addAction(
            "Save current state..", self.save_state_to_file)

        edit_menu = menu_bar.addMenu("Edit")
        settings_action = edit_menu.addAction(
            "Settings..", self.open_settings_dialog)

        help_menu = menu_bar.addMenu("Help")
        about_action = help_menu.addAction("About", self.open_about_menu)

    def _create_widgets(self):
        # ---- Create graph and buttons widget
        self.graph = MatplotlibWidget(settings, layout_engine="tight")
        self.graph.set_y_limits_policy("SPL")
        self.graph_buttons = pwi.PushButtonGroup(
            {
                "import_curve": "Import curve",
                "import_table": "Import table",
                "auto_import": "Auto import",
                "reset_indexes": "Reset indexes",
                "reset_colors": "Reset colors",
                "remove": "Remove",
                "rename": "Rename",
                "move_up": "Move up",
                "move_to_top": "Move to top",
                "hide": "Hide",
                "show": "Show",
                "set_reference": "Set reference",
                "processing": "Processing",
                "export_curve": "Export curve",
            },
            {"import_curve": "Import 2D curve from clipboard",
             "auto_import": "Attempt an import whenever new data is found on the clipboard.",
             },
        )
        # Add the widgets that users interact with into the dictionary
        self.graph_buttons.add_elements_to_dict(self._interactable_widgets)

        # ---- Set types and states for buttons
        self._interactable_widgets["auto_import_pushbutton"].setCheckable(True)
        self._interactable_widgets["set_reference_pushbutton"].setCheckable(
            True)

        # ---- Create list widget
        self.qlistwidget_for_curves = qtw.QListWidget()
        self.qlistwidget_for_curves.setSelectionMode(
            qtw.QAbstractItemView.ExtendedSelection)
        # self.qlistwidget_for_curves.setDragDropMode(qtw.QAbstractItemView.InternalMove)  # crashes the application

    def _place_widgets(self):
        self.setCentralWidget(qtw.QWidget())
        self.centralWidget().setLayout(qtw.QVBoxLayout())
        # self.layout().setSpacing(0)
        self.centralWidget().layout().addWidget(self.graph, 3)
        self.centralWidget().layout().addWidget(self.graph_buttons)
        self.centralWidget().layout().addWidget(self.qlistwidget_for_curves, 1)

        # set size policies
        self.graph.setSizePolicy(
            qtw.QSizePolicy.Expanding, qtw.QSizePolicy.MinimumExpanding)

    def _make_connections(self):
        # ---- All the buttons
        self._interactable_widgets["remove_pushbutton"].clicked.connect(
            self.remove_curves)
        self._interactable_widgets["reset_indexes_pushbutton"].clicked.connect(
            self.reset_indexes)
        self._interactable_widgets["reset_colors_pushbutton"].clicked.connect(
            self.reset_colors_of_curves)
        self._interactable_widgets["rename_pushbutton"].clicked.connect(
            self._rename_curve_clicked)
        self._interactable_widgets["move_up_pushbutton"].clicked.connect(
            self.move_up_1)
        self._interactable_widgets["move_to_top_pushbutton"].clicked.connect(
            self.move_to_top)
        self._interactable_widgets["hide_pushbutton"].clicked.connect(
            self.hide_curves)
        self._interactable_widgets["show_pushbutton"].clicked.connect(
            self.show_curves)
        self._interactable_widgets["export_curve_pushbutton"].clicked.connect(
            self._export_curve)
        self._interactable_widgets["auto_import_pushbutton"].toggled.connect(
            self._auto_importer_status_toggle)
        self._interactable_widgets["set_reference_pushbutton"].toggled.connect(
            self.reference_curve_status_toggle)
        self._interactable_widgets["processing_pushbutton"].clicked.connect(
            self.open_processing_dialog)
        self._interactable_widgets["import_curve_pushbutton"].clicked.connect(
            self.import_single_curve)
        self._interactable_widgets["import_table_pushbutton"].clicked.connect(
            self._import_table_clicked)

        # ---- Double click for highlighting/flashing a curve
        self.qlistwidget_for_curves.itemActivated.connect(self._flash_curve)

        # ---- Signals to Matplolib graph
        # self.signal_update_figure_request.connect(self.graph.update_figure)
        self.signal_reposition_curves_request.connect(
            self.graph.change_lines_order)
        self.signal_flash_curve_request.connect(self.graph.flash_curve)
        self.signal_update_labels_request.connect(
            self.graph.update_labels_and_visibilities)
        self.signal_reset_colors_request.connect(self.graph.reset_colors)
        self.signal_remove_curves_request.connect(
            self.graph.remove_multiple_line2d)
        self.signal_toggle_reference_curve_request.connect(
            self.graph.toggle_reference_curve)
        # self.signal_add_line_request.connect(self.graph.add_line2d)
        # self.signal_update_visibility_request.connect(self.graph.update_labels_and_visibilities)

        # ---- Signals from Matplotlib graph
        self.graph.signal_good_beep.connect(self.signal_good_beep)
        self.graph.signal_bad_beep.connect(self.signal_bad_beep)
        self.graph.signal_is_reference_curve_active.connect(
            self._interactable_widgets["set_reference_pushbutton"].setChecked)

        # Disable some buttons when there is a reference curve active
        self.graph.signal_is_reference_curve_active.connect(
            lambda x: self._interactable_widgets["processing_pushbutton"].setEnabled(not x))
        self.graph.signal_is_reference_curve_active.connect(
            lambda x: self._interactable_widgets["export_curve_pushbutton"].setEnabled(not x))

        # Import table dialog good/bad beeps
        self.signal_table_import_successful.connect(self.signal_good_beep)
        self.signal_table_import_fail.connect(self.signal_bad_beep)

    def _export_curve(self):
        """Paste selected curve(s) to clipboard in a table."""
        if self.return_false_and_beep_if_no_curve_selected():
            return
        elif len(self.qlistwidget_for_curves.selectedItems()) > 1:
            message_box = qtw.QMessageBox(qtw.QMessageBox.Information,
                                          "Feature not Implemented",
                                          "Can only export one curve at a time.",
                                          )
            message_box.setStandardButtons(qtw.QMessageBox.Ok)
            message_box.exec()
            return
        else:
            curve = self.get_selected_curves()[0]
        
        curve.export_to_clipboard(ppo=settings.export_ppo,
                                  must_include_freq=settings.interpolate_must_contain_hz,
                                  )
        self.signal_good_beep.emit()

    def _get_curve_from_clipboard(self):
        """Read a signal_tools.Curve object from clipboard."""
        data = pyperclip.paste()
        new_curve = signal_tools.Curve(data)
        if new_curve.is_curve():
            return new_curve
        else:
            print(f"Unrecognized curve object for data:\n{data}")
            return None

    def get_selected_curve_indexes(self) -> list:
        """Get a list of indexes for the curves currently selected in the list widget. MAY NOT BE SORTED!"""
        selected_list_items = self.qlistwidget_for_curves.selectedItems()
        indexes = [self.qlistwidget_for_curves.row(
            list_item) for list_item in selected_list_items]
        return indexes

    def get_selected_curves(self, as_dict: bool = False) -> (list, dict):
        """May NOT be SORTED"""
        selected_indexes = self.get_selected_curve_indexes()

        if as_dict:
            return {i: self.curves[i] for i in selected_indexes}
        else:
            return [self.curves[i] for i in selected_indexes]

    def get_selected_curves_sorted(self) -> list:
        curves = self.get_selected_curves(as_dict=True)
        return sorted(curves.items()).values()

    def count_selected_curves(self) -> int:
        selected_indexes = self.get_selected_curve_indexes()
        return len(selected_indexes)

    def return_false_and_beep_if_no_curve_selected(self) -> bool:
        if self.qlistwidget_for_curves.selectedItems():
            return False
        else:
            self.signal_bad_beep.emit()
            return True

    def _move_curve_up(self, i_insert: int):
        """Move curve up to index 'i_insert'"""
        selected_indexes_and_curves = self.get_selected_curves(as_dict=True)

        new_order_of_qlist_items = [*range(len(self.curves))]
        # each number in the list is the index before location change. index in the list is the new location.
        for i_within_selected, (i_before, curve) in enumerate(sorted(selected_indexes_and_curves.items())):
            # i_within_selected is the index within the selected curves
            # i_before is the index on the complete curves list
            i_after = i_insert + i_within_selected
            if i_before < i_after:
                raise IndexError(
                    "This function can only move the item higher up in the list.")

            # update the self.curves list (single source of truth)
            curve = self.curves.pop(i_before)
            self.curves.insert(i_after, curve)

            # update the QListWidget
            new_list_item = qtw.QListWidgetItem(curve.get_full_name())
            if not curve.is_visible():
                font = new_list_item.font()
                font.setWeight(qtg.QFont.Thin)
                new_list_item.setFont(font)

            self.qlistwidget_for_curves.insertItem(i_after, new_list_item)
            self.qlistwidget_for_curves.takeItem(i_before + 1)

            # update the changes dictionary to send to the graph
            new_order_of_qlist_items.insert(
                i_after, new_order_of_qlist_items.pop(i_before))

        new_indexes_of_qlist_items = dict(
            zip(new_order_of_qlist_items, range(len(self.curves))))

        # send the changes dictionary to the graph
        self.signal_reposition_curves_request.emit(new_indexes_of_qlist_items)

    def move_up_1(self):
        if self.return_false_and_beep_if_no_curve_selected():
            return
        selected_indexes = self.get_selected_curve_indexes()
        i_insert = max(0, selected_indexes[0] - 1)
        self._move_curve_up(i_insert)
        if len(selected_indexes) == 1:
            self.qlistwidget_for_curves.setCurrentRow(i_insert)

    def move_to_top(self):
        if self.return_false_and_beep_if_no_curve_selected():
            return
        self._move_curve_up(0)
        self.qlistwidget_for_curves.setCurrentRow(-1)

    def reset_indexes(self):
        """Reset the indexes that are stored in the signal_tools.Curve objects and shown as prefix of the name"""
        if not len(self.curves):
            self.signal_bad_beep.emit()
        else:
            new_labels = {}
            for i, curve in enumerate(self.curves):
                # print(i, curve.get_full_name())
                curve.set_name_prefix(f"#{i:02d}")
                self.qlistwidget_for_curves.item(
                    i).setText(curve.get_full_name())
                new_labels[i] = (curve.get_full_name(), curve.is_visible())

            self.signal_update_labels_request.emit(new_labels)

    def reset_colors_of_curves(self):
        """Reset the colors for the graph curves with ordered standard colors"""
        if not len(self.curves):
            self.signal_bad_beep.emit()
        else:
            self.signal_reset_colors_request.emit()

    def _rename_curve_clicked(self):
        """Update the base name and suffix. Does not modify the index part (the prefix in Curve object)."""
        new_labels = {}

        if self.return_false_and_beep_if_no_curve_selected():
            return

        # ---- Multiple curves. Can only add a common suffix.
        elif len(self.qlistwidget_for_curves.selectedItems()) > 1:
            indexes_and_curves = self.get_selected_curves(as_dict=True)
            text, ok = qtw.QInputDialog.getText(self,
                                                "Add suffix to multiple names",
                                                "Add suffix:", qtw.QLineEdit.Normal,
                                                "",
                                                )
            if not ok or text == '':
                return

            for index, curve in indexes_and_curves.items():
                curve.add_name_suffix(text)
                list_item = self.qlistwidget_for_curves.item(index)
                list_item.setText(curve.get_full_name())
                new_labels[index] = (curve.get_full_name(), curve.is_visible())

        # ---- Single curve. Edit base name and suffixes into a new base name
        else:
            index = self.qlistwidget_for_curves.currentRow()
            curve = self.curves[index]

            text, ok = qtw.QInputDialog.getText(self,
                                                "Change curve name",
                                                "New name:", qtw.QLineEdit.Normal,
                                                curve.get_base_name_and_suffixes(),
                                                )
            if not ok or text == '':
                return

            curve.clear_name_suffixes()
            curve.set_name_base(text)
            list_item = self.qlistwidget_for_curves.item(index)
            list_item.setText(curve.get_full_name())
            new_labels[index] = (curve.get_full_name(), curve.is_visible())

        self.graph.update_labels_and_visibilities(new_labels)

    def import_single_curve(self, curve: signal_tools.Curve = None):
        if not curve:
            clipboard_curve = self._get_curve_from_clipboard()
            if clipboard_curve is None:
                self.signal_bad_beep.emit()
                return
            else:
                curve = clipboard_curve

        if settings.import_ppo > 0:
            x, y = curve.get_xy()
            x_intp, y_intp = signal_tools.interpolate_to_ppo(
                x, y,
                settings.import_ppo,
                settings.interpolate_must_contain_hz,
            )
            curve.set_xy((x_intp, y_intp))

        if "clipboard_curve" in locals() or curve.is_curve():
            i_insert = self._add_single_curve(None, curve)
            self.qlistwidget_for_curves.setCurrentRow(i_insert)
            self.signal_good_beep.emit()
        else:
            self.signal_bad_beep.emit()

    def remove_curves(self, indexes: list = None):
        if isinstance(indexes, (list, np.ndarray)):
            if len(indexes) == 0:  # received empty list
                self.signal_bad_beep.emit()
                return
            else:
                indexes_to_remove = indexes

        elif not indexes:
            if self.return_false_and_beep_if_no_curve_selected():
                return
            else:
                indexes_to_remove = self.get_selected_curve_indexes()

        for i in sorted(indexes_to_remove, reverse=True):
            self.qlistwidget_for_curves.takeItem(i)
            self.curves.pop(i)

        self.signal_remove_curves_request.emit(indexes_to_remove)

    def _import_table_clicked(self):
        import_table_dialog = ImportDialog(parent=self)

        import_table_dialog.signal_import_table_request.connect(
            self._import_table_requested)
        self.signal_table_import_busy.connect(import_table_dialog.deactivate)

        self.signal_table_import_successful.connect(import_table_dialog.reject)

        self.signal_table_import_fail.connect(import_table_dialog.reactivate)

        import_table_dialog.exec()

    def _import_table_requested(self, source, import_settings):
        start_time = time.perf_counter()
        # ---- get the input
        logger.info(f"Import table requested from {source}.")
        logger.debug("Settings:" + str(settings))
        if source == "file":
            file_raw = qtw.QFileDialog.getOpenFileName(self, caption='Open CSV formatted file..',
                                                       dir=settings.last_used_folder,
                                                       filter='CSV format (*.txt *.csv)',
                                                       )[0]

            if file_raw and (file := Path(file_raw)).is_file():
                settings.update("last_used_folder", str(file.parent))
                import_file = file

            else:
                return

        elif source == "clipboard":
            import_file = StringIO(pyperclip.paste())

        # ---- setup how to read it
        if import_settings["no_header"] == 0:
            skiprows = None
            header = None
        else:
            skiprows = [*range(import_settings["no_header"] - 1)
                        ] if import_settings["no_header"] > 1 else None
            header = 0

        if import_settings["no_index"] == 0:
            index_col = None
        else:
            index_col = import_settings["no_index"] - 1

        # ---- read it
        self.signal_table_import_busy.emit()
        logger.debug(
            ("Attempting read_csv with settings:"
             f"\ndelimiter: {import_settings['delimiter']}"
             f"\ndecimal: {import_settings['decimal_separator']}"
             f"\nskiprows: {skiprows}"
             f"\nheader: {header}"
             f"\nindex_col: {index_col}")
        )

        try:
            df = pd.read_csv(import_file,
                             delimiter=import_settings["delimiter"],
                             decimal=import_settings["decimal_separator"],
                             skiprows=skiprows,
                             header=header,
                             index_col=index_col,
                             # skip_blank_lines=True,
                             # encoding='unicode_escape',
                             skipinitialspace=True,  # since we only have numbers
                             )
        except IndexError as e:
            logger.warning("IndexError: " + str(e))
            # always emit this first so the import dialog knows it didn't work
            self.signal_table_import_fail.emit()
            raise IndexError(
                "Check your import settings and if all your rows and columns have the same length in the imported text.")
        except (pd.errors.EmptyDataError, TypeError) as e:
            logger.warning("EmptyDataError: " + str(e))
            self.signal_table_import_fail.emit()
            return

        logger.debug(
            (f"Imported column names: {df.columns}"
             f"\nImported index names: {df.index}"
             f"\nWhole:\n{df}\n"
             )
        )

        # ---- transpose if frequencies are in indexes
        if import_settings["layout_type"] == 1:  # 1 means "Indexes are frequencies, headers are names"
            df = df.transpose()

        # ---- validate curve and header validity
        try:
            signal_tools.check_if_sorted_and_valid(
                tuple(df.columns))  # checking headers
            df.columns = df.columns.astype(float)
        except ValueError as e:
            logger.warning("Failed to validate curve: " +
                           str(e) + "\n" + str(df))
            self.signal_table_import_fail.emit()
            return

        # ---- Validate size
        if len(df.index) < 1:
            logger.warning("Import does not have any curves to put on graph.")
            self.signal_table_import_fail.emit()
            return

        # ---- validate datatype
        try:
            df = df.astype(float)
        except ValueError as e:
            logger.warning("Cannot convert table values to float: " + str(e))
            self.signal_table_import_fail.emit()
            raise ValueError(
                "Your dataset contains values that could not be interpreted as numbers.")

        logger.info(df.info)

        # ---- put on the graph
        for name, values in df.iterrows():
            logger.debug(f"Attempting to add xy data of index {
                         name} as curve.")
            curve = signal_tools.Curve((df.columns, values))

            if settings.import_ppo > 0:
                x, y = curve.get_xy()
                x_intp, y_intp = signal_tools.interpolate_to_ppo(
                    x, y,
                    settings.import_ppo,
                    settings.interpolate_must_contain_hz,
                )
                curve.set_xy((x_intp, y_intp))

            curve.set_name_base(name)
            _ = self._add_single_curve(None, curve, update_figure=False)

        logger.info(f"Import of curves finished in {
                    (time.perf_counter()-start_time)*1000:.4g}ms")
        self.graph.update_figure()
        self.signal_table_import_successful.emit()

    def _auto_importer_status_toggle(self, checked: bool):
        if checked == 1:
            self.auto_importer = AutoImporter(self)
            self.auto_importer.signal_new_import.connect(
                self.import_single_curve)
            self.auto_importer.start()
        else:
            self.auto_importer.requestInterruption()

    def reference_curve_status_toggle(self, checked: bool):
        """
        Reference curve is marked in the Curve class instances with "_visible"
        Also in the graph object, there is an attribute to store if there is a reference and if so which one it is.
        """
        if checked:
            # Block precessing options
            indexes_and_curves = self.get_selected_curves(as_dict=True)
            if len(indexes_and_curves) == 1:
                self._interactable_widgets["processing_pushbutton"].setEnabled(
                    False)
                index, curve = list(indexes_and_curves.items())[0]

                # mark it as reference
                curve.add_name_suffix("reference")
                curve.set_reference(True)

                # Update the names in qlist widget
                reference_item = self.qlistwidget_for_curves.item(index)
                reference_item.setText(curve.get_full_name())

                # Update graph
                self.signal_toggle_reference_curve_request.emit([index, curve])

            else:
                # multiple selections
                self._interactable_widgets["set_reference_pushbutton"].setChecked(
                    False)
                self.signal_bad_beep.emit()

        elif not checked:
            # find back the reference curve
            reference_curves = [(index, curve) for index, curve in enumerate(
                self.curves) if curve.is_reference()]
            if len(reference_curves) == 0:
                pass
            elif len(reference_curves) > 1:
                raise ValueError(
                    "Multiple reference curves are in the list somehow..")
            else:
                index, curve = reference_curves[0]

                # revert it
                curve.remove_name_suffix("reference")
                curve.set_reference(False)

                # Update the names in list
                reference_item = self.qlistwidget_for_curves.item(index)
                reference_item.setText(curve.get_full_name())

                # Update graph
                self.signal_toggle_reference_curve_request.emit(None)

    def _add_single_curve(self, i_insert: int, curve: signal_tools.Curve, update_figure: bool = True,
                          line2d_kwargs={},
                          ):
        if curve.is_curve():
            i_max = len(self.curves)
            if i_insert is None or i_insert >= i_max:
                # do an add
                if not curve.has_name_prefix():
                    curve.set_name_prefix(f"#{i_max:02d}")
                self.curves.append(curve)

                list_item = qtw.QListWidgetItem(curve.get_full_name())
                if not curve.is_visible():
                    font = list_item.font()
                    font.setWeight(qtg.QFont.Thin)
                    list_item.setFont(font)
                self.qlistwidget_for_curves.addItem(list_item)

                self.graph.add_line2d(i_max, curve.get_full_name(), curve.get_xy(),
                                      update_figure=update_figure, line2d_kwargs=line2d_kwargs,
                                      )

                return i_max

            else:
                # do an insert
                curve.set_name_prefix(f"#{i_max:02d}")
                self.curves.insert(i_insert, curve)

                list_item = qtw.QListWidgetItem(curve.get_full_name())
                if not curve.is_visible():
                    font = list_item.font()
                    font.setWeight(qtg.QFont.Thin)
                    list_item.setFont(font)
                self.qlistwidget_for_curves.insertItem(i_insert, list_item)

                self.graph.add_line2d(i_insert, curve.get_full_name(), curve.get_xy(
                ), update_figure=update_figure, line2d_kwargs=line2d_kwargs)

                return i_insert
        else:
            raise ValueError("Invalid curve")

    def hide_curves(self, indexes: list = None):
        if isinstance(indexes, (list, np.ndarray)):
            indexes_and_curves = {i: self.curves[i] for i in indexes}
        elif self.return_false_and_beep_if_no_curve_selected():
            return
        else:
            indexes_and_curves = self.get_selected_curves(as_dict=True)

        for index, curve in indexes_and_curves.items():
            item = self.qlistwidget_for_curves.item(index)
            font = item.font()
            font.setWeight(qtg.QFont.Thin)
            item.setFont(font)
            curve.set_visible(False)

        self.update_visibilities_of_graph_curves(indexes_and_curves)

    def show_curves(self, indexes: list = None):
        if isinstance(indexes, (list, np.ndarray)):
            indexes_and_curves = {i: self.curves[i] for i in indexes}
        elif self.return_false_and_beep_if_no_curve_selected():
            return
        else:
            indexes_and_curves = self.get_selected_curves(as_dict=True)

        for index, curve in indexes_and_curves.items():
            item = self.qlistwidget_for_curves.item(index)
            font = item.font()
            font.setWeight(qtg.QFont.Normal)
            item.setFont(font)

            curve.set_visible(True)

        self.update_visibilities_of_graph_curves(indexes_and_curves)

    def _flash_curve(self, item: qtw.QListWidgetItem):
        index = self.qlistwidget_for_curves.row(item)
        self.signal_flash_curve_request.emit(index)

    def update_visibilities_of_graph_curves(self, indexes_and_curves=None, update_figure=True):
        if not indexes_and_curves:
            visibility_states = {i: (None, curve.is_visible())
                                 for i, curve in enumerate(self.curves)}
        else:
            visibility_states = {i: (None, curve.is_visible())
                                 for i, curve in indexes_and_curves.items()}
        self.graph.update_labels_and_visibilities(
            visibility_states, update_figure=update_figure)

    def open_processing_dialog(self):
        if self.return_false_and_beep_if_no_curve_selected():
            return

        processing_dialog = ProcessingDialog(parent=self)
        processing_dialog.signal_processing_request.connect(
            self._processing_dialog_return)
        processing_dialog.exec()

    def _processing_dialog_return(self, processing_function_name):
        results = getattr(self, processing_function_name)()
        to_beep = False

        if "to_insert" in results.keys():
            # sort the dict by highest key value first
            for i_to_insert, curves in sorted(results["to_insert"].items(), reverse=True):
                if isinstance(curves, (list, tuple)):
                    for curve in reversed(curves):
                        _ = self._add_single_curve(
                            i_to_insert, curve, update_figure=False, line2d_kwargs=results["line2d_kwargs"])
                elif isinstance(curves, signal_tools.Curve):
                    curve = curves
                    _ = self._add_single_curve(
                        i_to_insert, curve, update_figure=False, line2d_kwargs=results["line2d_kwargs"])
                else:
                    raise TypeError(
                        f"Invalid data type to insert: {type(curves)}")

            self.graph.update_figure()
            to_beep = True

        if "result_text" in results.keys():
            result_text_box = pwi.ResultTextBox(
                results["title"], results["result_text"], parent=self)
            text_width = qtg.QFontMetrics(
                result_text_box.font()).averageCharWidth()
            result_text_box.setMinimumWidth(text_width * 144)
            result_text_box.show()
            to_beep = True

        if to_beep:
            self.signal_good_beep.emit()

    def _curve_summation(self):
        selected_curves = self.get_selected_curves()
        length_curves = len(selected_curves)
        if length_curves != 2:
            raise RuntimeError(
                "Summation operations can be done only when two curves are selected.")

        curves_sum, curves_diff = signal_tools.curve_summation(selected_curves)

        representative_base_name = find_longest_match_in_name(
            [curve.get_base_name_and_suffixes() for curve in selected_curves]
        )

        for curve in (curves_sum, curves_diff):
            curve.set_name_base(representative_base_name)

        curves_sum.add_name_suffix(f"sum")
        curves_diff.add_name_suffix(f"difference")

        result_curves = []
        if settings.sum_selected:
            result_curves.append(curves_sum)
        if settings.diff_selected:
            result_curves.append(curves_diff)

        line2d_kwargs = {"color": "r", "linestyle": "--"}

        return {"to_insert": {0: result_curves}, "line2d_kwargs": line2d_kwargs}

    def _calculate_sensitivity(self):
        selected_curves = self.get_selected_curves()
        length_curves = len(selected_curves)
        if length_curves < 1:
            raise RuntimeError(
                "No curves selected.")

        f_min, f_max = settings.average_calc_f_start, settings.average_calc_f_end
        average_value = {curve.get_full_name(): signal_tools.calculate_average(curve, f_min, f_max, logarithmic=True)
                         for curve in selected_curves}

        # Build into dataframe
        df = pd.DataFrame.from_dict(average_value,
                                    orient='index',
                                    columns=["Average values"],
                                    dtype=float,
                                    )

        # ---- Generate screen text
        result_text = "-- Average value for selected curves --"
        result_text = f"Start frequency: {settings.average_calc_f_start:.5g} Hz      End frequency: {
            settings.average_calc_f_end:.5g} Hz"
        result_text += "\n\n"
        result_text += tabulate(df[["Average values"]],
                                headers=("Item name", "Average"), floatfmt=(".2f"))

        return {"title": "Average values", "result_text": result_text}

    def _add_gain(self):
        selected_curves = self.get_selected_curves()
        length_curves = len(selected_curves)
        gain_value = settings.add_gain_value
        if length_curves < 1:
            raise RuntimeError(
                "No curves selected.")

        result_curves = [deepcopy(curve) for curve in selected_curves]
        for new_curve in result_curves:
            new_curve.set_xy(
                (new_curve.get_x(), new_curve.get_y() + gain_value))
            desc_text = f"subtracted {
                -gain_value:.2f}dB" if gain_value < 0 else f"added {gain_value:.2f}dB"
            new_curve.add_name_suffix(desc_text)

        line2d_kwargs = {"color": "k", "linestyle": "-"}

        return {"to_insert": {0: result_curves}, "line2d_kwargs": line2d_kwargs}

    def _mean_and_median_analysis(self):
        selected_curves = self.get_selected_curves()
        length_curves = len(selected_curves)
        if length_curves < 2:
            raise ValueError(
                "A minimum of 2 curves is needed for this analysis.")
        curve_mean, curve_median = signal_tools.mean_and_median_of_curves(
            [curve.get_xy() for curve in selected_curves]
        )

        representative_base_name = find_longest_match_in_name(
            [curve.get_base_name_and_suffixes() for curve in selected_curves]
        )

        for curve in (curve_mean, curve_median):
            curve.set_name_base(representative_base_name)

        curve_mean.add_name_suffix(f"mean, {length_curves} curves")
        curve_median.add_name_suffix(f"median, {length_curves} curves")

        result_curves = []
        if settings.mean_selected:
            result_curves.append(curve_mean)
        if settings.median_selected:
            result_curves.append(curve_median)

        line2d_kwargs = {"color": "k"}

        return {"to_insert": {0: result_curves}, "line2d_kwargs": line2d_kwargs}

    def _outlier_detection(self):
        selected_curves = self.get_selected_curves(as_dict=True)
        length_curves = len(selected_curves)

        if length_curves < 3:
            raise ValueError(
                "A minimum of 3 curves is needed for this analysis.")

        curve_median, lower_fence, upper_fence, outlier_indexes = signal_tools.iqr_analysis(
            {i: curve.get_xy() for i, curve in selected_curves.items()},
            settings.outlier_fence_iqr,
            f_min=settings.outlier_check_start_freq,
            f_max=settings.outlier_check_end_freq
        )
        result_curves = curve_median, lower_fence, upper_fence

        representative_base_name = find_longest_match_in_name(
            [curve.get_base_name_and_suffixes()
             for curve in selected_curves.values()]
        )

        for curve in result_curves:
            curve.set_name_base(representative_base_name)
        curve_median.add_name_suffix(f"median, {length_curves} curves")
        lower_fence.add_name_suffix(
            f"-{settings.outlier_fence_iqr:.1f}xIQR, {length_curves} curves")
        upper_fence.add_name_suffix(
            f"+{settings.outlier_fence_iqr:.1f}xIQR, {length_curves} curves")

        if settings.outlier_action == "Hide" and outlier_indexes:
            self.hide_curves(indexes=outlier_indexes)
            for curve in result_curves:
                curve.add_name_suffix("calculated before hiding outliers")
        elif settings.outlier_action == "Remove" and outlier_indexes:
            self.remove_curves(indexes=outlier_indexes)
            for curve in result_curves:
                curve.add_name_suffix("calculated before removing outliers")

        line2d_kwargs = {"color": "k", "linestyle": "--"}

        return {"to_insert": {0: result_curves}, "line2d_kwargs": line2d_kwargs}

    def _show_best_fits(self):
        selected_curves = self.get_selected_curves(as_dict=True)
        if len(selected_curves) != 1:
            warning = qtw.QMessageBox(qtw.QMessageBox.Warning,
                                      "Multiple curves found in selection",
                                      "For this operation you need to choose a single curve from the list.",
                                      qtw.QMessageBox.Ok,
                                      )
            warning.exec()
            return {}

        else:
            # ---- Collect curves
            i_ref_curve, ref_curve = list(selected_curves.items())[0]
            ref_freqs, ref_curve_interpolated = signal_tools.interpolate_to_ppo(
                *ref_curve.get_xy(),
                settings.best_fit_calculation_resolution_ppo,
                settings.interpolate_must_contain_hz,
            )

            # ---- Calculate residuals squared
            residuals_squared = {curve.get_full_name():
                                 (np.interp(np.log(ref_freqs), np.log(curve.get_x()), curve.get_y(),
                                            left=np.nan, right=np.nan) - ref_curve_interpolated)**2
                                 for curve in self.curves}

            df = pd.DataFrame.from_dict(residuals_squared,
                                        orient='index',
                                        columns=ref_freqs,
                                        dtype=float,
                                        # residuals squared. table is per frequency, per speaker.
                                        )

            # ---- Apply weighting to residuals_squared
            critical_columns = [column for column in df.columns if column >=
                                settings.best_fit_critical_range_start_freq and column < settings.best_fit_critical_range_end_freq]
            if critical_columns:
                weighing_normalizer = (len(df.columns) + len(critical_columns) *
                                       (settings.best_fit_critical_range_weight - 1)) / len(df.columns)
                weighing_critical = settings.best_fit_critical_range_weight / weighing_normalizer
                df[critical_columns].apply(lambda x: x * weighing_critical)
                # residuals squared, weighted. table is per frequency, per speaker.
                df = df / weighing_normalizer

            else:
                logger.warning(
                    "Critical frequency range does not contain any of the frequency points used in best fit")

            # --- Calculate standard deviation of weighted residuals
            df.loc[:, "Unbiased variance of weighted residuals"] = df.sum(
                axis=1, skipna=True) / (len(df.columns) - 1)
            df.loc[:, "Standard deviation of weighted residuals"] = df.loc[:,
                                                                           "Unbiased variance of weighted residuals"]**0.5
            df.sort_values(
                by=["Standard deviation of weighted residuals"], ascending=True, inplace=True)

            # ---- Generate screen text
            result_text = "-- Standard deviation of weighted residual error (Swr) --"
            result_text += f"\nReference: {ref_curve.get_name_prefix(
            )}    Amount of frequency points: {len(ref_freqs)}"
            result_text += "\n\n"
            result_text += tabulate(
                df[["Standard deviation of weighted residuals"]], headers=("Item name", "Swr"))

        return {"title": "Best fits", "result_text": result_text}

    def _interpolate_curves(self):
        selected_curves = self.get_selected_curves(as_dict=True)

        result_curves = {}

        for i_curve, curve in selected_curves.items():
            xy = signal_tools.interpolate_to_ppo(
                *curve.get_xy(),
                settings.processing_interpolation_ppo,
                settings.interpolate_must_contain_hz,
            )

            new_curve = signal_tools.Curve(xy)
            new_curve.set_name_base(curve.get_name_base())
            for suffix in curve.get_name_suffixes():
                new_curve.add_name_suffix(suffix)
            new_curve.add_name_suffix(
                f"interpolated to {settings.processing_interpolation_ppo} ppo")
            result_curves[i_curve + 1] = new_curve

        line2d_kwargs = {"color": "k", "linestyle": "-"}

        return {"to_insert": result_curves, "line2d_kwargs": line2d_kwargs}

    def _smoothen_curves(self):
        selected_curves = self.get_selected_curves(as_dict=True)

        result_curves = {}

        for i_curve, curve in selected_curves.items():

            if settings.smoothing_type == "Butterworth 8th, log spaced":
                xy = signal_tools.smooth_log_spaced_curve_butterworth_fast(*curve.get_xy(),
                                                                           bandwidth=settings.smoothing_bandwidth,
                                                                           resolution=settings.smoothing_resolution_ppo,
                                                                           order=8,
                                                                           )

            elif settings.smoothing_type == "Butterworth 4th, log spaced":
                xy = signal_tools.smooth_log_spaced_curve_butterworth_fast(*curve.get_xy(),
                                                                           bandwidth=settings.smoothing_bandwidth,
                                                                           resolution=settings.smoothing_resolution_ppo,
                                                                           order=4,
                                                                           )

            elif settings.smoothing_type == "Rectangular, w/o interpolation":
                xy = signal_tools.smooth_curve_rectangular_no_interpolation(*curve.get_xy(),
                                                                            bandwidth=settings.smoothing_bandwidth,
                                                                            )

            elif settings.smoothing_type == "Gaussian, log spaced":
                xy = signal_tools.smooth_curve_gaussian(*curve.get_xy(),
                                                        bandwidth=settings.smoothing_bandwidth,
                                                        resolution=settings.smoothing_resolution_ppo,
                                                        )

            else:
                raise NotImplementedError(
                    "This smoothing type is not available")

            new_curve = signal_tools.Curve(xy)
            new_curve.set_name_base(curve.get_name_base())
            for suffix in curve.get_name_suffixes():
                new_curve.add_name_suffix(suffix)
            new_curve.add_name_suffix(
                f"smoothed 1/{settings.smoothing_bandwidth}")
            result_curves[i_curve + 1] = new_curve

        line2d_kwargs = {"color": "k", "linestyle": "-"}

        return {"to_insert": result_curves, "line2d_kwargs": line2d_kwargs}

    def open_settings_dialog(self):
        settings_dialog = SettingsDialog(parent=self)
        settings_dialog.signal_settings_changed.connect(
            self._settings_dialog_return)

        return_value = settings_dialog.exec()
        # What does it return normally?
        if return_value:
            pass

    def _settings_dialog_return(self):
        self.signal_user_settings_changed.emit()
        self.graph.update_figure(recalculate_limits=False)
        self.signal_good_beep.emit()

    def _not_implemented_popup(self):
        message_box = qtw.QMessageBox(qtw.QMessageBox.Information,
                                      "Feature not Implemented",
                                      )
        message_box.setStandardButtons(qtw.QMessageBox.Ok)
        message_box.exec()

    def open_about_menu(self):
        result_text = "\n".join([
            "Linecraft - Frequency response display and statistics tool",
            f"Version: {app_definitions['version']}",
            "",
            f"{app_definitions['copyright']}",
            f"{app_definitions['website']}",
            f"{app_definitions['email']}",
            "",
            "This program is free software: you can redistribute it and/or modify",
            "it under the terms of the GNU General Public License as published by",
            "the Free Software Foundation, either version 3 of the License, or",
            "(at your option) any later version.",
            "",
            "This program is distributed in the hope that it will be useful,",
            "but WITHOUT ANY WARRANTY; without even the implied warranty of",
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the",
            "GNU General Public License for more details.",
            "",
            "You should have received a copy of the GNU General Public License",
            "along with this program.  If not, see <https://www.gnu.org/licenses/>.",
            "",
            "This software uses Qt for Python under the GPLv3 license.",
            "https://www.qt.io/",
            "",
            "See 'requirements.txt' for an extensive list of Python libraries used.",
        ])
        text_box = pwi.ResultTextBox("About", result_text, monospace=False)
        text_box.exec()

    def get_widget_state(self):
        ax = self.graph.ax
        graph_info = {"title": ax.get_title(),
                      "xlabel": ax.get_xlabel(),
                      "ylabel": ax.get_ylabel(),
                      "xlim": ax.get_xlim(),
                      "ylim": ax.get_ylim(),
                      "xscale": ax.get_xscale(),
                      "yscale": ax.get_yscale(),
                      }

        def collect_line2d_info(line):
            line_info = {"linestyle": line.get_linestyle(),
                         "drawstyle": line.get_drawstyle(),
                         "linewidth": line.get_linewidth(),
                         "color": line.get_color(),
                         "marker": line.get_marker(),
                         "markersize": line.get_markersize(),
                         "markerfacecolor": line.get_markerfacecolor(),
                         "markeredgecolor": line.get_markeredgecolor(),
                         }
            return line_info

        def collect_curve_info(curve):
            curve_info = {"visible": curve.is_visible(),
                          "identification": curve._identification,
                          "x": tuple(curve.get_x()),
                          "y": tuple(curve.get_y()),
                          }
            return curve_info

        lines_info = []
        curves_info = []
        for line, curve in zip(self.graph.get_lines_in_user_defined_order(), self.curves):
            lines_info.append(collect_line2d_info(line))
            curves_info.append(collect_curve_info(curve))

        package = pickle.dumps(
            (graph_info, lines_info, curves_info), protocol=5)
        return package

    def set_widget_state(self, package):
        graph_info, lines_info, curves_info = pickle.loads(package)

        # ---- delete all lines first
        # self.remove_curves([*range(len(self.curves))])

        if len(self.curves) == 0:
            # ---- apply graph state
            ax = self.graph.ax
            ax.set_title(graph_info["title"])
            ax.set_xlabel(graph_info["xlabel"])
            ax.set_ylabel(graph_info["ylabel"])
            ax.set_xscale(graph_info["xscale"])
            ax.set_yscale(graph_info["yscale"])
            if "xlim" in graph_info.keys():  # added as bug fix in 0.2.4
                ax.set_xlim(graph_info["xlim"])
                ax.set_ylim(graph_info["ylim"])

        # ---- add lines
        for line_info, curve_info in zip(lines_info, curves_info):
            curve = signal_tools.Curve((curve_info["x"], curve_info["y"]))
            curve.set_visible(curve_info["visible"])
            curve._identification = curve_info["identification"]

            self._add_single_curve(
                None, curve, update_figure=False, line2d_kwargs=line_info)

        self.update_visibilities_of_graph_curves(update_figure=False)
        self.graph.update_figure(recalculate_limits=False)

    def save_state_to_file(self):
        global settings

        path_unverified = qtw.QFileDialog.getSaveFileName(self, caption='Save state to a file..',
                                                          dir=settings.last_used_folder,
                                                          filter='Linecraft files (*.lc)',
                                                          )
        # path_unverified.setDefaultSuffix("lc") not available for getSaveFileName

        try:
            file_raw = path_unverified[0]
            if file_raw:  # if we received a string
                # Filter not working as expected in nautilus. Saves files without including the extension.
                # Therefore added this seciton.
                file = Path(
                    file_raw + ".lc" if file_raw[-3:] != ".lc" else file_raw)
                assert file.parent.exists()
            else:
                return  # nothing was selected, pick file canceled
        except:
            raise NotADirectoryError(file_raw)

        settings.update("last_used_folder", str(file.parent))
        package = self.get_widget_state()
        with open(file, "wb") as f:
            f.write(package)
        self.signal_good_beep.emit()

    def pick_a_file_and_add_state_from_it(self):
        file = qtw.QFileDialog.getOpenFileName(self, caption='Get state from a save file..',
                                               dir=settings.last_used_folder,
                                               filter='Linecraft files (*.lc)',
                                               )[0]
        if file:
            self.add_state_from_file(file)
        else:
            pass  # canceled file select

    def add_state_from_file(self, file: (str, Path)):

        try:
            my_file = Path(file)
        except TypeError as e:
            raise TypeError(f"Unable to convert argument '{
                            file}' into a file path. Error: {e}")

        if not my_file.is_file():
            raise FileNotFoundError(file)

        settings.update("last_used_folder", str(my_file.parent))
        with open(my_file, "rb") as f:
            self.set_widget_state(f.read())
        self.signal_good_beep.emit()


class ProcessingDialog(qtw.QDialog):
    global settings
    signal_processing_request = qtc.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowModality(qtc.Qt.WindowModality.ApplicationModal)
        self.setWindowTitle("Processing Menu")
        self.setLayout(qtw.QVBoxLayout())
        self.tab_widget = qtw.QTabWidget(
            tabPosition=qtw.QTabWidget.TabPosition.North)
        text_width = qtg.QFontMetrics(self.font()).averageCharWidth()
        # self.tab_widget.setMinimumWidth(text_width * 36)
        self.layout().addWidget(self.tab_widget)

        class TabTitle(qtw.QLabel):
            def __init__(self, text: str):
                super().__init__()
                self.setText(text)
                self.setStyleSheet("font-weight: bold")
                self.setAlignment(qtg.Qt.AlignmentFlag.AlignLeft)

        # dict of tuples. key is index of tab. value is a tuple(UserForm, processing_function_name)
        self.user_forms_and_recipient_functions = {}

        # ---- Statistics page
        user_form_0 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_0, "Statistics")
        i = self.tab_widget.indexOf(user_form_0)
        self.user_forms_and_recipient_functions[i] = (
            user_form_0, "_mean_and_median_analysis")

        user_form_0.add_row(TabTitle("Statistics"))
        user_form_0.add_row(qtw.QLabel(
            "Select multiple curves before proceeding."))

        user_form_0.add_row(pwi.CheckBox("mean_selected",
                                         "Returns a curve showing the mean value of level in dB."
                                         "Preferred method of estimating representtive curve when sample population is small and symmetrically distributed.",
                                         ),
                            "Calculate mean",
                            )

        user_form_0.add_row(pwi.CheckBox("median_selected",
                                         "Returns a curve showing the median value per frequency point."
                                         "Preferred method of estimating representtive curve when sample population is large and/or skewed.",
                                         ),
                            "Calculate median",
                            )

        # ---- Smoothing page
        user_form_1 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_1, "Smoothing")
        i = self.tab_widget.indexOf(user_form_1)
        self.user_forms_and_recipient_functions[i] = (
            user_form_1, "_smoothen_curves")

        user_form_1.add_row(TabTitle("Smoothing"))

        user_form_1.add_row(pwi.ComboBox("smoothing_type",
                                         None,
                                         [("Butterworth 8th, log spaced",),
                                          ("Butterworth 4th, log spaced",),
                                          ("Rectangular, w/o interpolation",),
                                          ("Gaussian, log spaced",),
                                          ]
                                         ),
                            "Type",
                            )
        # user_form_1.interactable_widgets["smoothing_type"].model().item(1).setEnabled(False)  # disable Klippel

        user_form_1.add_row(pwi.IntSpinBox("smoothing_resolution_ppo",
                                           "Parts per octave resolution for the operation",
                                           min_max=(1, 99999),
                                           ),
                            "Resolution (ppo)",
                            )
        user_form_1.add_row(pwi.IntSpinBox("smoothing_bandwidth",
                                           "Width of the frequency band in 1/octave."
                                           "\nFor Gaussion, bandwidth defines 2x the standard deviation of distribution."
                                           "\nFor Butterworth, bandwidth is the distance between critical frequencies, i.e. -3dB points for a first order filter.",
                                           min_max=(1, 99999),
                                           ),
                            "Bandwidth (1/octave)",
                            )

        # Disable the resolution spin box if smoothing type is rectangular.
        user_form_1.interactable_widgets["smoothing_type"].currentIndexChanged.connect(
            lambda x: user_form_1.interactable_widgets["smoothing_resolution_ppo"].setEnabled(
                x != 2)
        )

        # ---- Outlier detection page
        user_form_2 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_2, "Outliers")
        i = self.tab_widget.indexOf(user_form_2)
        self.user_forms_and_recipient_functions[i] = (
            user_form_2, "_outlier_detection")

        user_form_2.add_row(TabTitle("Outlier Detection"))

        user_form_2.add_row(pwi.FloatSpinBox("outlier_fence_iqr",
                                             "Fence post for outlier detection using IQR method. Unit is the interquartile range for given frequency."
                                             "Often the value 1.5 is used.",
                                             decimals=1,
                                             min_max=(0.1, 999.9),
                                             ),
                            "Outlier fence (IQR)",
                            )

        user_form_2.add_row(pwi.IntSpinBox("outlier_check_start_freq",
                                           "Lowest frequency to include for outlier calculation."),
                            "Lowest frequency (Hz)",
                            )

        user_form_2.add_row(pwi.IntSpinBox("outlier_check_end_freq",
                                           "Highest frequency to include for outlier calculation."),
                            "Highest frequency (Hz)",
                            )

        user_form_2.add_row(pwi.ComboBox("outlier_action",
                                         "Action to carry out on curves that fall partly or fully outside the fence.",
                                         [("None",),
                                          ("Hide",),
                                          ("Remove",),
                                          ]
                                         ),
                            "Action on outliers",
                            )

        # ---- Interpolation page
        user_form_3 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_3, "Interpolation")
        i = self.tab_widget.indexOf(user_form_3)
        self.user_forms_and_recipient_functions[i] = (
            user_form_3, "_interpolate_curves")

        user_form_3.add_row(TabTitle("Interpolation"))
        user_form_3.add_row(qtw.QLabel(
            "Interpolate selected curves to new octavely spaced points."))
        user_form_3.add_row(pwi.IntSpinBox("processing_interpolation_ppo",
                                           None,
                                           min_max=(1, 99999),
                                           ),
                            "Points per octave",
                            )

        # ---- Show best fits
        user_form_4 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_4, "Best fit")
        i = self.tab_widget.indexOf(user_form_4)
        self.user_forms_and_recipient_functions[i] = (
            user_form_4, "_show_best_fits")

        user_form_4.add_row(TabTitle("Best fit to current"))
        user_form_4.add_row(qtw.QLabel(
            "Find the best fit to the selected curve."))

        user_form_4.add_row(pwi.IntSpinBox("best_fit_calculation_resolution_ppo",
                                           "How many calculation points per octave to use for the calculation"
                                           " of the differences between the reference curve and the candidates."),
                            "Resolution (ppo)",
                            )

        user_form_4.add_row(pwi.IntSpinBox("best_fit_critical_range_start_freq",
                                           "Start frequency for range where weighing will be applied."),
                            "Critical range start (Hz)",
                            )

        user_form_4.add_row(pwi.IntSpinBox("best_fit_critical_range_end_freq",
                                           "End frequency for range where weighing will be applied."),
                            "Critical range end (Hz)",
                            )

        user_form_4.add_row(pwi.IntSpinBox("best_fit_critical_range_weight",
                                           "Multiplier to increase the weighting of the selected frequency range."
                                           "Setting to 1 means there will be no weighting."
                                           "Setting to 0 means the range will not be considered in the calculation"),
                            "Critical range weight",
                            )

        # ---- Summation page
        user_form_5 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_5, "Summation")
        i = self.tab_widget.indexOf(user_form_5)
        self.user_forms_and_recipient_functions[i] = (
            user_form_5, "_curve_summation")

        user_form_5.add_row(TabTitle("Summation"))
        user_form_5.add_row(qtw.QLabel(
            "Calculate the sum of or the difference between two selected curves."))

        user_form_5.add_row(pwi.CheckBox("sum_selected",
                                         "Returns the sum of the curves. Curves will be interpolated to all the frequency points provided in either of the curves."
                                         ),
                            "Summation",
                            )

        user_form_5.add_row(pwi.CheckBox("diff_selected",
                                         "Returns the distance between the two curves."
                                         " Curves will be interpolated to all the frequency points provided in either of the curves."
                                         ),
                            "Difference",
                            )

        # ---- Sensitivity page
        user_form_6 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_6, "Average value")
        i = self.tab_widget.indexOf(user_form_6)
        self.user_forms_and_recipient_functions[i] = (
            user_form_6, "_calculate_sensitivity")

        user_form_6.add_row(TabTitle("Average value (sensitivity)"))
        user_form_6.add_row(qtw.QLabel(
            "Calculate average value in given frequency range."))

        user_form_6.add_row(pwi.FloatSpinBox("average_calc_f_start",
                                             "Starting frequency for average value calculation.",
                                             decimals=1,
                                             ),
                            "Start frequency (Hz)",
                            )
        user_form_6.add_row(pwi.FloatSpinBox("average_calc_f_end",
                                             "End frequency for average value calculation.",
                                             decimals=1,
                                             ),
                            "End frequency (Hz)",
                            )

        # ---- Gain page
        user_form_7 = pwi.UserForm()
        # tab page is the UserForm widget
        self.tab_widget.addTab(user_form_7, "Gain")
        i = self.tab_widget.indexOf(user_form_7)
        self.user_forms_and_recipient_functions[i] = (
            user_form_7, "_add_gain")

        user_form_7.add_row(TabTitle("Gain"))
        user_form_7.add_row(qtw.QLabel(
            "Shift selected curves by this value in y axis."))

        user_form_7.add_row(pwi.FloatSpinBox("add_gain_value",
                                             "Shift the curve by this value.",
                                             min_max=(-999.99, 999.99),
                                             ),
                            "Value")

        # ---- Common buttons for the dialog
        button_group = pwi.PushButtonGroup({"run": "Run",
                                            "cancel": "Cancel",
                                            },
                                           {},
                                           )
        button_group.buttons()["run_pushbutton"].setDefault(True)
        self.layout().addWidget(button_group)

        # ---- Update parameters from settings
        self.tab_widget.setCurrentIndex(settings.processing_selected_tab)
        for i in range(self.tab_widget.count()):
            user_form = self.tab_widget.widget(i)
            for key, widget in user_form.interactable_widgets.items():
                saved_setting = getattr(settings, key)
                if isinstance(widget, qtw.QCheckBox):
                    widget.setChecked(saved_setting)
                elif isinstance(widget, qtw.QComboBox):
                    widget.setCurrentText(saved_setting)
                else:
                    widget.setValue(saved_setting)

        # ---- Connections
        button_group.buttons()["cancel_pushbutton"].clicked.connect(
            self.reject)
        button_group.buttons()["run_pushbutton"].clicked.connect(
            self._save_and_close)

    def _save_and_close(self):
        active_tab_index = self.tab_widget.currentIndex()
        user_form, processing_function_name = self.user_forms_and_recipient_functions[
            active_tab_index]
        settings.update("processing_selected_tab",
                        self.tab_widget.currentIndex())

        for key, widget in user_form.interactable_widgets.items():
            if isinstance(widget, qtw.QCheckBox):
                settings.update(key, widget.isChecked())
            elif isinstance(widget, qtw.QComboBox):
                settings.update(key, widget.currentText())
            else:
                settings.update(key, widget.value())

        self.setWindowTitle("Calculating...")
        self.setEnabled(False)  # calculating
        self.repaint()
        self.signal_processing_request.emit(processing_function_name)
        self.accept()


class ImportDialog(qtw.QDialog):
    global settings
    signal_import_table_request = qtc.Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # self.setWindowModality(qtc.Qt.WindowModality.ApplicationModal)
        self.setLayout(qtw.QVBoxLayout())
        self.setWindowTitle("Import table with curve(s)")

        # ---- Form
        user_form = pwi.UserForm()
        self.layout().addWidget(user_form)

        user_form.add_row(pwi.ComboBox("import_table_layout_type",
                                       "Choose how the data is laid out in the raw imported data.",
                                       [("Headers are frequencies, indexes are names", 0),
                                        ("Indexes are frequencies, headers are names", 1),
                                        ],
                                       ),
                          "Layout type",
                          )

        user_form.add_row(pwi.IntSpinBox("import_table_no_line_headers",
                                         "Which line in the imported data contains the headers of the table."
                                         "\nHeaders correspond to column names in a spreadsheet; "
                                         "'1' means column A, '2' means column B and so on."
                                         "\n'0' means there is no header column in the import data."),
                          "Line number of headers",
                          )

        user_form.add_row(pwi.IntSpinBox("import_table_no_columns",
                                         "Which column in the imported data are the indexes."
                                         "\nIndexes correspond to row names in a spreadsheet."
                                         "\n'0' means there is no index column in the import data."),
                          "Column number of indexes",
                          )

        user_form.add_row(pwi.ComboBox("import_table_delimiter",
                                       "Delimiter character that separates the data into columns.",
                                       [(", (comma)", ","),
                                        ("; (semi-colon)", ";"),
                                        ("Tab", "\t"),
                                        ("Space", " "),
                                        ],
                                       ),
                          "Delimiter",
                          )

        user_form.add_row(pwi.ComboBox("import_table_decimal_separator",
                                       "Decimal separator. '.' as default."
                                       "Europe should use ',' officially but scientific community sticks to '.' as far as I understand.",
                                       [(". (dot)", "."),
                                        (", (comma)", ","),
                                        ],
                                       ),
                          "Decimal separator",
                          )

        # ---- Buttons
        button_group = pwi.PushButtonGroup({"open_file": "Open file..",
                                            "read_clipboard": "Read clipboard",
                                            "close": "Close",
                                            },
                                           {},
                                           )
        button_group.buttons()["open_file_pushbutton"].setDefault(True)
        self.layout().addWidget(button_group)

        # read values from settings
        values_new = {}
        for key, widget in user_form.interactable_widgets.items():
            if isinstance(widget, qtw.QComboBox):
                values_new[key] = {"current_text": getattr(settings, key)}
            else:
                values_new[key] = getattr(settings, key)
        user_form.update_form_values(values_new)

        # Connections
        button_group.buttons()["close_pushbutton"].clicked.connect(self.reject)
        button_group.buttons()["open_file_pushbutton"].clicked.connect(
            partial(self._import_requested, "file", user_form))
        button_group.buttons()["read_clipboard_pushbutton"].clicked.connect(
            partial(self._import_requested, "clipboard", user_form))

    def _save_form_values_to_settings(self, user_form: pwi.UserForm):
        values = user_form.get_form_values()
        for widget_name, value in values.items():
            if isinstance(value, dict) and "current_text" in value.keys():  # if a qcombobox
                settings.update(widget_name, value["current_text"])
            else:
                settings.update(widget_name, value)

    @qtc.Slot()
    def deactivate(self):
        self.setWindowTitle("Importing...")
        self.setEnabled(False)
        self.repaint()

    @qtc.Slot()
    def reactivate(self):
        self.setWindowTitle("Import table with curve(s)")
        self.setEnabled(True)
        self.repaint()

    def _import_requested(self, source, user_form: pwi.UserForm):
        # Pass to easier names
        form_values = user_form.get_form_values()
        
        vals = {
            "no_header": form_values["import_table_no_line_headers"],
            "no_index": form_values["import_table_no_columns"],
            "layout_type": form_values["import_table_layout_type"]["current_data"],
            "delimiter": form_values["import_table_delimiter"]["current_data"],
            "decimal_separator": form_values["import_table_decimal_separator"]["current_data"],
            }
        
        # Do validations
        if vals["decimal_separator"] == vals["delimiter"]:
            raise ValueError(
                "Cannot have the same character for delimiter and decimal separator.")
        elif vals["layout_type"] == 0 and vals["no_header"] == 0:
            raise ValueError("Header line cannot be zero. Since you have selected"
                             " headers as frequencies, there needs to be a line for headers.")
        elif vals["layout_type"] == 1 and vals["no_index"] == 0:
            raise ValueError("Index column cannot be zero. Since you have selected"
                             " indexes as frequencies, there needs to be a column for indexes.")
        else:
            # Validations passed. Save settings.
            self._save_form_values_to_settings(user_form)

        try:
            self.signal_import_table_request.emit(source, vals)
        except:
            self.signal_table_import_fail.emit()


class SettingsDialog(qtw.QDialog):
    global settings
    signal_settings_changed = qtc.Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowModality(qtc.Qt.WindowModality.ApplicationModal)
        self.setLayout(qtw.QVBoxLayout())

        # ---- Form
        user_form = pwi.UserForm()
        self.layout().addWidget(user_form)

        user_form.add_row(pwi.CheckBox("show_legend", "Show legend on the graph"),
                          "Show legend")

        user_form.add_row(pwi.IntSpinBox("max_legend_size", "Limit the items that can be listed on the legend. Does not affect the shown curves in graph"),
                          "Nmax for graph legend")

        mpl_styles = [
            style_name for style_name in mpl.style.available if style_name[0] != "_"]
        user_form.add_row(pwi.ComboBox("matplotlib_style",
                                       "Style for the canvas. To see options, web search: 'matplotlib style sheets reference'",
                                       [(style_name, None)
                                        for style_name in mpl_styles],
                                       ),
                          "Matplotlib style",
                          )

        user_form.add_row(pwi.ComboBox("graph_grids",
                                       None,
                                       [("Style default", "default"),
                                        ("Major only", "major only"),
                                        ("Major and minor", "major and minor"),
                                        ],
                                       ),
                          "Graph grid view",
                          )

        user_form.add_row(pwi.SunkenLine())

        user_form.add_row(pwi.IntSpinBox("import_ppo",
                                         "Interpolate the curve to here defined points per octave in import"
                                         "\nThis is used to simplify curves with too many points, such as Klippel graph imports."
                                         "\nSet to '0' to do no modification to curve."
                                         "\nDefault value: 384",
                                         ),
                          "Interpolate during import (ppo)",
                          )

        user_form.add_row(pwi.IntSpinBox("export_ppo",
                                         "Interpolate the curve to here defined points per octave while exporting"
                                         "\nThis is used to simplify curves with too many points, such as Klippel graph imports."
                                         "\nSet to '0' to do no modifications to curve."
                                         "\nDefault value: 96",
                                         ),
                          "Interpolate before export (ppo)",
                          )

        user_form.add_row(pwi.IntSpinBox("interpolate_must_contain_hz",
                                         "Frequency that will always be a point within interpolated frequency array."
                                         "\nDefault value: 1000",
                                         min_max=(1, 999999),
                                         ),
                          "Interpolate must contain frequency (Hz)",
                          )

        user_form.add_row(pwi.SunkenLine())

        user_form.add_row(pwi.FloatSpinBox("A_beep",
                                           "Amplitude of the beep. Not in dB. 0 is off, 1 is maximum amplitude",
                                           min_max=(0, 1),
                                           ),
                          "Beep amplitude",
                          )

        # ---- Buttons
        button_group = pwi.PushButtonGroup({"save": "Save",
                                            "cancel": "Cancel",
                                            },
                                           {},
                                           )
        button_group.buttons()["save_pushbutton"].setDefault(True)
        self.layout().addWidget(button_group)

        # ---- read values from settings
        values_from_settings = {}
        for key, widget in user_form.interactable_widgets.items():
            if isinstance(widget, qtw.QComboBox):
                values_from_settings[key] = {"current_text": getattr(settings, key)}
            else:
                values_from_settings[key] = getattr(settings, key)
        user_form.update_form_values(values_from_settings)

        # Connections
        button_group.buttons()["cancel_pushbutton"].clicked.connect(
            self.reject)
        button_group.buttons()["save_pushbutton"].clicked.connect(
            partial(self._save_and_close,  user_form))

    def _save_and_close(self, user_form):
        vals = user_form.get_form_values()
        if vals["matplotlib_style"]["current_text"] != settings.matplotlib_style or vals["graph_grids"]["current_text"] != settings.graph_grids:
            message_box = qtw.QMessageBox(qtw.QMessageBox.Information,
                                          "Information",
                                          "Application needs to be restarted to be able to use the new graph settings.",
                                          )
            message_box.setStandardButtons(
                qtw.QMessageBox.Cancel | qtw.QMessageBox.Ok)
            returned = message_box.exec()

            if returned == qtw.QMessageBox.Cancel:
                return
        
        for widget_name, value in vals.items():
            if isinstance(value, dict) and "current_text" in value.keys():  # if a qcombobox
                settings.update(widget_name, value["current_text"])
            else:
                settings.update(widget_name, value)
        self.signal_settings_changed.emit()
        self.accept()


class AutoImporter(qtc.QThread):
    signal_new_import = qtc.Signal(signal_tools.Curve)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        while not self.isInterruptionRequested():
            try:
                cb_data = pyperclip.waitForNewPaste(1)
                # print("\nClipboard read:" + "\n" + str(type(cb_data)) + "\n" + cb_data)
                new_curve = signal_tools.Curve(cb_data)
                if new_curve.is_curve():
                    self.signal_new_import.emit(new_curve)
            except pyperclip.PyperclipTimeoutException:
                pass
            except Exception as e:
                logger.warning(e)


def parse_args(app_definitions):
    import argparse

    description = (
        f"{app_definitions['app_name']} - {app_definitions['copyright']}"
        "\nThis program comes with ABSOLUTELY NO WARRANTY"
        "\nThis is free software, and you are welcome to redistribute it"
        "\nunder certain conditions. See LICENSE file for more details."
    )

    parser = argparse.ArgumentParser(prog="python main.py",
                                     description=description,
                                     epilog={app_definitions['website']},
                                     )
    parser.add_argument('infile', nargs="?", type=Path,
                        help="Path to a '*.lc' file. This will open a saved state.")
    parser.add_argument('-d', '--loglevel', nargs="?",
                        choices=["debug", "info",
                                 "warning", "error", "critical"],
                        help="Set logging level for Python logging. Valid values are debug, info, warning, error and critical.")

    return parser.parse_args()


def create_sound_engine(app):
    sound_engine = pwi.SoundEngine(settings)
    sound_engine_thread = qtc.QThread()
    sound_engine.moveToThread(sound_engine_thread)

    # Connect
    app.aboutToQuit.connect(sound_engine.release_all)
    app.aboutToQuit.connect(sound_engine_thread.quit)

    sound_engine_thread.start(qtc.QThread.HighPriority)

    return sound_engine, sound_engine_thread


def setup_logging(level: str = "warning", args=None):
    if args and args.loglevel:
        log_level = getattr(logging, args.loglevel.upper())
    else:
        log_level = level.upper()

    log_filename = Path.home().joinpath(
        f".{app_definitions['app_name'].lower()}.log")

    file_handler = logging.FileHandler(filename=log_filename)
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    handlers = [file_handler, stdout_handler]

    logging.basicConfig(handlers=handlers,
                        level=log_level,
                        format="%(asctime)s %(levelname)s - %(funcName)s: %(message)s",
                        force=True,
                        )
    # had to force this
    # https://stackoverflow.com/questions/30861524/logging-basicconfig-not-creating-log-file-when-i-run-in-pycharm
    logger = logging.getLogger()
    logger.info(
        f"{time.strftime('%c')} - Started logging with log level {log_level}.")

    return logger


def main():
    global settings, app_definition, logger, create_sound_engine

    args = parse_args(app_definitions)
    logger = setup_logging(args=args)
    settings = Settings(app_definitions["app_name"])

    # ---- Create QApplication
    if not (app := qtw.QApplication.instance()):
        app = qtw.QApplication(sys.argv)
        # there is a new recommendation with qApp but how to do the sys.argv with that?
        # app.setQuitOnLastWindowClosed(True)  # is this necessary??
        app.setWindowIcon(qtg.QIcon(app_definitions["icon_path"]))

    # ---- Catch exceptions and handle with pop-up widget
    error_handler = pwi.ErrorHandlerUser(app, logger)
    sys.excepthook = error_handler.excepthook

    # ---- Create sound engine
    sound_engine, sound_engine_thread = create_sound_engine(app)

    # ---- Create main window
    mw = CurveAnalyze()
    mw.signal_bad_beep.connect(sound_engine.bad_beep)
    mw.signal_good_beep.connect(sound_engine.good_beep)

    # ---- Are we loading a state file?
    if args.infile:
        logger.info(
            f"Starting application with argument infile: {args.infile}")
        mw.add_state_from_file(args.infile)

    # --- Go
    mw.show()
    app.exec()


if __name__ == "__main__":
    main()
