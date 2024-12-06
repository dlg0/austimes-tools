import rich_click as click
from pathlib import Path
import pandas as pd
from loguru import logger
import sys
import numpy as np
import shutil
from openpyxl import load_workbook

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
    "Elec fuels": ["model", "study", "region", "year", "unit", "varbl", "fuel", "scen", "tech", "val"],
}


# Add this mapping dictionary before the main function
SHEET_NAME_MAPPING = {
    "MSM22 CO2 emis-ind-proc": "CO2 emissions - Industry - Process",
    "MSM22 emis-non-bldg+ind": "CO2 emissions - non bldg+ind",
    "MSM22 Commercial FE with EnInt": "CO2 emissions Commercial",
    "MSM22 Industry FE with EnInt": "CO2 emissions Industry",
    "MSM22 Elec cap and gen": "Elec capacity and generation",
    "MSM22 Elec fuels": "Elec fuels",
    "MSM22 EnEff Buildings": "EnEff Buildings",
    "MSM22 EnEff Industry": "EnEff Industry",
    "MSM22 Commercial FE with EnInt": "Fin Energy Commercial",
    "MSM22 Industry FE with EnInt": "Fin Energy Industry",
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


def process_msm22_files_logic(input_file: Path | str) -> None:
    """Process MSM22 files - creates CSVs and processes energy intensity files.

    Args:
        input_file: Path to the input Excel file
    """
    input_path = Path(input_file).resolve()
    output_path = input_path.parent

    logger.info(f"Reading Excel file: {input_path}")

    # Part 1: Create CSV files
    logger.info("Starting CSV creation...")
    excel_file = pd.ExcelFile(input_path)

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
            # Only replace fuel where fuel_override is not NaN
            mask = df["fuel_override"].notna()
            df.loc[mask, "fuel"] = df.loc[mask, "fuel_override"]
            # drop fuel_override
            df = df.drop(columns=["fuel_override"])

        # Override isp_subregion
        if "isp_subregion_override" in df.columns and "isp_subregion" in df.columns:
            # Only replace isp_subregion where isp_subregion_override is not NaN
            mask = df["isp_subregion_override"].notna()
            df.loc[mask, "isp_subregion"] = df.loc[mask, "isp_subregion_override"]
            # drop isp_subregion_override
            df = df.drop(columns=["isp_subregion_override"])

        # Rename columns as source_p to source and sector_p to sector
        df = df.rename(
            columns={"source_p": "source", "sector_p": "sector", "GrandTotal": "val"}
        )

        # Replace NaN with "-"
        df = df.fillna("-")

        # Check if DataFrame is empty before writing CSV
        if df.empty:
            logger.error(f"Empty DataFrame for sheet '{sheet_name}', skipping CSV creation")
            continue

        # Get the column order for the sheet
        csv_name = SHEET_NAME_MAPPING.get(sheet_name, None)
        if csv_name is None:
            logger.warning(f"No CSV name found for {sheet_name}, skipping CSV creation")
            continue

        column_order = CSV_COLUMN_ORDER_MAPPING.get(csv_name, None)
        if column_order is None:
            logger.info(f"No column order found for {sheet_name}, skipping CSV creation")
            logger.info(f"CSV name: {csv_name}")
            continue

        # Check all columns in column_order are in df.columns
        if not all(col in df.columns for col in column_order):
            print(f"Expected: {column_order}")
            print(f"Actual: {df.columns.tolist()}")
            logger.error(f"Missing columns: {set(column_order) - set(df.columns.tolist())}")
            raise ValueError(f"Missing columns in {sheet_name}")

        # Reorder columns if column_order is provided
        if column_order:
            df = df[column_order]

        # Run a groupby on all columns except val and sum
        df = df.groupby(column_order[:-1], as_index=False).sum()

        # Check for nans
        if df.isna().any().any():
            logger.error(f"NaN values found in {csv_name}, skipping CSV creation")
            continue

        csv_path = output_path / f"{csv_name}.csv"
        df.to_csv(csv_path, index=False)
        logger.info(f"Created CSV file: {csv_path}")



    do_energy_intensity_processing = False
    if do_energy_intensity_processing:
        # Part 2: Process energy intensity files
        logger.info("Starting energy intensity file processing...")
        target_sheets = ["MSM22 Commercial FE with EnInt", "MSM22 Industry FE with EnInt"]

        sheet_mapping = {
            "MSM22 Commercial FE with EnInt": "Commercial FE with EnInt",
            "MSM22 Industry FE with EnInt": "Industry FE with EnInt",
        }

        emissions_csv_names = ["CO2 emissions Commercial", "CO2 emissions Industry"]

        fin_energy_csv_names = ["Final Energy Commercial", "Final Energy Industry"]

        commercial_cols = [
            "sector_p",
            "scen",
            "region",
            "year",
            "enduse",
            "source_p",
            "buildingtype",
            "fuel_switched",
            "fuel",
        ]
        industry_cols = [
            "sector_p",
            "scen",
            "region",
            "year",
            "source_p",
            "hydrogen_source",
            "subsectorgroup_c",
            "fuel",
        ]

        if not TEMPLATE_PATH.exists():
            raise ValueError(f"Template file not found at: {TEMPLATE_PATH}")

        # Copy template file to destination first
        output_file = output_path / f"FE_processed_{input_path.resolve().stem}.xlsx"
        template_wb = pd.ExcelFile(TEMPLATE_PATH)

        # Copy template file to new location
        shutil.copy2(TEMPLATE_PATH, Path(output_file).resolve())

        # Now read the data we want to insert
        processed_dfs = {}
        for sheet_name in target_sheets:
            if sheet_name not in pd.ExcelFile(input_path).sheet_names:
                logger.warning(f"Sheet '{sheet_name}' not found in input file, skipping...")
                continue

            logger.info(f"Processing energy intensity sheet: {sheet_name}")
            df = pd.read_excel(input_path, sheet_name=sheet_name, skiprows=1)
            df = df.replace("-", np.nan)
            # drop any rows where year is < 2025
            df = df[df["year"] >= FIRST_YEAR]
            # override the isp_subregion
            if "isp_subregion_override" in df.columns and "isp_subregion" in df.columns:
                df["isp_subregion"] = df["isp_subregion_override"].bfill()
                # drop isp_subregion_override
                df = df.drop(columns=["isp_subregion_override"])
            processed_dfs[sheet_name] = df

        # Use openpyxl to update only the data cells while preserving formulas
        wb = load_workbook(output_file)

        # Before pasting, check that the column names match

        for source_sheet, processed_df in processed_dfs.items():
            target_sheet = sheet_mapping[source_sheet]
            ws = wb[target_sheet]
            template_columns = [col.value for col in ws[1]]
            processed_columns = processed_df.columns.tolist()[0:12]
            template_columns = template_columns[0:12]
            if template_columns != processed_columns:
                print(template_columns)
                print(processed_columns)
                raise ValueError(
                    f"Column names do not match for {source_sheet} and {target_sheet}"
                )

        for source_sheet, processed_df in processed_dfs.items():
            target_sheet = sheet_mapping[source_sheet]
            ws = wb[target_sheet]

            # Convert DataFrame to values and update cells directly
            data_values = processed_df.values
            for i, row in enumerate(data_values):
                for j, value in enumerate(row):
                    if pd.notna(value):  # Only update non-NA values
                        ws.cell(
                            row=i + 2, column=j + 1, value=value
                        )  # +2 because Excel is 1-based and we have header

            # Our data may be shorter than the template, so we need to delete any extra rows at the bottom
            max_row = ws.max_row
            if max_row > len(data_values) + 1:
                rows_to_delete = max_row - (len(data_values) + 1)
                logger.info(f"Deleting {rows_to_delete} rows from the bottom")
                ws.delete_rows(len(data_values) + 2, rows_to_delete)
            # If ours is longer, throw and error to say how many more rows we need to copy the formula down in columns M:P
            if max_row < len(data_values) + 1:
                raise ValueError(
                    f"Our data is longer than the template by {len(data_values) + 1 - max_row} rows. Please copy the formula down in columns M:P in the template and try again."
                )

        wb.save(output_file)

        # use xlwings to open the file and force recalculation of formulas
        try:
            import xlwings as xw

            wb = xw.Book(output_file)
            wb.save()
            wb.close()
        except Exception as e:
            logger.error(
                f"Failed to use xlwings to force recalculation of formulas - RUN IN A TERMINAL: {e}"
            )

        logger.info(f"Created processed energy intensity file: {output_file}")

        # Now we re-read in the processed file for the two target sheets, extract the data and create CSVs
        # do this for both emissions and fin energy
        for source_sheet, target_sheet in sheet_mapping.items():
            # Create emissions CSV
            logger.info(f"Creating emissions CSV for {source_sheet}")
            if target_sheet == "Commercial FE with EnInt":
                cols = commercial_cols
                emissions_csv_name = "CO2 emissions Commercial"
            else:
                cols = industry_cols
                emissions_csv_name = "CO2 emissions Industry"
            logger.info(f"Created CSV file: {output_path / f'{emissions_csv_name}.csv'}")
            df = pd.read_excel(
                output_file,
                sheet_name=target_sheet,
                usecols="A:Q",
                engine_kwargs={"data_only": True},
            )
            # Drop and rows where IESTCS_Out is NaN or missing
            df = df.dropna(subset=["IESTCS_Out"])

            # Log the columns
            logger.info(f"Columns: {df.columns.tolist()}")

            # Drop IESTCS_EnInt, IESTCS_Out, EnInt, PJ
            emissions_df = df[cols + ["kt"]]

            # Group by cols and sum
            emissions_df = emissions_df.groupby(cols, as_index=False).sum()
            emissions_df = emissions_df.rename(
                columns={"source_p": "source", "sector_p": "sector"}
            )
            # Check if DataFrame is empty before writing CSV
            if emissions_df.empty:
                logger.error(f"Empty DataFrame for {emissions_csv_name}, skipping CSV creation")
            else:
                emissions_df.to_csv(output_path / f"{emissions_csv_name}.csv", index=False)
            # Create fin energy CSV
            logger.info(f"Creating fin energy CSV for {source_sheet}")
            if target_sheet == "Commercial FE with EnInt":
                cols = commercial_cols
                fin_energy_csv_name = "Final Energy Commercial"
            else:
                cols = industry_cols
                fin_energy_csv_name = "Final Energy Industry"

            fin_energy_df = df[cols + ["PJ"]]
            # Group by cols and sum
            fin_energy_df = fin_energy_df.groupby(cols, as_index=False).sum()
            fin_energy_df = fin_energy_df.rename(
                columns={"source_p": "source", "sector_p": "sector"}
            )
            # Check if DataFrame is empty before writing CSV
            if fin_energy_df.empty:
                logger.error(f"Empty DataFrame for {fin_energy_csv_name}, skipping CSV creation")
            else:
                fin_energy_df.to_csv(output_path / f"{fin_energy_csv_name}.csv", index=False)


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
def process_msm22_files(input_file):
    """Process MSM22 files - creates CSVs and processes energy intensity files.

    [bold green]Arguments:[/]

    [yellow]input_file[/]: Path to the MSM22 Excel file to process

    [bold blue]Description:[/]

    This tool performs two operations:
    1. Converts all sheets from the MSM22 Excel file into separate CSV files
    2. Processes the energy intensity sheets and creates a new Excel file

    All output files will be created in the same directory as the input file.
    """
    process_msm22_files_logic(input_file)


if __name__ == "__main__":
    input_file = Path(
        "D:/gre538/Model_Aus_TIMES-msm24-004a/Exported_files/elec-fuels-test.xlsx"
    ).resolve()
 
    process_msm22_files_logic(input_file)  # For CLI
    # For debugging, you can use:
    # process_msm22_files_logic("path/to/file.xlsx")
