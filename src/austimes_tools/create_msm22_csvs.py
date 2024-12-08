import rich_click as click
from pathlib import Path
import pandas as pd
from loguru import logger
import sys
import numpy as np
import shutil
from openpyxl import load_workbook
from datetime import datetime
import re

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO")  # Add handler with stderr as sink

FIRST_YEAR = 2025

TEMPLATE_PATH = (
    Path(__file__).parent.parent.parent
    / "data"
    / "msm22-output-templates"
    / "FE_template.xlsx"
)

CSV_COLUMN_ORDER_MAPPING = {
    "Elec fuels": ["model", "study", "region", "isp_subregion", "year", "unit", "varbl", "fuel", "scen", "tech", "val"],
    "CO2 emissions - non bldg+ind": ["model", "region", "isp_subregion", "year", "unit", "emission_type", "enduse", "scen", "sector", "state", "subsector_p", "tech", "val"],
    "CO2 emissions - Industry - Process": ["region", "isp_subregion", "year", "unit", "ee_category", "endusegroup_p", "scen", "source", "val"],
    "Elec capacity and generation": ["model", "study", "region", "isp_subregion", "year", "unit", "varbl", "fuel", "scen", "tech", "val"],
    "EnEff Buildings": ["model", "study", "region", "isp_subregion","year", "unit", "varbl", "buildingtype", "ee_category", "enduse", "fuel", "scen", "source", "val"],
    "EnEff Industry": ["model", "study", "region", "isp_subregion", "year", "unit", "varbl", "ee_category", "fuel", "nemreg", "scen", "source", "subsectorgroup_c", "val"],
    "Fin Energy Residential": ["model", "study", "region", "isp_subregion", "year", "unit", "varbl", "enduse", "fuel", "fuel_switched", "scen", "source", "subsector_p", "val"],
    "Fin energy Transport": ["region", "isp_subregion","year", "unit", "varbl", "enduse", "fuel", "scen", "subsector_p", "tech", "val"],
    "Fuels switched industry": ["sector", "scen", "region", "isp_subregion", "year", "source", "subsectorgroup_c", "fuel_switched_from", "fuel_switched_to", "hydrogen_source", "PJ_switched"],
    "Hydrogen capacity and generation": ["model", "study", "region", "year", "unit", "varbl", "process", "scen", "tech", "val"],
    "Hydrogen exports": ["model", "study", "region", "year", "unit", "varbl", "scen", "val"],
    "Hydrogen fuels": ["model", "study", "region", "year", "unit", "varbl", "process", "commodity", "fuel", "scen", "tech", "val"],
}

CSV_TO_FILTER_OUT_MAPPING = {
    "CO2 emissions - Industry - Process": [{"source":["-"]}],
}


# Add this mapping dictionary before the main function
SHEET_NAME_MAPPING = {
    "MSM22 CO2 emis-ind-proc": "CO2 emissions - Industry - Process",
    "MSM22 emis-non-bldg+ind": "CO2 emissions - non bldg+ind",
    "MSM22 Commercial FE with EnInt": "Fin Energy Commercial",
    "MSM22 Industry FE with EnInt": "Fin Energy Industry",
    "MSM22 Elec cap and gen": "Elec capacity and generation",
    "MSM22 Elec fuels": "Elec fuels",
    "MSM22 EnEff Buildings": "EnEff Buildings",
    "MSM22 EnEff Industry": "EnEff Industry",
    "MSM22 Fin energy res": "Fin Energy Residential",
    "MSM22 Fin energy tra": "Fin energy Transport",
    "MSM22 Industry FE with EnInt": "Fuels switched industry",
    "MSM22 h2-cap-and-gen": "Hydrogen capacity and generation",
    "MSM22 Hydrogen exports": "Hydrogen exports",
    "MSM22 Hydrogen fuels": "Hydrogen fuels",
    "MSM22-ind2-emissions": "IND2 emissions",
}

# Add this near the top of the file with other imports
pd.set_option("future.no_silent_downcasting", True)

def is_valid_results_file(filename: str) -> bool:
    """Check if filename matches the results_YYYYMMDD-HHMMSS.xlsx pattern."""
    pattern = r"results_\d{8}-\d{6}\.xlsx$"
    return bool(re.match(pattern, filename))

def extract_datetime(filename: str) -> datetime:
    """Extract datetime from results filename."""
    # Extract YYYYMMDD-HHMMSS from the filename
    date_str = re.search(r"(\d{8}-\d{6})", filename).group(1)
    return datetime.strptime(date_str, "%Y%m%d-%H%M%S")

