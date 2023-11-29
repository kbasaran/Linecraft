# Introduction
Linecraft is a tool for visualization and statistical analysis of frequency response curves.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_main.png)

## Features
- Import curves from CSV files or clipboard
- Interpolation of curves into other array of frequencies 
- Calculation of mean and median from a group of curves
- Calculation of interquartile range and detection of outliers in a group
- Sorting of curves based on their correlation to a reference curve (i.e. best fit to reference)
- Display of deviations from a reference curve (i.e. set a certain curve as y<sub>ref</sub>)

## Scope
Linecraft accepts only real and positive numbers for frequency (horizontal) axis. Values must be unique and sorted.

The amplitude axis (vertical) is linear. This means the average of 88dB and 90dB will be calculated as 89dB.

## Performance
Linecraft is tailored to stay responsive while working with relatively large number of curves (e.g. 2000 curves with 200 points each). As the amount of data goes up, it will require more memory and may feel unresponsive. To improve the performance, consider making your application window smaller and choosing a more basic Matplotlib style such as 'fast'. This will reduce the workload of rendering the graph, which accounts for most of the processing time.

# Installation
## Using Windows 64-bit Installer
1. Download the latest .msi installer from [releases](https://github.com/kbasaran/Linecraft/releases/latest)
2. Run installer and follow instructions

## Within an existing Python environment (Windows/Linux)
> Only tested with Python 3.11.5
```
pip install -r requirements.txt
python main.py
```

# Importing curves
## Import single curve from clipboard
Use the 'Import curve' button to import a single curve from the clipboard. The application will do verification on the data at the clipboard and import it if it's valid.
- dB-lab exports will automatically be recognized and the curve name and frequency array will be imported
- Tab or comma separated tables will be automatically parsed to extract a frequency response curve
  - The dimension with 'size=2' will be assumed to split the frequency and amplitude arrays
    - If both dimensions are 'size=2', columns will be assumed to split the frequency and value arrays
    - e.g.:

| 1000 | 80.4 |
| --- | --- |
| 2000 | 85.6 |
  - If the import data contains more than one tab character, delimiter will be assumed as tab. Otherwise comma will be used. (Excel uses tab as default delimiter)
  - Decimal separator must always be a dot for single curve imports from clipboard.

## Import multiple curves
When 'Import table' button is clicked the application will show a dialog. The user needs to define the correct import settings here. Afterwards the user chooses if the data is to be gathered from a CSV file or the clipboard.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_table_import.png)
### Layout type
Choose how your table is laid out.

- If column labels (i.e. headers) list the frequencies, choose 'headers are frequencies'. Row indexes (A1, A2 below) will be used as names of the curves.

| name | 100 | 200 | 400 | 800 | 1600 |
| --- | --- | --- | --- | --- | --- |
| A1 | 80 | 85 | 84 | 84 | 86 |
| A2 | 82 | 85 | 82 | 84 | 86 |
| A3 | 83 | 85 | 83 | 85 | 86 |
| A4 | 82 | 85 | 82 | 84 | 85 |

> If there is no column with names, select 0. Application will generate a unique name for each curve.

- If row labels (i.e. indexes) list the frequencies, choose 'headers are names'. Headers (A1, A2 below) will be used as names of the curves.

| frequency | A1 | A2 | A3 | A4 |
| --- | --- | --- | --- | --- |
| 100 | 80 | 82 | 83 | 82 |
| 200 | 85 | 85 | 85 | 85 |
| 400 | 84 | 82 | 83 | 82 |
| 800 | 84 | 84 | 85 | 84 |
| 1600 | 86 | 86 | 86 | 85 |

> If there is no row with names, select 0. Application will generate a unique name for each curve.

### Line number of headers
Use this value to define the line number which contains the headers. E.g. in below example the line number of headers need to be set to 3 since the table starts with 2 rows of unused data.
> Counting here uses natural numbers, therefore starting at 1.

| A row with unused data | | | | |
| --- | --- | --- | --- | --- |
| Another row with unused data | | | | |
| frequency | A1 | A2 | A3 | A4 |
| 100 | 80 | 82 | 83 | 82 |
| 200 | 85 | 85 | 85 | 85 |
| 400 | 84 | 82 | 83 | 82 |
| 800 | 84 | 84 | 85 | 84 |
| 1600 | 86 | 86 | 86 | 85 |

