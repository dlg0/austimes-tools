import click
from pathlib import Path
import pandas as pd
from loguru import logger
import sys

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO")  # Add handler with stderr as sink

# Add this mapping dictionary before the main function
SHEET_NAME_MAPPING = {
    'CO2 emissions - Industry - Process': 'MSM22 CO2 emis-ind-proc',
    'CO2 emissions - non bldg+ind': 'MSM22 emis-non-bldg+ind',
    'CO2 emissions Commercial': 'MSM22 Commercial FE with EnInt',
    'CO2 emissions Industry': 'MSM22 Industry FE with EnInt',
    'Elec capacity and generation': 'MSM22 Elec cap and gen',
    'Elec fuels': 'MSM22 Elec fuels',
    'EnEff Buildings': 'MSM22 EnEff Buildings',
    'EnEff Industry': 'MSM22 EnEff Industry',
    'Fin Energy Commercial': 'MSM22 Commercial FE with EnInt',
    'Fin Energy Industry': 'MSM22 Industry FE with EnInt',
    'Fin Energy Residential': 'MSM22 Fin energy res',
    'Fin energy Transport': 'MSM22 Fin energy tra',
    'Fuels switched industry': 'MSM22 Industry FE with EnInt',
    'Hydrogen capacity and generation': 'MSM22 h2-cap-and-gen',
    'Hydrogen exports': 'MSM22 Hydrogen exports',
    'Hydrogen fuels': 'MSM22 Hydrogen fuels'
}

@click.command()
@click.argument('input_file', type=click.Path(exists=True))
def create_msm22_csvs(input_file):
    """Create CSV files from MSM22 Excel sheets."""
    try:
        input_path = Path(input_file)
        output_path = input_path.parent  # Output path is the same as input file's directory
        
        logger.info(f"Reading Excel file: {input_path}")
        
        # Read all sheets from the Excel file
        excel_file = pd.ExcelFile(input_path)
        
        # Process each sheet
        for sheet_name in excel_file.sheet_names:
            if sheet_name == 'Info':
                logger.info(f"Skipping Info sheet")
                continue
                
            logger.info(f"Processing sheet: {sheet_name}")
            
            # Read the sheet, skipping the first row
            df = pd.read_excel(excel_file, sheet_name=sheet_name, skiprows=1)

            # Rename "GrandTotal" to "val" (if it exists)
            if "GrandTotal" in df.columns:
                df.rename(columns={"GrandTotal": "val"}, inplace=True)

            # Drop the model and study columns
            if "model" in df.columns:
                df.drop(columns=["model"], inplace=True)
            if "study" in df.columns:
                df.drop(columns=["study"], inplace=True)

            # Rename source_p to source, sector_p to sector (if they exist)
            if "source_p" in df.columns:
                df.rename(columns={"source_p": "source"}, inplace=True)
            if "sector_p" in df.columns:
                df.rename(columns={"sector_p": "sector"}, inplace=True)

            # Replace all "-" with missing values
            df.replace('-', pd.NA, inplace=True)

            # Override "fuel" column with "fuel_override" values if present
            if "fuel_override" in df.columns:
                df['fuel'] = df['fuel_override'].fillna(method='bfill')
                df.drop(columns=["fuel_override"], inplace=True)

            # Override "isp_subregion" column with "isp_subregion_override" values if present
            if "isp_subregion_override" in df.columns:
                df['isp_subregion'] = df['isp_subregion_override'].fillna(method='bfill')
                df.drop(columns=["isp_subregion_override"], inplace=True)
            # Use the mapping dictionary to get the new filename
            for mapped_name, original_name in SHEET_NAME_MAPPING.items():
                if sheet_name == original_name:
                    csv_path = output_path / f"{mapped_name}.csv"
                    df.to_csv(csv_path, index=False)
                    logger.info(f"Created CSV file: {csv_path}")
                    break
            else:
                # Fall back to the original sanitization for unmapped sheets
                safe_name = "".join(c if c.isalnum() else "_" for c in sheet_name.lower())
                safe_name = safe_name.replace("msm22_", "")
                csv_path = output_path / f"{safe_name}.csv"
                df.to_csv(csv_path, index=False)
                logger.warning(f"No mapping found for sheet '{sheet_name}', using sanitized name: {csv_path}")
        
        click.echo(f"Successfully created CSV files in: {output_path}")
        
    except Exception as e:
        logger.error(f"Error processing Excel file: {e}")
        raise click.ClickException(str(e))

if __name__ == "__main__":
    create_msm22_csvs() 