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

# Map the fuel suffix to the fuel type
# ES format is ES-<fuel>
ES_process_name_col = "commodity"
ES_process_prefix = "ES"
ES_from_fuel_mapping = {
    "c": "Coal",
    "l": "Liquid",
    "o": "Oil",
    "e": "Electricity",
    "g": "Natural Gas",
    "b": "Biomass",
    "r": "Brown Coal",
}

# TR format is TR-<fuel>
TR_process_name_col = "commodity"
TR_process_prefix = "TR"
TR_from_fuel_mapping = {
    "Bdl": "Biodiesel",
    "Cng": "Compressed Natural Gas",
    "Fch": "Fuel Cell Hydrogen",
    "Lpg": "Liquefied Petroleum Gas",
    "Pet": "Petrol",
    "Ele": "Electricity",
}

# TCS format is TCS_<fuel>-<end-use> where ...
# <fuel> is one of [BioG=Biogas, Elec=Electricity, Gas2Elc=Electricity, H2-Gas=Hydrogen, Oil=Oil]
# <end-use> is a single letter [a, h, w, o, v, l, i, c]
CS_process_name_col = "commodity"
CS_process_prefix = "CS"
CS_from_fuel_mapping = {
    "BioG": "Biogas",
    "Elec": "Electricity",
    "Gas2Elc": "Electricity",
    "H2-Gas": "Hydrogen",
    "Oil": "Oil",
    "g": "Natural Gas",
    "e": "Electricity",
    "o": "Oil",
}

# RS format is RS<existing>_<rs-type>_<end-use>-<fuel> where ...
# <existing> is a single letter [n,e], 
# <rs-type> is one of [Appt, SHou, THou], 
# <end-use> is a single letter [a, h, w, o, v, l, i, c]
# <fuel> is one of [e=Electricity, g=Natural Gas, l=LPG, w=Wood]
RS_process_name_col = "commodity"
RS_process_prefix = "RS"
RS_from_fuel_mapping = {
    "e": "Electricity",
    "g": "Natural Gas",
    "l": "LPG",
    "w": "Wood",
}

sector_structure = {
    "ES": {
        "process_name_col": ES_process_name_col,
        "process_prefix": ES_process_prefix,
        "from_fuel_mapping": ES_from_fuel_mapping,
    },
    "TR": {
        "process_name_col": TR_process_name_col,
        "process_prefix": TR_process_prefix,
        "from_fuel_mapping": TR_from_fuel_mapping,
    },
    "CS": {
        "process_name_col": CS_process_name_col,
        "process_prefix": CS_process_prefix,
        "from_fuel_mapping": CS_from_fuel_mapping,
    },
    "RS": {
        "process_name_col": RS_process_name_col,
        "process_prefix": RS_process_prefix,
        "from_fuel_mapping": RS_from_fuel_mapping,
    },
}

ETI_fuel_mapping = {
    "ele": "Electricity",
    "hyd": "Hydrogen",
    "bio": "Biomass",
}

ENSER_fuel_mapping = {
    "IES_coa": "Coal",
    "IES_gas": "Natural Gas",
    "IES_ele": "Electricity",
    "Oil Energy": "Oil",
    "LPG Energy": "LPG",
    "Wood Energy": "Wood",
    "IES_bio": "Biomass",
    "IES_elc": "Electricity",
    "IES_biogas_0": "Biogas",
    "IES_h2_0": "Hydrogen",
    "IES_h2_1": "Hydrogen",
    "IES_h2_2": "Hydrogen",
    "IES_oil": "Oil",
    "IES_cob": "Brown Coal",
}

