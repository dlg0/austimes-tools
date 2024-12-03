import rich_click as click
import pandas as pd
from pathlib import Path
from loguru import logger
import sys

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO")  # Add handler with stderr as sink

def calculate_fuel_switching_logic(file_path: Path | str) -> None:
    """Calculate fuel switching metrics from a CSV or Excel file.
    
    Args:
        file_path: Path to the CSV or Excel file containing fuel switching data
    """
    input_path = Path(file_path).resolve()
    cache_path = input_path.parent / f"{input_path.stem}_cache.pkl"
    
    # Check for cached data
    if cache_path.exists():
        logger.info(f"Loading cached data from: {cache_path}")
        try:
            df = pd.read_pickle(cache_path)
            return df
        except Exception as e:
            logger.warning(f"Failed to load cache, reading original file. Error: {e}")
    
    # Original file reading logic
    logger.info(f"Reading file: {input_path}")
    if input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
    elif input_path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(input_path)
    else:
        raise ValueError("File must be CSV or Excel (.csv, .xlsx, .xls)")
    
    # Cache the dataframe
    logger.info(f"Caching data to: {cache_path}")
    df.to_pickle(cache_path)
    
    # TODO: Add fuel switching calculations here
    
    # Save output to same directory as input
    output_path = input_path.parent / f"{input_path.stem}_fuel_switching{input_path.suffix}"
    df.to_excel(output_path, index=False)
    logger.info(f"Saved fuel switching calculations to: {output_path}")

@click.command()
@click.argument('input_file', type=click.Path(exists=True))
def calculate_fuel_switching(input_file):
    """Calculate fuel switching metrics from an Excel file.
    
    [bold green]Arguments:[/]
    
    [yellow]input_file[/]: Path to the Excel file containing fuel switching data
    
    [bold blue]Description:[/]
    
    This tool calculates fuel switching metrics from an input Excel file and saves the results
    to a new Excel file in the same directory.
    """
    calculate_fuel_switching_logic(input_file)

if __name__ == "__main__":
    calculate_fuel_switching() 