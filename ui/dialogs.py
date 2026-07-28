import logging
from functools import partial

import matplotlib as mpl
import pyperclip
from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw

from generictools import signal_tools
import generictools.personalized_widgets as pwi
from generictools.settings import singleton_settings

app_settings = singleton_settings()
logger = logging.getLogger(__name__)


class HorizontalTextTabStyle(qtw.QProxyStyle):
    """Keep tab labels horizontal when tabs are placed on the left/right side."""

    def sizeFromContents(self, contents_type, option, size, widget):
        s = super().sizeFromContents(contents_type, option, size, widget)
        if contents_type == qtw.QStyle.ContentsType.CT_TabBarTab:
            s.transpose()
        return s

    def drawControl(self, element, option, painter, widget):
        if element == qtw.QStyle.ControlElement.CE_TabBarTabLabel:
            option = qtw.QStyleOptionTab(option)
            option.shape = qtw.QTabBar.Shape.RoundedNorth
        super().drawControl(element, option, painter, widget)


class ProcessingDialog(qtw.QDialog):
    signal_processing_request = qtc.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowModality(qtc.Qt.WindowModality.ApplicationModal)
        self.setWindowTitle("Processing Menu")
        self.setMinimumHeight(400)
        self.setLayout(qtw.QVBoxLayout())
        self.tab_widget = qtw.QTabWidget(
            tabPosition=qtw.QTabWidget.TabPosition.West)
        self._tab_style = HorizontalTextTabStyle()
        self.tab_widget.tabBar().setStyle(self._tab_style)
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
        self.tab_widget.setCurrentIndex(app_settings.get_value("processing_selected_tab"))
        for i in range(self.tab_widget.count()):
            user_form = self.tab_widget.widget(i)
            tab_settings = {}
            for key in user_form.interactable_widgets.keys():
                tab_settings[key] = app_settings.get_value(key)
            user_form.update_complete_form(tab_settings)

        # ---- Connections
        button_group.buttons()["cancel_pushbutton"].clicked.connect(
            self.reject)
        button_group.buttons()["run_pushbutton"].clicked.connect(
            self._save_and_close)

    def _save_and_close(self):
        active_tab_index = self.tab_widget.currentIndex()
        user_form, processing_function_name = self.user_forms_and_recipient_functions[active_tab_index]
        app_settings.set_value("processing_selected_tab",
                        self.tab_widget.currentIndex())

        processing_settings = {}
        for key in user_form.interactable_widgets.keys():
            processing_settings[key] = user_form.get_value(key)
        app_settings.set_all_from_dict(processing_settings)

        self.setWindowTitle("Calculating...")
        self.setEnabled(False)  # calculating
        self.repaint()
        self.signal_processing_request.emit(processing_function_name)
        self.accept()


class ImportDialog(qtw.QDialog):
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
        stored_import_settings = {}
        for key, widget in user_form.interactable_widgets.items():
            stored_import_settings[key] = app_settings.get_value(key)
        user_form.update_complete_form(stored_import_settings)

        # Connections
        button_group.buttons()["close_pushbutton"].clicked.connect(self.reject)
        button_group.buttons()["open_file_pushbutton"].clicked.connect(
            partial(self._import_requested, "file", user_form))
        button_group.buttons()["read_clipboard_pushbutton"].clicked.connect(
            partial(self._import_requested, "clipboard", user_form))

    def _save_form_values_to_settings(self, user_form: pwi.UserForm):
        form_values = user_form.get_form_values()
        app_settings.set_all_from_dict(form_values)

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
            values_from_settings[key] = app_settings.get_value(key)
        user_form.update_complete_form(values_from_settings)

        # Connections
        button_group.buttons()["cancel_pushbutton"].clicked.connect(
            self.reject)
        button_group.buttons()["save_pushbutton"].clicked.connect(
            partial(self._save_and_close, user_form))

    def _save_and_close(self, user_form):
        vals = user_form.get_form_values()
        if vals["matplotlib_style"]["current_text"] != app_settings.get_value("matplotlib_style"):
            message_box = qtw.QMessageBox(qtw.QMessageBox.Information,
                                          "Information",
                                          "Application needs to be restarted to be able to use the new matplotlib style.",
                                          )
            message_box.setStandardButtons(
                qtw.QMessageBox.Cancel | qtw.QMessageBox.Ok)
            returned = message_box.exec()

            if returned == qtw.QMessageBox.Cancel:
                return

        for widget_name, value in vals.items():
            app_settings.set_value(widget_name, value)
        self.signal_settings_changed.emit()
        self.accept()


class AutoImporter(qtc.QThread):
    signal_new_import = qtc.Signal(signal_tools.Curve)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def run(self):
        while not self.isInterruptionRequested():
            try:
                cb_data = pyperclip.waitForPaste(1)
                new_curve = signal_tools.Curve(cb_data)
                if new_curve.is_curve():
                    self.signal_new_import.emit(new_curve)
            except pyperclip.PyperclipTimeoutException:
                pass
            except Exception as e:
                logger.warning(e)
