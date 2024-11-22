import click
import pandas as pd
from pathlib import Path
from loguru import logger

@click.command()
@click.argument('csv_path', type=click.Path(exists=True))
def pivot_csv(csv_path):
    """
    Pivot a CSV file to be wide in the year column.
    
    CSV_PATH is the path to the input CSV file to be pivoted.
    """
    try:
        # Convert to Path object
        file_path = Path(csv_path)
        
        # Read the CSV
        logger.info(f"Reading CSV file: {file_path}")
        df = pd.read_csv(file_path)
        
        # Check if 'year' column exists
        if 'year' not in df.columns:
            raise ValueError("CSV must contain a 'year' column")
            
        # Drop 'val~den' column if it exists
        if 'val~den' in df.columns:
            df = df.drop(columns=['val~den'])
            
        # Pivot the dataframe
        logger.info("Pivoting dataframe")
        cols_except_year = [col for col in df.columns if col != 'year']
        df_wide = df.pivot(columns='year', values=cols_except_year[0])
        
        # Create output filename with -wide suffix
        output_path = file_path.parent / f"{file_path.stem}-wide{file_path.suffix}"
        
        # Save the pivoted dataframe
        logger.info(f"Saving pivoted CSV to: {output_path}")
        df_wide.to_csv(output_path)
        
        click.echo(f"Successfully pivoted CSV and saved to: {output_path}")
        
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        raise click.ClickException(str(e))

if __name__ == "__main__":
    pivot_csv() 