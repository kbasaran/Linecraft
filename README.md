# Linecraft
Frequency response plotting and statistics tool developed using Qt for Python

![](/images/sc_main.png)

## Introduction
Linecraft can import frequency response curves from .csv files, spreadsheets and dB-lab. It allows plotting of the curves using Matplotlib library. It offers the following manipulation and statistical analysis possibilities:
- Interpolation of curve into new frequency points
- Calculation of mean and median response from a group of curves
- Calculation of interquartile range and detection of outliers
- Sorting of curves based on their correlation to a reference curve (i.e. best fit to reference)
- Display of deviations from a reference curve (i.e. set a curve as y=0)

## Installation
### Using Windows 64-bit Installer
1. Download the latest .msi installer from [releases](https://github.com/kbasaran/Linecraft/releases/latest)
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
