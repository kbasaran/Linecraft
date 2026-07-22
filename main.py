# Linecraft - Frequency response display and statistics tool
# Copyright (C) 2026 - Kerem Basaran
# https://github.com/kbasaran

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

import logging
import sys
import time
from pathlib import Path

from PySide6 import QtCore as qtc
from PySide6 import QtGui as qtg
from PySide6 import QtWidgets as qtw

import generictools.personalized_widgets as pwi
from config.app_config import APP_DEFINITIONS
from ui.main_window import CurveAnalyze

logger = logging.getLogger(__name__)


def get_main_dir():

    if getattr(sys, 'frozen', False):
        # The application is frozen
        return Path(sys.executable).parent

    else:
        # The application is not frozen
        return Path(__file__).parent


def parse_args(APP_DEFINITIONS):
    import argparse

    description = (
        f"{APP_DEFINITIONS['app_name']} - {APP_DEFINITIONS['copyright']}"
        "\nThis program comes with ABSOLUTELY NO WARRANTY"
        "\nThis is free software, and you are welcome to redistribute it"
        "\nunder certain conditions. See LICENSE file for more details."
    )

    parser = argparse.ArgumentParser(prog="python main.py",
                                     description=description,
                                     epilog={APP_DEFINITIONS['website']},
                                     )
    parser.add_argument('infile', nargs="?", type=Path,
                        help="Path to a '*.lc' file. This will open a saved state.")
    parser.add_argument('-d', '--loglevel', nargs="?",
                        choices=["debug", "info",
                                 "warning", "error", "critical"],
                        help="Set logging level for Python logging. Valid values are debug, info, warning, error and critical.")

    return parser.parse_args()


def create_sound_engine(app):
    sound_engine = pwi.SoundEngine()
    sound_engine_thread = qtc.QThread()
    sound_engine.moveToThread(sound_engine_thread)

    # Connect
    # app.aboutToQuit.connect(sound_engine.release_all)
    app.aboutToQuit.connect(sound_engine_thread.quit)

    sound_engine_thread.start(qtc.QThread.HighPriority)

    return sound_engine, sound_engine_thread


def setup_logging(level: str = "warning", args=None):
    if args and args.loglevel:
        log_level = getattr(logging, args.loglevel.upper())
    else:
        log_level = level.upper()

    log_filename = Path.home().joinpath(
        f".{APP_DEFINITIONS['app_name'].lower()}.log")

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
    args = parse_args(APP_DEFINITIONS)
    logger = setup_logging(args=args)

    # ---- Create QApplication
    if not (app := qtw.QApplication.instance()):
        app = qtw.QApplication(sys.argv)
        # there is a new recommendation with qApp but how to do the sys.argv with that?
        # app.setQuitOnLastWindowClosed(True)  # is this necessary??
        icon_path = str(get_main_dir().joinpath(APP_DEFINITIONS["icon_path"]))
        app.setWindowIcon(qtg.QIcon(icon_path))

    # ---- Create sound engine
    sound_engine, sound_engine_thread = create_sound_engine(app)

    # ---- Create main window
    mw = CurveAnalyze()
    mw.signal_bad_beep.connect(sound_engine.bad_beep)
    mw.signal_good_beep.connect(sound_engine.good_beep)
    # mw.add_state_from_file("Test apps/test.lc")


    # ---- Catch exceptions and handle with pop-up widget
    error_handler = pwi.ErrorHandler(logger, developer=False)
    sys.excepthook = error_handler.excepthook


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
