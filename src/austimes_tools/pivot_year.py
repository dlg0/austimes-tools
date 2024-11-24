import click
import polars as pl
from pathlib import Path
from loguru import logger
import sys

# initialise logger to screen
logger.add(sys.stdout, level="INFO")


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def pivot_file(file_path):
    """
    Pivot a CSV or Excel file to be wide in the year column.

    FILE_PATH is the path to the input file to be pivoted (supports .csv, .xlsx, .xls).
    """
    try:
        # Convert to Path object
        file_path = Path(file_path)

        # Read the file based on extension
        logger.info(f"Reading file: {file_path}")
        if file_path.suffix.lower() == ".csv":
            df = pl.read_csv(file_path)
            value_col = "val"
            # Drop 'val~den' column if it exists
            if "val~den" in df.columns:
                df = df.drop("val~den")
        elif file_path.suffix.lower() in [".xlsx", ".xls"]:
            df = pl.read_excel(file_path)
            value_col = "value"
        else:
            raise ValueError("File must be CSV or Excel (.csv, .xlsx, .xls)")

        # Check if 'year' column exists
        if "year" not in df.columns:
            raise ValueError("CSV must contain a 'year' column")

        # Check if value column exists
        if value_col not in df.columns:
            raise ValueError(f"File must contain a '{value_col}' column")

        # Pivot the dataframe
        logger.info("Pivoting dataframe")
        index_cols = [col for col in df.columns if col not in ["year", value_col]]
        df_wide = df.pivot(values=value_col, index=index_cols, columns="year")

        # Create output filename with -wide suffix
        output_path = file_path.parent / f"{file_path.stem}-wide{file_path.suffix}"

        # Save the pivoted dataframe in same format as input
        logger.info(f"Saving pivoted file to: {output_path}")
        if file_path.suffix.lower() == ".csv":
            df_wide.write_csv(output_path)
        else:
            df_wide.write_excel(output_path)

        click.echo(f"Successfully pivoted file and saved to: {output_path}")

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise click.ClickException(str(e))


if __name__ == "__main__":
    pivot_file()