### Column number of indexes
Use this value to define the column number with the indexes. E.g. in below example the column number of indexes need to be set to 2 so as to skip the first empty column.
> Counting here uses natural numbers, therefore starting at 1.

| | frequency | A1 | A2 | A3 | A4 |
| --- | --- | --- | --- | --- | --- |
| | 100 | 80 | 82 | 83 | 82 |
| | 200 | 85 | 85 | 85 | 85 |
| | 400 | 84 | 82 | 83 | 82 |
| | 800 | 84 | 84 | 85 | 84 |
| | 1600 | 86 | 86 | 86 | 85 |

### Delimiter
Choose the delimiter that separates the columns in the comma separated file. Please note Excel clipboard exports will use tab as delimiter while a CSV file usually employs a comma. For more information check [here](https://en.wikipedia.org/wiki/Comma-separated_values).
### Decimal separator
Select the character that is used as decimal separator. Most commonly a dot is used in English language and academia.

## Auto Import
When this function is enabled, the application will attempt a single curve import each time there is new information on the clipboard.

# Displaying curves
Each imported curve will appear in the graph and the selection list below. The curve name will be an auto generated index number followed by a description.

To make operations on a curve, you first need to select it from the list.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_curve_names.png)

## Hide/show
Use this to put curves in the background. They will still be accessible and their data intact.
## Reset indexes
Use this to reset the index numbers shown before the names of the curves. Numbers will be sorted from zero upwards based on current position in list.
## Rename
Use this to change name of a curve. If multiple curves are selected, this function will add a user defined suffix to all the selected curves.
## Reset colors
Reset the curve colors to the default Matplotlib sequence. The curve's position in the list defines its color.
## Set reference
Subtracts all curves on graph by the selected curve. This makes the selected curve into the 'y=0' line and all other curves are shown with their relative value to this curve.

# Processing
Most of the processing functions rely on having common frequency points between different curves. This way, statistical operations can be done per frequency point. If your curves do not have common frequency points, consider using the 'interpolate' method to interpolate your curves to a new array of frequency points. You can also use the 'interpolate on import' function in settings to interpolate curves automatically during import.

## Statistics - Mean/Median
The mean/median is calculated for each frequency point common in the selected curves. The result is made into a new curve and this new curve is added to the list.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_stats_example.png)

## Smoothing
Smooths the selected curves.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_smoothing.png)

### Type of smoothing
| Type | Speed | Accuracy | Requires high resolution input data | Interpolates to new points |
| --- | --- | --- | --- | --- |
| Rectangular | High | Medium | Yes | No |
| Gaussian | Low | Medium | No | Yes |
| Butterworth | Very low | Very high | No | Yes |

> Gaussian smoothing uses a Gaussian curve whose sigma is equal to half the selected smoothing bandwidth. It is not common practice for smoothing of octavely spaced data. Added here for convenience.

### Outlier detection
![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_outliers_dialog.png)

This feature is used to detect curves that are considered outliers. It will check if the curves have data points outside of the fence values defined using the inter-quartile range (IQR) method. The fence is created symmetrically above and below the median curve. The distance of the fence to the median is defined by the fence value given by user.

The control is done per frequency point. If a single value in the curve is outside the fences, the curve is considered an outlier.

For more information about the method [visit here](https://en.wikipedia.org/wiki/Interquartile_range#Outliers).

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_outlier_example.png)

### Interpolation
Interpolates the selected curve(s) to a new array of frequencies that is octavely spaced. The number of frequency points is defined by the user input.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_interpolation_example.png)

### Best fit to current
Creates a list of curves that are most similar to the selected curve. The error is calculated as the standard deviation of the residuals at each frequency. It is possible to define a certain frequency range and apply a weighing else than 1 for it. This range is referred to as "critical range" in the application but can also be set to a lower weighing.

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_best_fit_settings.png)

![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_best_fit_results_example.png)

## Settings
![](https://github.com/kbasaran/Linecraft/blob/main/images/sc_settings.png) 
