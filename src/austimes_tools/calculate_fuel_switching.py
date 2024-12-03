import rich_click as click
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from loguru import logger
import sys
import re
import plotly.express as px

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

    # Filter for the variables of interest
    df = df[df["variable"].isin(["FinEn_AEMO_eneff", "FinEn_enser"])]

    # Retain only the relevant columns
    cols = ["process", "commodity", "variable", "unit", "sector0", "sector1", "fuel"]
    years = ["2025", "2030", "2035", "2040", "2045", "2050"]
    df = df[cols + years]

    # Groupby the relevant columns and sum the values
    df = df.groupby(cols).sum().reset_index()

    # Get a list of all the processes
    process_col = "commodity"
    processes = df[process_col].unique()
    # Strip the `-?` or `-??` suffix and remove duplicates
    processes = [re.sub(r"-.{1,2}$", "", p) for p in processes]
    processes = list(set(processes))
    # Loop through each process and calculate the fuel switching
    cnt = 0
    for process in processes:
        # Filter for the process
        logger.info(f"Processing: {process}")

        # Get the relevant rows for all processes which start with the process name
        df_process = df[df[process_col].str.startswith(process)]

        # Get the baseline total energy demand by simply summing all rows
        df_process_baseline = df_process.loc[:, years].sum()

        # Drop everything but years and fuel, then groupby fuel and sum
        df_process_fuel = (
            df_process[df_process["variable"] == "FinEn_enser"]
            .loc[:, years + ["fuel"]]
            .groupby("fuel")
            .sum()
            .reset_index()
        )

        # Extract the first year of df_process_fuel
        first_year_fuel_breakdown = df_process_fuel.set_index("fuel").loc[:, years[0]]

        # Do a scaling such that the first year sums to the total baseline energy demand
        scaling_factor = df_process_baseline.values[0] / first_year_fuel_breakdown.sum()
        df_process_fuel[years] = df_process_fuel[years].multiply(scaling_factor)

        # Normalise the first year of df_process_fuel to sum to 1
        first_year_fraction = first_year_fuel_breakdown / first_year_fuel_breakdown.sum()

        # Use an outer product to multiply the first year of df_process_fuel by the total baseline energy demand
        # to give a table, not a series
        df_process_fuel_baseline = pd.DataFrame(
            first_year_fraction.values[:, None] * df_process_baseline.values[None, :],
            columns=df_process_baseline.index,
            index=first_year_fuel_breakdown.index,
        ).reset_index()

        # Ensure all columns are of the same type (including the melted result)
        df_process_fuel[years] = df_process_fuel[years].astype(float)
        melted_df = df_process_fuel.melt(id_vars=["fuel"], value_vars=years)
        melted_df["value"] = melted_df["value"].astype(float)
        melted_df["variable"] = melted_df["variable"].astype(str)

        df_process_fuel_baseline[years] = df_process_fuel_baseline[years].astype(float)
        melted_df_baseline = df_process_fuel_baseline.melt(
            id_vars=["fuel"], value_vars=years
        )
        melted_df_baseline["value"] = melted_df_baseline["value"].astype(float)
        melted_df_baseline["variable"] = melted_df_baseline["variable"].astype(str)

        # Instead of subtracting entire DataFrames, create a new one with just the value difference
        df_fuel_switch = melted_df.copy()
        df_fuel_switch["value"] = melted_df["value"] - melted_df_baseline["value"]

        # TODO: It's the fuel override that indicates the fuel switching per fuel type process. 

        # NOTES:
        # - There is an increase or decrease in mt demand which changes energy demand
        # - There is an increase or decrease in efficiency which changes energy demand
        # - There are EE which further increase efficiency (fuel switch or not?)
        # - There are ETI/IFL which reduce demand that would otherwise have to be met by something else
        # - There are ETI/IFL which explicitly switches fuel. 
        # - Why can't we just rely on the explict fuel switch? (apart from multiple techs)
        # - What about hydrogen? Is that captured in the fuel switch?
        # - Look at one fuel suffix at a time. 

        # Create a 2x1 subplot with the first plot showing fuel consumption and the second plot showing baseline energy demand
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=[
                f"{process} Fuel Consumption",
                f"{process} Baseline Energy Demand",
                f"{process} Fuel Switching",
                "",  # Empty title for unused subplot
            ],
        )

        # Create a consistent color map for all fuels
        unique_fuels = melted_df["fuel"].unique()
        colors = px.colors.qualitative.Set3[:len(unique_fuels)]  # You can change Set3 to another colorset if desired
        fuel_colors = dict(zip(unique_fuels, colors))

        # Create baseline energy demand trace once and reuse it
        baseline_trace = go.Scatter(
            x=years,
            y=df_process_baseline.values,
            mode="lines",
            name="Baseline Energy Demand",
            line=dict(color="black", width=2, dash="dash"),
            showlegend=True,
        )

        # Plot for fuel consumption (top left)
        for fuel in unique_fuels:
            mask = melted_df["fuel"] == fuel
            fig.add_trace(
                go.Scatter(
                    x=melted_df[mask]["variable"],
                    y=melted_df[mask]["value"],
                    name=fuel,
                    fill="tonexty",
                    stackgroup="one",
                    line=dict(color=fuel_colors[fuel]),
                    showlegend=True,
                ),
                row=1,
                col=1,
            )
        # Add baseline to first plot
        fig.add_trace(baseline_trace, row=1, col=1)

        # Plot for baseline energy demand (top right)
        for fuel in unique_fuels:
            mask = melted_df_baseline["fuel"] == fuel
            fig.add_trace(
                go.Scatter(
                    x=melted_df_baseline[mask]["variable"],
                    y=melted_df_baseline[mask]["value"],
                    name=fuel,
                    fill="tonexty",
                    stackgroup="two",
                    line=dict(color=fuel_colors[fuel]),
                    showlegend=False,
                ),
                row=1,
                col=2,
            )
        # Add baseline to second plot
        fig.add_trace(
            go.Scatter(
                x=years,
                y=df_process_baseline.values,
                mode="lines",
                name="Baseline Energy Demand",
                line=dict(color="black", width=2, dash="dash"),
                showlegend=False,
            ),
            row=1,
            col=2,
        )

        # Plot for fuel switching (bottom left)
        for fuel in unique_fuels:
            mask = df_fuel_switch["fuel"] == fuel
            fig.add_trace(
                go.Scatter(
                    x=df_fuel_switch[mask]["variable"],
                    y=df_fuel_switch[mask]["value"],
                    name=fuel,
                    line=dict(color=fuel_colors[fuel]),
                    showlegend=False,
                ),
                row=2,
                col=1,
            )
        # Add baseline to third plot
        fig.add_trace(
            go.Scatter(
                x=years,
                y=df_process_baseline.values,
                mode="lines",
                name="Baseline Energy Demand",
                line=dict(color="black", width=2, dash="dash"),
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        # Update layout
        fig.update_layout(
            height=800,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.05,
            ),
        )

        fig.show()

        logger.info(f"df_process_fuel: {df_process_fuel}")

        cnt += 1
        if cnt > 4:
            exit()

    # For ES, CS, RS we use FinEn_AEMO_eneff + FinEn_enser to get the baseline energy demand

    # Save output to same directory as input
    output_path = (
        input_path.parent / f"{input_path.stem}_fuel_switching{input_path.suffix}"
    )
    df.to_excel(output_path, index=False)
    logger.info(f"Saved fuel switching calculations to: {output_path}")


@click.command()
@click.argument("input_file", type=click.Path(exists=True))
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
    file_path = Path("~/scratch/processed_view_2024-12-02T21.00_MSM24.csv").expanduser()
    calculate_fuel_switching_logic(file_path)
