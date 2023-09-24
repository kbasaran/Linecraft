#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from cx_Freeze import setup, Executable

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
                        copyright="Copyright (C) 2023 Kerem Basaran",
                        base=base,
                        shortcut_name="Linecraft 0.1.0",
                        shortcut_dir="DesktopFolder",
                        icon=r".\logo\icon.ico",
                        )
            ],

setup(
    name="Linecraft",
    version="0.1.0",
    description="Frequency response plotting and statistics",
    options={"build_exe": build_exe_options},
    executables=executables,
)

