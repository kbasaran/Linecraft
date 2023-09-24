# Linecraft
Frequency response plotting and statistics tool developed using Qt for Python

![](/images/sc_main.png)

## Introduction
Linecraft can import frequency response curves from csv files, spreadsheet applications or dB-lab. It allows plotting of the curves using Matplotlib library. It offers following manipulation and statistical analysis possibilities:
- Linear interpolation to octave spaced frequency points
- Calculation of mean and median responses from imported curves
- Calculation of interquartile range and detection of outliers based on their z-score
- Sorting of curves based on their weighted correlation to a reference curve (i.e. best fit or reference selection)
- Display of curves relative to a reference curve (i.e. set reference curve as y=0)

## Installation
### Using Windows 64-bit Installer
1. Download the latest .msi installer from [releases](/releases/latest)
2. Run installer and follow instructions

### Existing Python environment (Windows/Linux)
> Only tested with Python 3.11.5
```
pip install -r requirements.txt
python main.pyw
```

## Screenshots
### Table import
![](/images/sc_table_import.png)
### Smoothing options
![](/images/sc_smoothing.png)
### Settings
![](/images/sc_settings.png)
