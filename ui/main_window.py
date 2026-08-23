import logging
import pickle
import time
from copy import deepcopy
from functools import partial
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import pyperclip
from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw
from PySide6.QtWidgets import QListWidgetItem
from tabulate import tabulate

from config.app_config import APP_DEFINITIONS
from generictools import signal_tools
from generictools.graphing_widget import MatplotlibWidget
from generictools.settings import singleton_settings
import generictools.personalized_widgets as pwi
from ui.dialogs import AutoImporter, ImportDialog, ProcessingDialog, SettingsDialog
from utils import find_longest_match_in_name

app_settings = singleton_settings()
app_definitions = APP_DEFINITIONS
logger = logging.getLogger(__name__)


class CurveAnalyze(qtw.QMainWindow):

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

    signal_reference_curve_activate = qtc.Signal(int)
    signal_reference_curve_deactivate = qtc.Signal(int)
    signal_reference_curve_successful = qtc.Signal(int)

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
        if keyEvent.matches(qtg.QKeySequence.Paste):
            self.import_single_curve()
        if keyEvent.matches(qtg.QKeySequence.Copy):
            self._export_curve()

    # View menu "y axis limits" options -> generictools.graphing_widget policy name.
    # "Freeze" needs the graph's current ylim as kwargs, so picking it from the menu
    # is handled separately -- see _y_limits_menu_action_triggered.
    _Y_LIMITS_POLICY_BY_MENU_TEXT = {
        "Default": None,
        "SPL optimized": "SPL",
        "THD/Impedance optimized": "impedance",
        "Freeze": "fixed",
    }
    _Y_LIMITS_MENU_TEXT_BY_POLICY = {
        policy: text for text, policy in _Y_LIMITS_POLICY_BY_MENU_TEXT.items()}
    # What the application starts with, unless something else picks a policy later.
    _Y_LIMITS_DEFAULT_MENU_TEXT = "Default"

    def _create_core_objects(self):
        # a dictionary of QWidgets that users interact with
        self._interactable_widgets = dict()
        # frequency response curves. THIS IS THE SINGLE SOURCE OF TRUTH FOR CURVE DATA.
        self.curves = []
        # (policy_name, kwargs) requested via the View menu, applied to the graph
        # immediately. The menu is disabled while a reference curve is active, since
        # that overrides the policy until it is deactivated.
        self._y_limits_policy_selection = (
            self._Y_LIMITS_POLICY_BY_MENU_TEXT[self._Y_LIMITS_DEFAULT_MENU_TEXT], {})

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

        view_menu = menu_bar.addMenu("View")
        view_menu.addSection("y axis limits")
        self.y_limits_action_group = qtg.QActionGroup(self)
        self.y_limits_action_group.setExclusive(True)
        self._y_limits_actions = {}
        for text in ("Default",
                     "SPL optimized",
                     "THD/Impedance optimized",
                     "Freeze",
                     ):
            action = view_menu.addAction(text)
            action.setCheckable(True)
            self.y_limits_action_group.addAction(action)
            self._y_limits_actions[text] = action
        # Reflect the policy the graph starts with (applied in _create_widgets) without
        # triggering it -- setChecked() does not emit triggered().
        self._y_limits_actions[self._Y_LIMITS_DEFAULT_MENU_TEXT].setChecked(True)

        help_menu = menu_bar.addMenu("Help")
        about_action = help_menu.addAction("About", self.open_about_menu)

    def _create_widgets(self):
        # ---- Create graph and buttons widget
        self.graph = MatplotlibWidget(layout_engine="tight")
        policy_name, policy_kwargs = self._y_limits_policy_selection
        self.graph.set_y_limits_policy(policy_name, **policy_kwargs)
        self.graph_buttons = pwi.PushButtonGroup(
            {
                "import_curve": "Import curve",
                "import_table": "Import table",
                # "auto_import": "Auto import",
                "reset_indexes": "Reset indexes",
                "reset_colors": "Reset colors",
                "remove": "| Remove |",
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
             # "auto_import": "Attempt an import whenever new data is found on the clipboard.",
             },
        )

        # Create a palette
        palette = qtg.QPalette()

        # Set the button text color to red
        palette.setColor(qtg.QPalette.ButtonText, qtg.QColor(190, 70, 70))

        # Apply the palette to the button
        self.graph_buttons.buttons()["remove_pushbutton"].setPalette(palette)

        # Add the widgets that users interact with into the dictionary
        self.graph_buttons.add_elements_to_dict(self._interactable_widgets)

        # ---- Set types and states for buttons
        # self._interactable_widgets["auto_import_pushbutton"].setCheckable(True)
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
        # self._interactable_widgets["auto_import_pushbutton"].toggled.connect(
        #     self._auto_importer_status_toggle)
        self._interactable_widgets["set_reference_pushbutton"].toggled.connect(
            self.reference_curve_button_toggled)
        self._interactable_widgets["processing_pushbutton"].clicked.connect(
            self.open_processing_dialog)
        self._interactable_widgets["import_curve_pushbutton"].clicked.connect(
            self.import_single_curve)
        self._interactable_widgets["import_table_pushbutton"].clicked.connect(
            self._import_table_clicked)

        # ---- Double click for highlighting a curve
        self.qlistwidget_for_curves.itemActivated.connect(self.toggle_highlight)

        # ---- View menu: y axis limits
        # A lambda is used instead of functools.partial: PySide6 does not always
        # unwrap partial objects when matching the triggered(bool) signal, which
        # silently drops the "checked" argument.
        for text, action in self._y_limits_actions.items():
            action.triggered.connect(
                lambda checked, menu_text=text: self._y_limits_menu_action_triggered(menu_text, checked))

        # ---- Signals to Matplolib graph
        self.signal_reposition_curves_request.connect(
            self.graph.change_lines_order)
        self.signal_update_labels_request.connect(
            self.graph.update_labels_and_visibilities)
        self.signal_reset_colors_request.connect(self.graph.reset_colors)
        self.signal_remove_curves_request.connect(
            self.graph.remove_multiple_line2d)

        self.signal_reference_curve_activate.connect(
            self.graph.activate_reference_curve)
        self.signal_reference_curve_deactivate.connect(
            self.graph.deactivate_reference_curve)
        # self.signal_add_line_request.connect(self.graph.add_line2d)
        # self.signal_update_visibility_request.connect(self.graph.update_labels_and_visibilities)

        # ---- Signals from Matplotlib graph
        self.graph.signal_good_beep.connect(self.signal_good_beep)
        self.graph.signal_bad_beep.connect(self.signal_bad_beep)

        # Reference curve
        # activated
        self.graph.signal_reference_curve_activated.connect(
            lambda: self._interactable_widgets["set_reference_pushbutton"].setChecked(True))
        self.graph.signal_reference_curve_activated.connect(
            lambda: self._interactable_widgets["processing_pushbutton"].setEnabled(False))
        self.graph.signal_reference_curve_activated.connect(
            lambda: self._interactable_widgets["export_curve_pushbutton"].setEnabled(False))
        # A reference curve overrides the y-limits policy while active; disable the
        # menu so it can't be changed to something that won't take effect.
        self.graph.signal_reference_curve_activated.connect(
            lambda: self.y_limits_action_group.setEnabled(False))
        # self.graph.signal_reference_curve_activated.connect(
        #     lambda: self._interactable_widgets["move_up_pushbutton"].setEnabled(False))
        # self.graph.signal_reference_curve_activated.connect(
        #     lambda: self._interactable_widgets["move_to_top_pushbutton"].setEnabled(False))
        # self.graph.signal_reference_curve_activated.connect(
        #     lambda: self._interactable_widgets["reset_indexes_pushbutton"].setEnabled(False))
        # self.graph.signal_reference_curve_activated.connect(
        #     lambda: self._interactable_widgets["reset_colors_pushbutton"].setEnabled(False))
        self.graph.signal_reference_curve_activated.connect(
            self.reference_curve_activate_successful_actions)


        # deactivated
        self.graph.signal_reference_curve_deactivated.connect(
            lambda: self._interactable_widgets["set_reference_pushbutton"].setChecked(False))
        self.graph.signal_reference_curve_deactivated.connect(
            lambda: self._interactable_widgets["processing_pushbutton"].setEnabled(True))
        self.graph.signal_reference_curve_deactivated.connect(
            lambda: self._interactable_widgets["export_curve_pushbutton"].setEnabled(True))
        self.graph.signal_reference_curve_deactivated.connect(
            lambda: self.y_limits_action_group.setEnabled(True))
        # self.graph.signal_reference_curve_deactivated.connect(
        #     lambda: self._interactable_widgets["move_up_pushbutton"].setEnabled(True))
        # self.graph.signal_reference_curve_deactivated.connect(
        #     lambda: self._interactable_widgets["move_to_top_pushbutton"].setEnabled(True))
        # self.graph.signal_reference_curve_deactivated.connect(
        #     lambda: self._interactable_widgets["reset_indexes_pushbutton"].setEnabled(True))
        # self.graph.signal_reference_curve_deactivated.connect(
        #     lambda: self._interactable_widgets["reset_colors_pushbutton"].setEnabled(True))
        self.graph.signal_reference_curve_deactivated.connect(
            self.reference_curve_deactivated_actions)
        # No need to re-apply the menu selection here: the graph restores the policy
        # the reference curve was overriding, which is the one this menu last set.

        # failed
        self.graph.signal_reference_curve_failed.connect(
            lambda: self._interactable_widgets["set_reference_pushbutton"].setChecked(False))
        self.graph.signal_reference_curve_failed.connect(
            lambda: self._interactable_widgets["processing_pushbutton"].setEnabled(True))
        self.graph.signal_reference_curve_failed.connect(
            lambda: self._interactable_widgets["export_curve_pushbutton"].setEnabled(True))
        self.graph.signal_reference_curve_failed.connect(
            lambda: self.y_limits_action_group.setEnabled(True))
        # self.graph.signal_reference_curve_failed.connect(
        #     lambda: self._interactable_widgets["move_up_pushbutton"].setEnabled(True))
        # self.graph.signal_reference_curve_failed.connect(
        #     lambda: self._interactable_widgets["move_to_top_pushbutton"].setEnabled(True))
        # self.graph.signal_reference_curve_failed.connect(
        #     lambda: self._interactable_widgets["reset_indexes_pushbutton"].setEnabled(True))
        # self.graph.signal_reference_curve_failed.connect(
        #     lambda: self._interactable_widgets["reset_colors_pushbutton"].setEnabled(True))
        self.graph.signal_reference_curve_failed.connect(self.signal_bad_beep)
        self.graph.signal_reference_curve_failed.connect(lambda x: pwi.ErrorPopup(self, x))

        # Import table dialog good/bad beeps
        self.signal_table_import_successful.connect(self.signal_good_beep)
        self.signal_table_import_fail.connect(self.signal_bad_beep)

    def _export_curve(self):
        """Paste selected curve(s) to clipboard in a table."""
        if self.return_false_and_beep_if_no_curve_selected():
            return
        elif len(self.qlistwidget_for_curves.selectedItems()) > 1:
            error_message = "Can only export one curve at a time."
            pwi.ErrorPopup(self, error_message)
        else:
            curve = self.get_selected_curves()[0]
            curve.export_to_clipboard(ppo=app_settings.get_value("export_ppo"),
                                      must_include_freq=app_settings.get_value("interpolate_must_contain_hz"),
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
                self.set_qitem_font(new_list_item, "thin")
            if curve.is_highlighted():
                self.set_qitem_font(new_list_item, "bold")

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
        # if any([self.curves[index].is_reference() for index in selected_indexes]):
        #     pwi.ErrorPopup(self, "Cannot move active reference curve.")
        #     return

        i_insert = max(0, selected_indexes[0] - 1)
        self._move_curve_up(i_insert)
        if len(selected_indexes) == 1:
            self.qlistwidget_for_curves.setCurrentRow(i_insert)

    def move_to_top(self):
        if self.return_false_and_beep_if_no_curve_selected():
            return

        # selected_indexes = self.get_selected_curve_indexes()
        # if any([self.curves[index].is_reference() for index in selected_indexes]):
        #     pwi.ErrorPopup(self, "Cannot move active reference curve.")
        #     return

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
                new_labels[i] = (curve.get_full_name(), curve.is_visible(), curve.is_highlighted(), curve.is_reference())

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
                new_labels[index] = (curve.get_full_name(), curve.is_visible(), curve.is_highlighted(), curve.is_reference())

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
            new_labels[index] = (curve.get_full_name(), curve.is_visible(), curve.is_highlighted(), curve.is_reference())

        self.graph.update_labels_and_visibilities(new_labels)

    def import_single_curve(self, curve: signal_tools.Curve = None):
        if not curve:
            clipboard_curve = self._get_curve_from_clipboard()
            if clipboard_curve is None:
                self.signal_bad_beep.emit()
                return
            else:
                curve = clipboard_curve

        if app_settings.get_value("import_ppo") > 0:
            x, y = curve.get_xy()
            x_intp, y_intp = signal_tools.interpolate_to_ppo(
                x, y,
                app_settings.get_value("import_ppo"),
                app_settings.get_value("interpolate_must_contain_hz"),
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

        if any([self.curves[index].is_reference() for index in indexes_to_remove]):
            pwi.ErrorPopup(self,"Cannot move active reference curve.")
            return

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
        logger.debug("Settings:" + str(app_settings))
        if source == "file":
            file_raw = qtw.QFileDialog.getOpenFileName(self, caption='Open CSV formatted file..',
                                                       dir=app_settings.get_value("last_used_folder"),
                                                       filter='CSV format (*.txt *.csv)',
                                                       )[0]

            if file_raw and (file := Path(file_raw)).is_file():
                app_settings.set_value("last_used_folder", str(file.parent))
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

            if app_settings.get_value("import_ppo") > 0:
                x, y = curve.get_xy()
                x_intp, y_intp = signal_tools.interpolate_to_ppo(
                    x, y,
                    app_settings.get_value("import_ppo"),
                    app_settings.get_value("interpolate_must_contain_hz"),
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

    def _y_limits_menu_action_triggered(self, menu_text, checked):
        # QActionGroup emits triggered(False) for the action it just unchecked;
        # only react to the one that became checked. The menu is disabled while a
        # reference curve is active (see _make_connections), so this can't fire then.
        if not checked:
            return

        if menu_text == "Freeze":
            y_min, y_max = self.graph.ax.get_ylim()
            policy = ("fixed", {"min": y_min, "max": y_max})
        else:
            policy = (self._Y_LIMITS_POLICY_BY_MENU_TEXT[menu_text], {})

        self._y_limits_policy_selection = policy
        self._apply_y_limits_policy_selection()

    def _apply_y_limits_policy_selection(self):
        policy_name, policy_kwargs = self._y_limits_policy_selection
        self.graph.set_y_limits_policy(policy_name, **policy_kwargs)
        self.graph.update_figure()

    def _set_y_limits_policy_selection(self, policy_name, policy_kwargs=None):
        """
        Point both the View menu and the graph at the given policy. For policies
        that come from somewhere other than the menu itself, e.g. a loaded state file.
        """
        self._y_limits_policy_selection = (policy_name, dict(policy_kwargs or {}))
        menu_text = self._Y_LIMITS_MENU_TEXT_BY_POLICY.get(
            policy_name, self._Y_LIMITS_DEFAULT_MENU_TEXT)
        # setChecked() does not emit triggered(), so this only moves the checkmark.
        self._y_limits_actions[menu_text].setChecked(True)
        self._apply_y_limits_policy_selection()

    def reference_curve_activate_successful_actions(self, i_ref_curve):
        curve = self.curves[i_ref_curve]

        # mark it as reference
        curve.set_reference(True)

        # Update the names in qlist widget
        reference_item = self.qlistwidget_for_curves.item(i_ref_curve)
        reference_item.setText(curve.get_full_name())

    def reference_curve_deactivated_actions(self):
        """
        Reference curve deactivated or failed to activate.
        """
        for i, curve in enumerate(self.curves):
            if curve.is_reference():
                # revert it
                curve.set_reference(False)

                # Update the name in list
                reference_item = self.qlistwidget_for_curves.item(i)
                reference_item.setText(curve.get_full_name())

    def reference_curve_button_toggled(self, checked: bool):
        """
        Reference curve is marked in the Curve class instances with "_visible"
        Also in the graph object, there is an attribute to store if there is a reference and if so which one it is.
        """
        if checked:  # activate
            # Disable processing button
            indexes_and_curves = self.get_selected_curves(as_dict=True)
            if len(indexes_and_curves) != 1:
                # multiple selection
                self.reference_curve_deactivated_actions()
                self.signal_bad_beep.emit()
                return

            i_ref_curve, curve = list(indexes_and_curves.items())[0]
            curve_new = deepcopy(curve)
            curve_new.set_reference(True)
            self.update_curve_states_in_qlist_and_graph({i_ref_curve: curve_new},
                                                        update_figure=False,
                                                        )
            self.signal_reference_curve_activate.emit(i_ref_curve)


        elif not checked:  # deactivate
            # find back the reference curve
            reference_curves = [(i_ref_curve, curve) for i_ref_curve, curve in enumerate(self.curves) if curve.is_reference()]
            if len(reference_curves) == 0:
                return
            if len(reference_curves) > 1:
                raise RuntimeError("Multiple reference curves are in the list somehow..")

            i_ref_curve, ref_curve = reference_curves[0]
            curve_new = deepcopy(ref_curve)
            curve_new.set_reference(False)
            # Update graph
            self.update_curve_states_in_qlist_and_graph({i_ref_curve: curve_new},
                                                        update_figure=False,
                                                        )
            self.signal_reference_curve_deactivate.emit(i_ref_curve)

    def _add_single_curve(self, i_insert: int | None, curve: signal_tools.Curve, update_figure: bool = True,
                          line2d_kwargs={},
                          ):

        if not curve.is_curve():
            raise ValueError("Invalid curve")

        i_max = len(self.curves)
        first_curve = i_max == 0
        if i_insert is None or i_insert >= i_max:
            # do an add
            if not curve.has_name_prefix():
                curve.set_name_prefix(f"#{i_max:02d}")
            self.curves.append(curve)

            list_item = qtw.QListWidgetItem(curve.get_full_name())
            self.qlistwidget_for_curves.addItem(list_item)

            self.graph.add_line2d(i_max, curve.get_full_name(), curve.get_xy(),
                                  update_figure=False, line2d_kwargs={**line2d_kwargs},
                                  )
            insert_point = i_max

        else:
            # do an insert
            curve.set_name_prefix(f"#{i_max:02d}")
            self.curves.insert(i_insert, curve)

            list_item = qtw.QListWidgetItem(curve.get_full_name())
            self.qlistwidget_for_curves.insertItem(i_insert, list_item)

            self.graph.add_line2d(i_insert, curve.get_full_name(), curve.get_xy(
            ), update_figure=False, line2d_kwargs={**line2d_kwargs})

            insert_point = i_insert

        # The first curve on an empty graph needs the limits recalculated. The graph
        # is still at its default limits (or at the stale ones left over from before
        # the last curve was removed) and the custom x ticks are not applied yet.
        self.update_curve_states_in_qlist_and_graph({insert_point: curve},
                                                    update_figure=update_figure and not first_curve,
                                                    )
        if update_figure and first_curve:
            self.graph.update_figure()

        return insert_point

    def set_qitem_font(self, item: QListWidgetItem, set_to: str) -> None:
        """
        Set font type for a list item.
        """
        font = item.font()
        match set_to:
            case "normal":
                font.setWeight(qtg.QFont.Normal)
            case "thin":
                font.setWeight(qtg.QFont.Thin)
            case "bold":
                font.setWeight(qtg.QFont.Bold)
            case _:
                return

        item.setFont(font)

    def hide_curves(self, indexes: list = None):
        if isinstance(indexes, (list, np.ndarray)):
            indexes_and_curves = {i: self.curves[i] for i in indexes}
        elif self.return_false_and_beep_if_no_curve_selected():
            return
        else:
            indexes_and_curves = self.get_selected_curves(as_dict=True)

        if any([curve.is_reference() for _, curve in indexes_and_curves.items()]):
            pwi.ErrorPopup(self,"Cannot modify active reference curve.")
            return

        for index, curve in indexes_and_curves.items():
            curve.set_visible(False)

        self.update_curve_states_in_qlist_and_graph(indexes_and_curves)

    def show_curves(self, indexes: list = None):
        if isinstance(indexes, (list, np.ndarray)):
            indexes_and_curves = {i: self.curves[i] for i in indexes}
        elif self.return_false_and_beep_if_no_curve_selected():
            return
        else:
            indexes_and_curves = self.get_selected_curves(as_dict=True)

        if any([curve.is_reference() for _, curve in indexes_and_curves.items()]):
            pwi.ErrorPopup(self, "Cannot modify active reference curve.")
            return

        for index, curve in indexes_and_curves.items():
            curve.set_visible(True)

        self.update_curve_states_in_qlist_and_graph(indexes_and_curves)

    def toggle_highlight(self, item: qtw.QListWidgetItem):
        index = self.qlistwidget_for_curves.row(item)
        curve = self.curves[index]

        if curve.is_reference():
            pwi.ErrorPopup(self,"Cannot change highlight state of active reference curve.")
            return

        if curve.is_highlighted() is True:
            curve.set_highlighted(False)

        elif curve.is_highlighted() is False:
            curve.set_highlighted(True)

        self.update_curve_states_in_qlist_and_graph(indexes_and_curves={index: curve})

    def update_curve_states_in_qlist_and_graph(self, indexes_and_curves=None, update_figure=True):
        # 4 states exist
        # reference, 0.1 alpha, not shown on legend
        # highlighted, 1.0 alpha
        # normal shown, 0.9 alpha
        # hidden, 0.1 alpha, not shown on legend

        if indexes_and_curves is None:
            i_curve_list = list(enumerate(self.curves))
        else:
            i_curve_list = list(indexes_and_curves.items())

        curve_states = {i: (None, curve.is_visible(), curve.is_highlighted(), curve.is_reference())
                             for i, curve in i_curve_list}

        self.graph.update_labels_and_visibilities(curve_states, update_figure=update_figure)

        for index, curve in i_curve_list:
            item = self.qlistwidget_for_curves.item(index)
            if curve.is_highlighted():
                self.set_qitem_font(item, "bold")
            elif curve.is_visible():
                self.set_qitem_font(item, "normal")
            else:
                self.set_qitem_font(item, "thin")

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
        if app_settings.get_value("sum_selected"):
            result_curves.append(curves_sum)
        if app_settings.get_value("diff_selected"):
            result_curves.append(curves_diff)

        line2d_kwargs = {"color": "r", "linestyle": "--"}

        return {"to_insert": {0: result_curves}, "line2d_kwargs": line2d_kwargs}

    def _calculate_sensitivity(self):
        selected_curves = self.get_selected_curves()
        length_curves = len(selected_curves)
        if length_curves < 1:
            raise RuntimeError(
                "No curves selected.")

        f_min, f_max = app_settings.get_value("average_calc_f_start"), app_settings.get_value("average_calc_f_end")
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
        result_text = f"Start frequency: {app_settings.get_value("average_calc_f_start"):.5g} Hz      End frequency: {
            app_settings.get_value("average_calc_f_end"):.5g} Hz"
        result_text += "\n\n"
        result_text += tabulate(df[["Average values"]],
                                headers=("Item name", "Average"), floatfmt=(".2f"))
        result_text += "\n"
        result_text += f"\nMedian of averages: {df[["Average values"]].median().values[0]:.2f}"
        result_text += f"\nMean of averages:   {df[["Average values"]].mean().values[0]:.2f}"

        return {"title": "Average values", "result_text": result_text}

    def _add_gain(self):
        selected_curves = self.get_selected_curves()
        length_curves = len(selected_curves)
        gain_value = app_settings.get_value("add_gain_value")
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
        if app_settings.get_value("mean_selected"):
            result_curves.append(curve_mean)
        if app_settings.get_value("median_selected"):
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
            app_settings.get_value("outlier_fence_iqr"),
            f_min=app_settings.get_value("outlier_check_start_freq"),
            f_max=app_settings.get_value("outlier_check_end_freq")
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
            f"-{app_settings.get_value("outlier_fence_iqr"):.1f}xIQR, {length_curves} curves")
        upper_fence.add_name_suffix(
            f"+{app_settings.get_value("outlier_fence_iqr"):.1f}xIQR, {length_curves} curves")

        if app_settings.get_value("outlier_action") == "Hide" and outlier_indexes:
            self.hide_curves(indexes=outlier_indexes)
            for curve in result_curves:
                curve.add_name_suffix("calculated before hiding outliers")
        elif app_settings.get_value("outlier_action") == "Remove" and outlier_indexes:
            self.remove_curves(indexes=outlier_indexes)
            for curve in result_curves:
                curve.add_name_suffix("calculated before removing outliers")

        line2d_kwargs = {"color": "k", "linestyle": "--"}

        return {"to_insert": {0: result_curves}, "line2d_kwargs": line2d_kwargs}

    def _show_best_fits(self):
        selected_curves = self.get_selected_curves(as_dict=True)
        if len(selected_curves) != 1:
            error_message = ("Multiple curves found in selection."
                            "\nTo find best fit to a curve, you need to choose a single curve from the list first."
                             )
            pwi.ErrorPopup(self, error_message)
            return {}

        else:
            # ---- Collect curves
            i_ref_curve, ref_curve = list(selected_curves.items())[0]
            ref_freqs, ref_curve_interpolated = signal_tools.interpolate_to_ppo(
                *ref_curve.get_xy(),
                app_settings.get_value("best_fit_calculation_resolution_ppo"),
                app_settings.get_value("interpolate_must_contain_hz"),
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
                                app_settings.get_value("best_fit_critical_range_start_freq") and column < app_settings.get_value("best_fit_critical_range_end_freq")]
            if critical_columns:
                weighing_normalizer = (len(df.columns) + len(critical_columns) *
                                       (app_settings.get_value("best_fit_critical_range_weight") - 1)) / len(df.columns)
                weighing_critical = app_settings.get_value("best_fit_critical_range_weight") / weighing_normalizer
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
                app_settings.get_value("processing_interpolation_ppo"),
                app_settings.get_value("interpolate_must_contain_hz"),
            )

            new_curve = signal_tools.Curve(xy)
            new_curve.set_name_base(curve.get_name_base())
            for suffix in curve.get_name_suffixes():
                new_curve.add_name_suffix(suffix)
            new_curve.add_name_suffix(
                f"interpolated to {app_settings.get_value("processing_interpolation_ppo")} ppo")
            result_curves[i_curve + 1] = new_curve

        line2d_kwargs = {"color": "k", "linestyle": "-"}

        return {"to_insert": result_curves, "line2d_kwargs": line2d_kwargs}

    def _smoothen_curves(self):
        selected_curves = self.get_selected_curves(as_dict=True)

        result_curves = {}

        for i_curve, curve in selected_curves.items():

            if app_settings.get_value("smoothing_type") == "Butterworth 8th, log spaced":
                xy = signal_tools.smooth_log_spaced_curve_butterworth_fast(*curve.get_xy(),
                                                                           bandwidth=app_settings.get_value("smoothing_bandwidth"),
                                                                           resolution=app_settings.get_value("smoothing_resolution_ppo"),
                                                                           order=8,
                                                                           )

            elif app_settings.get_value("smoothing_type") == "Butterworth 4th, log spaced":
                xy = signal_tools.smooth_log_spaced_curve_butterworth_fast(*curve.get_xy(),
                                                                           bandwidth=app_settings.get_value("smoothing_bandwidth"),
                                                                           resolution=app_settings.get_value("smoothing_resolution_ppo"),
                                                                           order=4,
                                                                           )

            elif app_settings.get_value("smoothing_type") == "Rectangular, w/o interpolation":
                xy = signal_tools.smooth_curve_rectangular_no_interpolation(*curve.get_xy(),
                                                                            bandwidth=app_settings.get_value("smoothing_bandwidth"),
                                                                            )

            elif app_settings.get_value("smoothing_type") == "Gaussian, log spaced":
                xy = signal_tools.smooth_curve_gaussian(*curve.get_xy(),
                                                        bandwidth=app_settings.get_value("smoothing_bandwidth"),
                                                        resolution=app_settings.get_value("smoothing_resolution_ppo"),
                                                        )

            else:
                raise NotImplementedError(
                    "This smoothing type is not available")

            new_curve = signal_tools.Curve(xy)
            new_curve.set_name_base(curve.get_name_base())
            for suffix in curve.get_name_suffixes():
                new_curve.add_name_suffix(suffix)
            new_curve.add_name_suffix(
                f"smoothed 1/{app_settings.get_value("smoothing_bandwidth")}")
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
        # y limits are not stored; they are recalculated from the policy on load.
        # The policy stored is the one selected in the View menu, not the graph's
        # current one -- an active reference curve overrides that with its own.
        y_limits_policy_name, y_limits_policy_kwargs = self._y_limits_policy_selection
        graph_info = {"title": ax.get_title(),
                      "xlabel": ax.get_xlabel(),
                      "ylabel": ax.get_ylabel(),
                      "xlim": ax.get_xlim(),
                      "xscale": ax.get_xscale(),
                      "yscale": ax.get_yscale(),
                      "y_limits_policy_name": y_limits_policy_name,
                      "y_limits_policy_kwargs": y_limits_policy_kwargs,
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
                          "highlighted": curve.is_highlighted(),
                          "identification": curve._identification,
                          "x": tuple(curve.get_x()),
                          "y": tuple(curve.get_y()),
                          }
            return curve_info

        lines_info = []
        curves_info = []
        for line, curve in zip(self.graph.get_lines_in_qlist_order(), self.curves):
            lines_info.append(collect_line2d_info(line))
            curves_info.append(collect_curve_info(curve))

        package = pickle.dumps(
            (graph_info, lines_info, curves_info), protocol=5)
        return package

    def set_widget_state(self, package):
        graph_info, lines_info, curves_info = pickle.loads(package)

        # ---- delete all lines first
        # self.remove_curves([*range(len(self.curves))])

        # The graph state in the file is only applied when starting from an empty
        # graph. When adding to curves that are already there, the current state stays.
        apply_graph_state = len(self.curves) == 0

        if apply_graph_state:
            # ---- apply graph state
            ax = self.graph.ax
            ax.set_title(graph_info["title"])
            ax.set_xlabel(graph_info["xlabel"])
            ax.set_ylabel(graph_info["ylabel"])
            ax.set_xscale(graph_info["xscale"])
            ax.set_yscale(graph_info["yscale"])
            # x limits are applied after the figure update at the end of this method,
            # since a recalculating update can autoscale them away. y limits are not
            # restored at all -- the stored policy defines them.

        # ---- add lines
        for line_info, curve_info in zip(lines_info, curves_info):
            curve = signal_tools.Curve((curve_info["x"], curve_info["y"]))
            curve.set_visible(curve_info["visible"])
            curve.set_highlighted(curve_info.get("highlighted", False))
            curve._identification = curve_info["identification"]

            self._add_single_curve(
                None, curve, update_figure=False, line2d_kwargs=line_info)

        self.update_curve_states_in_qlist_and_graph(update_figure=False)

        if not apply_graph_state:
            self.graph.update_figure(recalculate_limits=False)
            return

        # ---- y limits: from the policy stored in the file. Files written before this
        # was stored (they carry a "ylim" key instead) fall back to the default policy.
        # This also does the figure update.
        self._set_y_limits_policy_selection(
            graph_info.get("y_limits_policy_name",
                           self._Y_LIMITS_POLICY_BY_MENU_TEXT[self._Y_LIMITS_DEFAULT_MENU_TEXT]),
            graph_info.get("y_limits_policy_kwargs"),
            )

        # ---- x limits, after the update above, which can autoscale them away
        if "xlim" in graph_info.keys():  # added as bug fix in 0.2.4
            self.graph.ax.set_xlim(graph_info["xlim"])
            self.graph.canvas.draw_idle()

    def save_state_to_file(self):
        path_unverified = qtw.QFileDialog.getSaveFileName(self, caption='Save state to a file..',
                                                          dir=app_settings.get_value("last_used_folder"),
                                                          filter='Linecraft files (*.lc)',
                                                          )
        # path_unverified.setDefaultSuffix("lc") not available for getSaveFileName

        try:
            file_raw = path_unverified[0]
            if file_raw:  # if we received a string
                file = Path(file_raw)
                # Filter not working as expected in nautilus. Saves files without including the extension.
                # Therefore added this seciton.
                if file.suffix != ".lc":
                    file = file.with_suffix(".lc")
                assert file.parent.exists()
            else:
                return  # nothing was selected, pick file canceled
        except:
            raise NotADirectoryError(file_raw)

        app_settings.set_value("last_used_folder", str(file.parent))
        package = self.get_widget_state()
        with open(file, "wb") as f:
            f.write(package)
        self.signal_good_beep.emit()

    def pick_a_file_and_add_state_from_it(self):
        file = qtw.QFileDialog.getOpenFileName(self, caption='Get state from a save file..',
                                               dir=app_settings.get_value("last_used_folder"),
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

        app_settings.set_value("last_used_folder", str(my_file.parent))
        with open(my_file, "rb") as f:
            self.set_widget_state(f.read())
        self.signal_good_beep.emit()
