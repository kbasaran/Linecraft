import time
import logging
from pathlib import Path
from generictools.settings import SettingsManager

APP_DEFINITIONS = {"app_name": "Linecraft",
                   "version": "1.0.0",
                   "description": "Loudspeaker design and calculations",
                   "copyright": "Copyright (C) 2026 Kerem Basaran",
                   "icon_path": "logo/icon.ico",  # relative posix path
                   "author": "Kerem Basaran",
                   "author_short": "kbasaran",
                   "email": "kbasaran@gmail.com",
                   "website": "https://github.com/kbasaran",
                   }
# uncomment for release candidate builds
# APP_DEFINITIONS["version"] += "rc" + time.strftime("%y%m%d", time.localtime())

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger()

    try:
        answer = input("Type 'x' to delete all settings: ")
        if answer.lower() == 'x':
            logger.info("Deleting all settings...")
            app_settings = SettingsManager(APP_DEFINITIONS, DEFAULTS)
            app_settings.reset_all_to_defaults()
            logger.info("Settings deleted successfully.")
        else:
            logger.info("Operation cancelled by user.")
    except KeyboardInterrupt:
        exit()

else:
    logger = logging.getLogger(__name__)
