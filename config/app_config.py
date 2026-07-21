from dataclasses import dataclass, fields
from pathlib import Path
import time
import logging
import json
from PySide6 import QtCore as qtc

APP_DEFINITIONS = {"app_name": "Linecraft",
                   "version": "0.4.5",
                   "description": "Loudspeaker design and calculations",
                   "copyright": "Copyright (C) 2026 Kerem Basaran",
                   "icon_path": "images/logo2025.ico",  # relative posix path
                   "author": "Kerem Basaran",
                   "author_short": "kbasaran",
                   "email": "kbasaran@gmail.com",
                   "website": "https://github.com/kbasaran",
                   }
# uncomment for release candidate builds
APP_DEFINITIONS["version"] += "rc" + time.strftime("%y%m%d", time.localtime())

class SettingsManager(qtc.QObject):
    _instance = None
    _initialized = False
    settings_changed = qtc.Signal()

    # Define your defaults here
    DEFAULTS = {
    "app_name": APP_DEFINITIONS["app_name"],
    "author": APP_DEFINITIONS["author"],
    "author_short": APP_DEFINITIONS["author_short"],
    "version": APP_DEFINITIONS["version"],
    "last_used_folder": str(Path.home()),

    "A_beep": 0.25,
    "show_legend": True,
    "max_legend_size": 7,  # 0 means no limit
    "import_ppo": 48,
    "export_ppo": 48,
    "matplotlib_style": "bmh",
    "interpolate_must_contain_hz": 1000,
    "graph_grids": "Major and minor",

    "processing_selected_tab": 0,

    "mean_selected": False,
    "median_selected": True,

    "smoothing_type": "Butterworth 8th, log spaced",
    "smoothing_resolution_ppo": 96,
    "smoothing_bandwidth": 6,

    "outlier_fence_iqr": 10.,
    "outlier_check_start_freq": 20,
    "outlier_check_end_freq": 20_000,
    "outlier_action": "None",

    "sum_selected": True,
    "diff_selected": True,

    "average_calc_f_start": 20,
    "average_calc_f_end": 20_000,

    "add_gain_value": 0.,

    "processing_interpolation_ppo": 96,

    "best_fit_calculation_resolution_ppo": 24,
    "best_fit_critical_range_start_freq": 200,
    "best_fit_critical_range_end_freq": 5000,
    "best_fit_critical_range_weight": 1.,

    "import_table_no_line_headers": 1,
    "import_table_no_columns": 1,
    "import_table_layout_type": "Headers are frequencies, indexes are names",
    "import_table_delimiter": "Tab",
    "import_table_decimal_separator": ". (dot)",
}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self.__class__._initialized:
            return
        super().__init__()
        self.q_settings = qtc.QSettings(
            APP_DEFINITIONS["author_short"],
            self.get_storage_title()
        )
        self.__class__._initialized = True

    def get_storage_title(self):
        return (
                APP_DEFINITIONS["app_name"]
                + " v"
                + (".".join(APP_DEFINITIONS["version"].split(".")[:2]) if "." in APP_DEFINITIONS["version"] else "???")
        )

    def get_value(self, key: str):
        """
        Retrieve value from QSettings.
        If key doesn't exist, return the default value from DEFAULTS.
        Returns the value with its original JSON type.
        """
        # Check if key exists in QSettings
        if not self.q_settings.contains(key):
            return self.DEFAULTS.get(key)

        # Retrieve and decode JSON
        raw = self.q_settings.value(key)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            # Fallback if value wasn't JSON (legacy or corruption)
            return raw

    def get_all_as_dict(self):
        """
        Retrieve all settings as a dictionary.
        """
        return {key: self.get_value(key) for key in self.DEFAULTS.keys()}

    def set_all_from_dict(self, settings_dict: dict, signal=True):
        """
        Set all settings from a dictionary.
        """
        for key, value in settings_dict.items():
            self.set_value(key, value, signal=False)
        if signal:
            self.settings_changed.emit()

    def set_value(self, key: str, value, signal=True):
        """
        Store value as JSON string in QSettings.
        Emits setting_changed signal with key and value.
        """
        if isinstance(value, dict):
            new_value = value["current_text"]  # handles data coming from comboboxes. stores main text only.
        else:
            new_value = value

        json_string = json.dumps(new_value)
        self.q_settings.setValue(key, json_string)
        if signal:
            self.settings_changed.emit()

    def remove_value(self, key: str):
        """Delete a setting. Next get_value will return the default."""
        self.q_settings.remove(key)

    def reset_to_default(self, key: str):
        """Remove a setting so it falls back to the default value."""
        self.remove_value(key)

    def reset_all_to_defaults(self):
        """Clear all settings and reload from DEFAULTS."""
        self.q_settings.clear()
        self.settings_changed.emit()

    def sync(self):
        """Force write to disk."""
        self.q_settings.sync()

    def get_all_defaults(self):
        """Return a copy of the defaults dictionary."""
        return self.DEFAULTS.copy()

    def clear(self):
        """Clear all settings and reload from DEFAULTS."""
        self.q_settings.clear()
        self.settings_changed.emit()


# Global accessor
def singleton_settings():
    return SettingsManager()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger()

    try:
        answer = input("Type 'x' to delete all settings: ")
        if answer.lower() == 'x':
            logger.info("Deleting all settings...")
            app_settings = singleton_settings()
            app_settings.reset_all_to_defaults()
            logger.info("Settings deleted successfully.")
        else:
            logger.info("Operation cancelled by user.")
    except KeyboardInterrupt:
        exit()

else:
    logger = logging.getLogger(__name__)
