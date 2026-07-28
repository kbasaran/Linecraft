#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from cx_Freeze import setup, Executable
# https://cx-freeze.readthedocs.io/en/stable/setup_script.html

# This script lives in package_win/, one level below the project root. Anchor every
# source path to the root and put the root on sys.path so the project imports work
# regardless of the directory the build is launched from (the build itself is run
# from package_win/ so build/ and dist/ land there).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.app_config import APP_DEFINITIONS

# Dependencies are automatically detected, but it might need fine tuning.
# include_files entries are (absolute source, path-inside-the-build): absolute
# sources so the build does not depend on the current directory, root-relative
# destinations so the frozen layout mirrors the source tree.
build_exe_options = {
    "packages": ["scipy", "numpy",  # RecursionError in cx_Freeze if these are not provided
                 "sounddevice", "_sounddevice_data",  # bundle PortAudio native binary
                 "tabulate"],  # used directly and dynamically by pandas.to_markdown()
    "include_files": [
        (str(ROOT / "LICENSE"), "LICENSE"),
        (str(ROOT / "README.md"), "README.md"),
        (str(ROOT / APP_DEFINITIONS["icon_path"]), APP_DEFINITIONS["icon_path"]),
        ],
    "silent_level": 1,
}

bdist_msi_options = {
    "extensions": [{"extension": "lc",
                    "verb": "load",
                    "argument": '"%1"',
                    "executable": "main.exe",
                    }]
                  }

executables=[Executable(str(ROOT / "main.py"),
                        copyright=APP_DEFINITIONS["copyright"],
                        base="gui",
                        shortcut_name=APP_DEFINITIONS["app_name"] + " v" + APP_DEFINITIONS["version"],
                        shortcut_dir="DesktopFolder",
                        icon=str(ROOT / APP_DEFINITIONS["icon_path"]),
                        ),
            ]

setup(
    name=APP_DEFINITIONS["app_name"],
    version=APP_DEFINITIONS["version"],
    description=APP_DEFINITIONS["description"],
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=executables,
)