def process_msm22_csvs(input_dir: Path | str) -> None:
    """Process MSM22 files from a directory and create CSVs.

    Args:
        input_dir: Path to directory containing MSM22 Excel files
    """
    input_path = Path(input_dir).resolve()
    output_path = input_path

    logger.info(f"Reading Excel files from: {input_path}")

    # Initialize DataFrames to store combined data for each sheet type
    combined_data = {}

    # Find all Excel files in directory that match the pattern
    excel_files = [
        f for f in input_path.glob("*.xlsx") 
        if is_valid_results_file(f.name)
    ]
    
    if not excel_files:
        logger.info(f"Files found in directory: {[f.name for f in input_path.glob('*.xlsx')]}")
        raise ValueError(f"No valid results files found in {input_path}")

    # Sort files by datetime (oldest first)
    excel_files.sort(key=lambda x: extract_datetime(x.name))
    
    logger.info(f"Found {len(excel_files)} valid results files")
    for file in excel_files:
        logger.info(f"  {file.name} ({extract_datetime(file.name)})")

    # Process each Excel file
    for excel_path in excel_files:
        logger.info(f"Processing file: {excel_path}")
        excel_file = pd.ExcelFile(excel_path)

        for sheet_name in excel_file.sheet_names:
            if sheet_name == "Info":
                logger.info(f"Skipping Info sheet")
                continue

            logger.info(f"Processing sheet: {sheet_name}")
            df = pd.read_excel(excel_file, sheet_name=sheet_name, skiprows=1)

            df_raw = df.copy(deep=True)

            # Convert year column to numeric, coercing errors to NaN
            df["year"] = pd.to_numeric(df["year"], errors="coerce")

            # Drop any rows where year is < FIRST_YEAR
            df = df[df["year"] >= FIRST_YEAR]

            # Replace "-" with NaN
            df = df.replace("-", np.nan)

            # Override fuel
            if "fuel_override" in df.columns:
                logger.info(f"Overriding fuel")
                mask = df["fuel_override"].notna()
                df.loc[mask, "fuel"] = df.loc[mask, "fuel_override"]
                df = df.drop(columns=["fuel_override"])

            # Override isp_subregion
            if "isp_subregion_override" in df.columns and "isp_subregion" in df.columns:
                logger.info(f"Overriding isp_subregion")
                mask = df["isp_subregion_override"].notna()
                df.loc[mask, "isp_subregion"] = df.loc[mask, "isp_subregion_override"]
                df = df.drop(columns=["isp_subregion_override"])

            # Rename columns
            df = df.rename(
                columns={"source_p": "source", "sector_p": "sector", "GrandTotal": "val"}
            )

            # Replace NaN with "-"
            df = df.fillna("-")

            if df.empty:
                logger.error(f"Empty DataFrame for sheet '{sheet_name}', skipping")
                continue

            # Get the CSV name and column order
            csv_name = SHEET_NAME_MAPPING.get(sheet_name, None)
            if csv_name is None:
                logger.warning(f"No CSV name found for {sheet_name}, skipping")
                continue

            column_order = CSV_COLUMN_ORDER_MAPPING.get(csv_name, None)
            if column_order is None:
                logger.info(f"No column order found for {csv_name}, skipping")
                continue

            # Check columns
            if not all(col in df.columns for col in column_order):
                logger.error(f"Column mismatch in {sheet_name}:")
                logger.error(f"Found columns: {sorted(list(df.columns))}")
                logger.error(f"Expected columns: {sorted(column_order)}")
                # list the missing columns
                missing_cols = [col for col in column_order if col not in df.columns]
                logger.error(f"Missing columns: {sorted(missing_cols)}")
                continue
            # Reorder columns
            df = df[column_order]

            # Add to combined data - newer files will overwrite older ones
            csv_name = SHEET_NAME_MAPPING.get(sheet_name)

            # Group by all columns except val and sum
            df = df.groupby(column_order[:-1], as_index=False).sum()

            # Check for nans
            if df.isna().any().any():
                logger.error(f"NaN values found in {csv_name}, skipping CSV creation")
                continue

            # Filter out rows
            if csv_name in CSV_TO_FILTER_OUT_MAPPING:
                for filter_dict in CSV_TO_FILTER_OUT_MAPPING[csv_name]:
                    logger.info(f"Filtering out rows with {filter_dict}")
                    # Log unique values in each filter column
                    for col, values in filter_dict.items():
                        unique_vals = df[col].unique()
                        logger.info(f"Unique values in {col}: {unique_vals}")
                        # Remove entire rows where this column matches any of the filtered values
                        rows_before = len(df)
                        df = df[~df[col].isin(values)]
                        rows_removed = rows_before - len(df)
                        logger.info(f"Filtered out {rows_removed} rows where {col} matched {values}")
                        # log new unique values
                        new_unique_vals = df[col].unique()
                        logger.info(f"New unique values in {col}: {new_unique_vals}")

            csv_path = output_path / f"{csv_name}.csv"
            df.to_csv(csv_path, index=False)
            logger.info(f"Created CSV file: {csv_path}")

def process_energy_intensity(input_file: Path | str) -> None:
    """Process energy intensity files from a single Excel file.

    Args:
        input_file: Path to the input Excel file
    """
    input_path = Path(input_file).resolve()
    output_path = input_path.parent

    logger.info("Starting energy intensity file processing...")
    
    # ... (rest of the energy intensity processing code remains the same,
    #      starting from the do_energy_intensity_processing section)
    # ... (copy the existing energy intensity processing code here)

@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--process-energy/--no-process-energy",
    default=False,
    help="Process energy intensity files after creating CSVs",
)
@click.option(
    "--energy-file",
    type=click.Path(exists=True),
    help="Excel file to process for energy intensity (required if --process-energy is set)",
)
def process_msm22_files(input_path, process_energy, energy_file):
    """Process MSM22 files - creates CSVs and optionally processes energy intensity files.

    [bold green]Arguments:[/]

    [yellow]input_path[/]: Path to directory containing MSM22 Excel files

    [bold blue]Description:[/]

    This tool performs two operations:
    1. Converts all sheets from all MSM22 Excel files in the directory into combined CSV files
    2. Optionally processes the energy intensity sheets from a specific file
    """
    process_msm22_csvs(input_path)
    
    if process_energy:
        if not energy_file:
            raise click.UsageError("--energy-file is required when --process-energy is set")
        process_energy_intensity(energy_file)

if __name__ == "__main__":
    input_dir = Path(
        "D:/gre538/Model_Aus_TIMES-msm24-004a/Exported_files/"
    ).resolve()
    
    process_msm22_csvs(input_dir)  # For CLI