def get_to_fuel(supply_process: str, from_fuel: str) -> tuple[str, str]:

    #row_variable = row["varbl"]

    if supply_process.startswith("EE"):
        logger.info(f"Supply process: {supply_process} is EE")
        to_fuel_suffix = supply_process.split("-")[-1]
        to_fuel = from_fuel # this is an energy efficiency process
        entry_type = "energy-efficiency"

    elif supply_process.startswith("ETI_EE"):
        logger.info(f"Supply process: {supply_process} is ETI_EE")
        to_fuel = from_fuel # this is an energy efficiency process
        entry_type = "energy-efficiency"

    elif supply_process.startswith("ETI"):
        eti_mapping = {
            "ELE": "electrification",
            "FS": "fuel-switch",
        }
        logger.info(f"Supply process: {supply_process} is ETI")
        supply_process_no_prefix = supply_process.replace("ETI_", "")
        eti_type = supply_process_no_prefix.split("_")[0]
        eti_type = eti_mapping[eti_type]
        to_fuel_suffix = supply_process_no_prefix.split("_")[1]
        to_fuel = ETI_fuel_mapping[to_fuel_suffix]
        entry_type = eti_type

    elif supply_process.startswith("IFL"):
        logger.info(f"Supply process: {supply_process} is IFL")
        ifl_mapping = {
            "IT": "automation",
        }
        supply_process_no_prefix = supply_process.replace("IFL_", "")
        ifl_type = supply_process_no_prefix.split("_")[0]
        ifl_type = ifl_mapping[ifl_type]
        to_fuel = from_fuel # these are all automation, etc type processes which can remove any fuel type
        entry_type = ifl_type

    elif supply_process.startswith("IES"):
        logger.info(f"Supply process: {supply_process} is IES")
        entry_type = "no-switch"
        if supply_process.startswith("IES_ele"):
            supply_process = "IES_ele"
            entry_type = "electrification"

        to_fuel = ENSER_fuel_mapping[supply_process]

    elif supply_process.startswith("BFL"):
        logger.info(f"Supply process: {supply_process} is BFL")
        bfl_mapping = {
            "Eni": "energy-efficiency",
            "Dem": "demand-reduction",
        }
        bfl_type = supply_process.split("_")[3].split("-")[0]
        bfl_type = bfl_mapping[bfl_type]
        to_fuel = from_fuel # these are all energy efficiency processes
        entry_type = bfl_type

    elif supply_process.startswith("TCS"):
        logger.info(f"Supply process: {supply_process} is TCS")
        if "BioG-Gas" in supply_process:
            logger.info(f"Supply process: {supply_process} is BioG-Gas")
            to_fuel = "Biogas"
            entry_type = "fuel-switch"
        elif "Gas2Elc" in supply_process:
            logger.info(f"Supply process: {supply_process} is Gas2Elc")
            to_fuel = "Electricity"
            entry_type = "electrification"
        elif "H2-Gas" in supply_process:
            logger.info(f"Supply process: {supply_process} is H2-Gas")
            to_fuel = "Hydrogen"
            entry_type = "fuel-switch"
        elif "Oil" in supply_process:
            logger.info(f"Supply process: {supply_process} is Oil")
            to_fuel = "Oil"
            entry_type = "no-switch"
        elif "Elec" in supply_process:
            logger.info(f"Supply process: {supply_process} is Elec")
            to_fuel = "Electricity"
            entry_type = "no-switch"
        elif "Gas" in supply_process:
            logger.info(f"Supply process: {supply_process} is Gas")
            to_fuel = "Natural Gas"
            entry_type = "no-switch"
        else:
            raise ValueError(f"Unknown process: {supply_process}")

    elif supply_process.startswith("CEE"):
        logger.info(f"Supply process: {supply_process} is CEE")
        entry_type = "energy-efficiency"
        to_fuel = from_fuel # these are all energy efficiency processes

    elif supply_process.startswith("RTS"):
        logger.info(f"Supply process: {supply_process} is RTS")
        to_fuel_suffix = supply_process.split("-")[-1]
        if to_fuel_suffix in ["g2e", "w2e", "l2e"]:
            to_fuel = "Electricity"
            entry_type = "electrification"
        elif to_fuel_suffix in ["e", "g", "l", "w"]:
            to_fuel = from_fuel # these are all energy efficiency processes
            entry_type = "no-switch"
        else:
            raise ValueError(f"Unknown process: {supply_process}")

    elif supply_process.startswith("REE"):
        logger.info(f"Supply process: {supply_process} is REE")
        entry_type = "energy-efficiency"
        to_fuel = from_fuel # these are all energy efficiency processes

    else:
        raise ValueError(f"Unknown process: {supply_process}")

    return to_fuel, entry_type



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
    else:
        if input_path.suffix.lower() == ".csv":
            df = pd.read_csv(input_path)
        elif input_path.suffix.lower() in [".xlsx", ".xls"]:
            df = pd.read_excel(input_path)
        else:
            raise ValueError("File must be CSV or Excel (.csv, .xlsx, .xls)")

        # filter out varbl = ["FinEn_AEMO", "FinEn_AEMO_eneff", "FinEn_enser", "FinEn_consumed"]
        df = df[df["varbl"].isin(["FinEn_AEMO", "FinEn_AEMO_eneff", "FinEn_enser", "FinEn_consumed"])]

        # Cache the dataframe
        logger.info(f"Caching data to: {cache_path}")
        df.to_pickle(cache_path)

    # Varbl long descriptions from lmadefs
    # FinEn_AEMO (): Total production of energy services for Industry and Buildings. OK to check fuel mixes, but absolute values miss energy efficiency etc. Transport OK.
    # FinEn_AEMO_eneff (p,c): Production of energy services for Buildings and Industry - ONLY from EE, BFL, IFL, and ETI sources.
    # FinEn_enser (p,c): Production of energy services for Buildings and Industry - EXCEPT from EE, BFL, IFL, and ETI sources.
    # FinEn_consumed (p,c): Complete final energy - consumption of sector fuels. Hence, not very disaggregated for Industry and Buildings

    years = ["2025", "2030", "2035", "2040", "2045", "2050"]

    cols_to_keep = ["scen", "region", "source_p", "subsectorgroup_c", "hydrogen_source", "unit"]
    cols_we_use = ["process", "commodity", "varbl", "fuel"]

    # check to see if cols_to_keep + cols_we_use are in the df, and if not, log which are missing
    for col in cols_to_keep + cols_we_use:
        if col not in df.columns:
            logger.warning(f"Column {col} not found in the dataframe")

    new_cols = ["fuel-switched-from", "fuel-switched-to", "sector", "process_name", "entry_type"]

    # Retain only the relevant columns
    cols = cols_to_keep + cols_we_use 
    df = df[cols + years]

    # Groupby the relevant columns and sum the values
    df = df.groupby(cols).sum().reset_index()

    final_cols = cols_to_keep + cols_we_use + new_cols + years
    csv_cols = cols_to_keep + new_cols + ["year"] 
    df_fuel_switch_all = pd.DataFrame(columns=final_cols)

    # Get a list of all the processes
   # Strip the `-?` or `-??` suffix and remove duplicates
    #processes = [re.sub(r"-.{1,2}$", "", p) for p in processes]
    #processes = list(set(processes))
    # Loop through each process and calculate the fuel switching

    # sectors to process
    sectors = ["Industry", "Commercial", "Residential"]
    sector_prefix_mapping = {
        "Industry": "ES",
        "Transport": "TR",
        "Commercial": "CS",
        "Residential": "RS",
    }

    # Create empty df for fuel switching results with the following columns:
    # study, scen, sector0, sector1, process, fuel-from, fuel-to, type-of-change
    # type-of-change is one of [energy-efficiency-1, energy-efficiency-2, energy-efficiency-3, material substitution, fuel-switch,]
    for sector in sectors:
        sector_prefix = sector_prefix_mapping[sector]
        this_sector_structure = sector_structure[sector_prefix]
        from_fuel_mapping = this_sector_structure["from_fuel_mapping"]
        process_name_col = this_sector_structure["process_name_col"]
        process_prefix = this_sector_structure["process_prefix"]
        # Filter for the relevant rows for all processes which start with the process prefix
        df_sector = df[df[process_name_col].str.startswith(process_prefix)]
        processes = df_sector[process_name_col].unique()
 
        cnt = 0
        for process in processes:
            # Filter for the process
            logger.info(f"Processing: {process}")
            # Get the relevant rows for all processes which start with the process name
            df_process = df_sector[df_sector[process_name_col].str.startswith(process)]
            # Filter for varbl = ["FinEn_AEMO_eneff"]
            df_process = df_process[df_process["varbl"].isin(["FinEn_AEMO_eneff","FinEn_enser"])]

            # Extract the process name and fuel suffix
            if sector == "Industry":
                process_name_no_prefix = process.replace(process_prefix+"_", "")
                from_fuel_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(f"-{from_fuel_suffix}", "")
            elif sector == "Commercial":
                process_name_no_prefix = process.replace(process_prefix+"_", "")
                from_fuel_suffix = process_name_no_prefix.split("-")[-1][0]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(f"-{from_fuel_suffix}", "")
            elif sector == "Residential":
                process_name_no_prefix = process.replace(process_prefix, "")
                from_fuel_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(f"-{from_fuel_suffix}", "")

            # Log the process name, from_fuel, and from_fuel_suffix
            logger.info(f"Process: {process_name}, From Fuel: {from_fuel}, From Fuel Suffix: {from_fuel_suffix}")
            # Get the baseline total energy demand by simply summing all rows
            df_process_baseline = df_process.loc[:, years].sum()

            # Loop through each row of df_process
            for index, row in df_process.iterrows():

                supply_process = row["process"]
                to_fuel, entry_type = get_to_fuel(supply_process, from_fuel)

                # Get the fuel-to from the process column entry
                # Log the fuel-from and fuel-to
                logger.info(f"Fuel-from: {from_fuel}, Fuel-to: {to_fuel}")

                # Create a new row which is row plus the fuel-switched-from and fuel-switched-to
                new_row = row.copy()
                new_row["fuel-switched-from"] = from_fuel
                new_row["fuel-switched-to"] = to_fuel
                new_row["process_name"] = process_name
                new_row["sector"] = sector
                new_row["entry_type"] = entry_type

                # Couple of checks
                if from_fuel == to_fuel:
                    if entry_type not in ["no-switch", "energy-efficiency", "automation", "demand-reduction"]:
                        raise ValueError(f"Entry type is not consumption or energy-efficiency (is {entry_type}) for {supply_process} -> {process} with from_fuel {from_fuel} and to_fuel {to_fuel}")
                if entry_type in ["fuel-switch", "electrification"]:
                    if to_fuel in ["Coal", "Natural Gas", "LPG", "Wood", "Oil", "Brown Coal"]:
                        logger.warning(f"Entry type is {entry_type} for {supply_process} -> {process} with from_fuel {from_fuel} and to_fuel {to_fuel}")
                        raise ValueError(f"Fuel switch to {to_fuel} is not allowed")

                df_fuel_switch_all = pd.concat([df_fuel_switch_all, pd.DataFrame([new_row])], ignore_index=True)

            # Drop everything but years and fuel, then groupby fuel and sum
            df_process_fuel = (
                df_process[df_process["varbl"] == "FinEn_enser"]
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
            # - There are ETI/IFL/BFL which reduce demand that would otherwise have to be met by something else
            # - There are ETI/IFL/BFL which explicitly switches fuel (the "FS" type). 
            #       "ETI_FS_<fuel-to>_*" (ind only though)
            #       "ETI_ELE_<fuel-to>_*" (ind only though - electrification)
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

            #fig.show()

            logger.info(f"df_process_fuel: {df_process_fuel}")

            cnt += 1
            #if cnt > 4:
            #    exit()

    # For ES, CS, RS we use FinEn_AEMO_eneff + FinEn_enser to get the baseline energy demand

    # Save output to same directory as input
    output_path = (
        input_path.parent / f"{input_path.stem}_fuel_switching{input_path.suffix}"
    )
    df.to_excel(output_path, index=False)
    logger.info(f"Saved fuel switching calculations to: {output_path}")

    # Save output to same directory as input
    output_path = (
        input_path.parent / f"{input_path.stem}_fuel_switching.csv"
    )
    # melt to long format
    df_fuel_switch_all = df_fuel_switch_all.melt(id_vars=cols_to_keep+cols_we_use+new_cols, value_vars=years, var_name="year", value_name="value")
    # groupby csv_cols and sum the value
    df_fuel_switch_all = df_fuel_switch_all.groupby(csv_cols).sum().reset_index()
    # drop the cols not grouped by
    df_fuel_switch_all = df_fuel_switch_all.drop(columns = [col for col in df_fuel_switch_all.columns if col not in csv_cols+["value"]])
    df_fuel_switch_all.to_csv(output_path, index=False)
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
    #file_path = Path("~/scratch/processed_view_2024-12-06T09.14_MSM24.csv").expanduser()
    file_path = Path("~/scratch/raw_view_old_only-wide.xlsx").expanduser()
    calculate_fuel_switching_logic(file_path)
