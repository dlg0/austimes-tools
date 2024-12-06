# Austimes Command-Line Tool

## Overview

This tool processes Excel files from the `data/luto/20241010` directory, extracting and transforming data for simulation models.

## Usage

### Load LUTO Data

1. Run the tool from the command line to load LUTO data:
   ```bash
   austimes-tools load-luto
   ```
   This command will process Excel files from the `data/luto/20241010` directory, extracting and transforming data for simulation models. The processed data will be saved in the `output` directory as `luto_processed_data.xlsx`.

### Merge AppData JSON Files

2. To merge AppData JSON files, run the following command:
   ```bash
   austimes-tools merge-appdata --appdata-dir path/to/AppData
   ```
   This command will merge AppData JSON files for result views. You can specify the directory containing the JSON files using the `--appdata-dir` option. If not specified, the tool will look for the AppData directory relative to the script location.

### Pivot CSV Files

3. To pivot a CSV file to be wide in the year column:
   ```bash
   austimes-tools pivot-csv path/to/input.csv
   ```
   This command will read the CSV file, pivot it to be wide in the year column, drop the "val~den" column if present, and save the result as "input-wide.csv" in the same directory.
