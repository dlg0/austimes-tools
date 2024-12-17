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


# Fuel Switching Calculation Methodology

The fuel switching calculation determines how much fuel consumption which would have occured had the future production been met by the current day fuel mix is avoided. The fuel consumption which would have occured based on the current day mix of fuels is referred to as the counterfactual or baseline fuel consumption. The analysis examines the difference between the counterfactual and the model solution, and does this on an every-fuel-to-every-other-fuel basis. It reports several "entry-type"s of results (which sum to give the counterfactual energy demand). These are:

1. "electrification": Electrification (specifically switching to electricity) 
2. "fuel-switch": Fuel switching (changing from one fuel type to another)
3. "efficiency-improvement": Fuel/energy avoided due to efficiency improvements
4. "remaining-consumption": Refers to that part of actual (model solution) consumption unrelated to the 3 previous items. Note that this is NOT the actual consumption, only that part of actual consumption not accounted for by the 3 previous items.

All values are reported in PJ. The electrification and fuel-switch types are the PJ of the "fuel-switched-from" fuel (electrification is just a fuel-switch to electricity). The remaining-consumption type is how much of that fuel was unrelated to the fuel switching.

## Sector Coverage

The calculation covers the following sectors:

- Industry (ES prefix, and new industry prefixes (`im_`, `inm_`, `pc_`)
- Commercial (CS prefix)
- Residential (RS prefix)

## General Approach

For each sector, the calculation:

1. Establishes baseline energy consumption patterns
   - For ES, CS, and RS, this is established by the model inputs (and is embedded in the model solution by examining the sum of the `FinEn_AEMO_eneff` and `FinEn_enser` variables)
   - For new industry, this is established in the `calculate_fuel_switching.py` script by multiplying the current day fuel mix by the ration of future production to current day production (in mt using the `UCrepI_Activity-*` reporting variables)
2. Identifies changes in fuel consumption over time
3. Categorizes changes into:
   - Direct fuel switches (e.g., gas to hydrogen)
   - Electrification
   - Energy efficiency improvements
   - Remaining baseline consumption

## New Industry Methodology

The heavy industry sector requires special handling. The calculation:

1. Groups processes by subsector (Alumina, Aluminum, Cement+, PetChem, Iron and Steel)
2. For regions where there is present day production, scales the present day fuel mix 
   - Note that for regions where there is no present day production - which only occurs for Iron & Steel, there is no fuel switching
3. Differences the baseline and actual for each process group
4. Accounts for both:
   - Single fuel to single fuel switches
   - Single fuel to multiple fuel switches assuming the fraction of the from_fuel switched to a particular to_fuel is the relative fraction of that to_fuel in the total difference of all to_fuels. 
   - Multiple fuel to single fuel switches
   - Multiple fuel to multiple fuel switches, which assumes the relative fraction of the total difference in both the from and to directions to assign the fractions of from fuels to to fuels. 

## Output Structure

Results are provided in a table with the following columns:

- `scen`: The scenario name
- `region`: The region name
- `sector`: The subsector group name
- `hydrogen_source`: The hydrogen source (if applicable)
- `unit`: The unit of measure
- `from_fuel`: The original fuel type
- `to_fuel`: The new fuel type
- `process`: The process/sector where switch occurred
- `entry_type`: The type of change (remaining consumption, fuel switch, or electrification)
- `value`: The quantity of energy affected
- `year`: The year of change
