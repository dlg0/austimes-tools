import os
import pandas as pd
import re
import click
from loguru import logger


@click.command()
def load_luto_data():
    input_dir = "data/luto/20241010"
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "luto_processed_data.xlsx")
    all_data = []

    for filename in os.listdir(input_dir):
        if filename.endswith(".xlsx") and not filename.startswith("~"):
            # Log the filename
            logger.info(f"Processing file: {filename}")

            # Extract parameters from filename
            carbon_price = re.search(r"cp(\d+)", filename).group(1)
            hurdle_rate = re.search(r"hr(\d+)", filename).group(1)
            cap_constraint = "On" if "capConOn" in filename else "Off"

            # Load Excel file
            file_path = os.path.join(input_dir, filename)
            df = pd.read_excel(file_path, engine="openpyxl")

            # Filter for total carbon sequestration row
            total_carbon_row = df[df.iloc[:, 0] == "Total carbon sequestration (tCO2e)"].copy()

            # Drop the first column
            total_carbon_row = total_carbon_row.drop(columns=[total_carbon_row.columns[0]])

            # Add metadata columns to the left of the dataframe
            total_carbon_row.insert(0, "Carbon Price", carbon_price)
            total_carbon_row.insert(1, "Hurdle Rate", hurdle_rate)
            total_carbon_row.insert(2, "Capacity Constraint", cap_constraint)

            # Convert to millions of tonnes
            numeric_columns = total_carbon_row.columns[3:]  # Skip the metadata columns
            total_carbon_row.loc[:, numeric_columns] = total_carbon_row.loc[:, numeric_columns].div(1e6, axis=0)

            all_data.append(total_carbon_row)

    # Concatenate all data
    result_df = pd.concat(all_data, ignore_index=True)

    # Drop rows where the capacity constraint is Off
    result_df = result_df[result_df["Capacity Constraint"] == "On"]

    # Drop the capacity constraint column
    result_df = result_df.drop(columns=["Capacity Constraint"])

    # Convert numeric columns
    icol_year1 = 2
    year_columns = result_df.columns[icol_year1:]  # Skip metadata columns
    result_df[year_columns] = result_df[year_columns].apply(pd.to_numeric, errors="coerce")

    # Set the dtype of Carbon Price, Hurdle Rate, and Capacity Constraint to int
    result_df["Carbon Price"] = result_df["Carbon Price"].astype(int)
    result_df["Hurdle Rate"] = result_df["Hurdle Rate"].astype(int)

    # reset the index
    result_df = result_df.reset_index(drop=True)
 
    # For each hurdle rate
    # For each carbon price
    # Subtracte the value from the previous carbon price in a new dataframe
    result_diff_df = result_df.copy()
    for hurdle_rate in result_df["Hurdle Rate"].unique():
        for i, carbon_price1 in enumerate(sorted(result_df["Carbon Price"].unique())):
            if carbon_price1 > min(result_df["Carbon Price"].unique()):
                carbon_price2 = sorted(result_df["Carbon Price"].unique())[i - 1]
                logger.info(f"Hurdle Rate: {hurdle_rate}, Carbon Price1: {carbon_price1}, Carbon Price2: {carbon_price2}")
                locs1 = (result_df["Hurdle Rate"] == hurdle_rate) & (result_df["Carbon Price"] == carbon_price1)
                locs2 = (result_df["Hurdle Rate"] == hurdle_rate) & (result_df["Carbon Price"] == carbon_price2)
                # get the index of the rows
                index1 = result_df.loc[locs1].index
                data1 = result_df.loc[locs1, year_columns].reset_index(drop=True)
                data2 = result_df.loc[locs2, year_columns].reset_index(drop=True)
                tmp = data1.sub(data2, axis=1)
                result_diff_df.iloc[index1, icol_year1:] = tmp
            else:
                logger.info(f"Skipping Hurdle Rate: {hurdle_rate}, Carbon Price1: {carbon_price1}")


    # Calculate max sequestration for each scenario
    result_diff_df["Max Sequestration"] = result_diff_df[year_columns].max(axis=1)

    # Melt the year columns into a single column
    result_diff_df = result_diff_df.melt(
        id_vars=["Carbon Price", "Hurdle Rate", "Max Sequestration"],
        value_vars=year_columns,
        var_name="Year",
        value_name="Sequestration [MtCO2e]",
    )

    # Reset the index
    result_diff_df = result_diff_df.reset_index(drop=True)
    
    # Calculate normalized sequestration
    result_diff_df["SHAPE"] = result_diff_df["Sequestration [MtCO2e]"].div(result_diff_df["Max Sequestration"])

    # Create a new column which is the year - min year + 1
    result_diff_df["SHAPE_Year"] = result_diff_df["Year"].astype(int) - min(result_diff_df["Year"].astype(int)) + 1

    # Reverse sort by Carbon Price, Hurdle Rate
    result_diff_df = result_diff_df.sort_values(
        by=["Hurdle Rate", "Carbon Price"]
    )

    # Create a new table for the updated max_value per carbon price and hurdle rate
    veda_max_value_df = result_diff_df[
        ["Carbon Price", "Hurdle Rate", "Max Sequestration"]
    ].copy()

    # Drop duplicates
    veda_max_value_df = veda_max_value_df.drop_duplicates()

    # Create a new table for the VEDA_SHAPE values
    veda_shape_df = result_diff_df[["Carbon Price", "Hurdle Rate", "SHAPE_Year", "SHAPE"]].copy()

    # Collect all the rename statements
    rename_statements = {
        "Carbon Price": "other_indexes",
        "SHAPE": "AllRegions",
        "SHAPE_Year": "Year"
    }

    # Rename the columns
    veda_shape_df.rename(columns=rename_statements, inplace=True)

    # Move hurdle rate to the front
    veda_shape_df = veda_shape_df[["Hurdle Rate", "other_indexes", "AllRegions", "Year"]]

    # Add an empty column after hurdle rate
    veda_shape_df.insert(1, " ", "")

    # Sort by other_indexes and then by Year
    veda_shape_df = veda_shape_df.sort_values(by=["Hurdle Rate", "other_indexes", "Year"])


    # Save each of the dataframes to a separate sheet in the same excel file
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        result_diff_df.to_excel(writer, sheet_name="Processed_Data", index=False)
        veda_shape_df.to_excel(writer, sheet_name="VEDA_SHAPE", index=False)
        veda_max_value_df.to_excel(writer, sheet_name="VEDA_Max_Sequestration", index=False)
    click.echo(f"Data processed and saved to {output_file}")


if __name__ == "__main__":
    load_luto_data()
