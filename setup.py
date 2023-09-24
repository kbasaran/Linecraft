#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from cx_Freeze import setup, Executable
from main import app_definitions
# https://cx-freeze.readthedocs.io/en/stable/setup_script.html

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": ["scipy", "numpy"],
    "include_files": [
        (".\LICENSE", ".\LICENSE"),
        (".\README.md", ".\README.md"),
	(".\logo\icon.ico", ".\logo\icon.ico"),
        ],
    "silent_level": 1,
}

# base="Win32GUI" should be used only for Windows GUI app
base = "Win32GUI" if sys.platform == "win32" else None

executables=[Executable("main.pyw",
                        copyright=app_definitions["copyright"],
                        base=base,
                        shortcut_name=app_definitions["app_name"] + " v" + app_definitions["version"],
                        shortcut_dir="DesktopFolder",
                        icon=app_definitions["icon_path"],
                        )
            ],

setup(
    name=app_definitions["app_name"],
    version=app_definitions["version"],
    description=app_definitions["description"],
    options={"build_exe": build_exe_options},
    executables=executables,
)
