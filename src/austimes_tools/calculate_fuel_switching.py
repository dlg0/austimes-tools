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

ind2_varbl_process_mapping = {
    "Alumina": "UCrepI_Activity-Al",
    "Aluminum": "UCrepI_Activity-Alum",
    "Cement+": "UCrepI_Activity-Cem",
    "PetChem": "UCrepI_Activity-Che",
    "Iron and Steel": "UCrepI_Activity-IronSteel",
}
ind2_output_varbls = list(ind2_varbl_process_mapping.values())

IND2_process_name_col = "commodity"
IND2_process_prefix = "IND2"
IND2_from_fuel_mapping = {
    "e": "Electricity",
    "g": "Natural Gas",
    "l": "LPG",
    "w": "Wood",
}

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
        "varbl_filter": ["FinEn_AEMO_eneff","FinEn_enser"],
    },
    "TR": {
        "process_name_col": TR_process_name_col,
        "process_prefix": TR_process_prefix,
        "from_fuel_mapping": TR_from_fuel_mapping,
        "varbl_filter": ["FinEn_AEMO_eneff","FinEn_enser"],
    },
    "CS": {
        "process_name_col": CS_process_name_col,
        "process_prefix": CS_process_prefix,
        "from_fuel_mapping": CS_from_fuel_mapping,
        "varbl_filter": ["FinEn_AEMO_eneff","FinEn_enser"],
    },
    "RS": {
        "process_name_col": RS_process_name_col,
        "process_prefix": RS_process_prefix,
        "from_fuel_mapping": RS_from_fuel_mapping,
        "varbl_filter": ["FinEn_AEMO_eneff","FinEn_enser"],
    },
    "IND2": {
        "process_name_col": IND2_process_name_col,
        "process_prefix": IND2_process_prefix,
        "from_fuel_mapping": IND2_from_fuel_mapping,
        "varbl_filter": ["FinEn_consumed"],
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
        entry_type = "remaining-consumption"
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
            entry_type = "remaining-consumption"
        elif "Elec" in supply_process:
            logger.info(f"Supply process: {supply_process} is Elec")
            to_fuel = "Electricity"
            entry_type = "remaining-consumption"
        elif "Gas" in supply_process:
            logger.info(f"Supply process: {supply_process} is Gas")
            to_fuel = "Natural Gas"
            entry_type = "remaining-consumption"
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
            entry_type = "remaining-consumption"
        else:
            raise ValueError(f"Unknown process: {supply_process}")

    elif supply_process.startswith("REE"):
        logger.info(f"Supply process: {supply_process} is REE")
        entry_type = "energy-efficiency"
        to_fuel = from_fuel # these are all energy efficiency processes

    else:
        raise ValueError(f"Unknown process: {supply_process}")

    return to_fuel, entry_type


def create_industry2_df(df: pd.DataFrame, years: list[str], csv_cols: list[str]) -> pd.DataFrame:

    _cols = ["scen", "region", "subsector_p"]

    # find all entries of df["fuel] == "Natural gas" and set them to "Natural Gas"
    df.loc[df["fuel"] == "Natural gas", "fuel"] = "Natural Gas"

    # alumina production
    subsectors = ["Alumina", "Aluminum", "Cement+", "PetChem", "Iron and Steel"]
    # melt the dataframe
    all_cols_not_years = [col for col in df.columns if col not in years]

    consumption_pj = df[(df["varbl"].isin(["FinEn_consumed"]) & (df["is_ind2_p"].isin(["yes"])))]
    consumption_pj = consumption_pj.melt(id_vars=all_cols_not_years, value_vars=years, var_name="year")
    consumption_pj = consumption_pj.groupby(all_cols_not_years + ["year"]).sum().reset_index()

    production_mt = df[(df["varbl"].isin(ind2_output_varbls)) & (df["is_ind2_p"].isin(["yes"]))]
    production_mt = production_mt.melt(id_vars=all_cols_not_years, value_vars=years, var_name="year")
    production_mt = production_mt.groupby(all_cols_not_years + ["year"]).sum().reset_index()

    cols_to_keep = _cols + ["year","fuel","value","varbl","process"]

    consumption_pj = consumption_pj[cols_to_keep]
    production_mt = production_mt[cols_to_keep]
    scenarios = consumption_pj["scen"].unique()
    regions = consumption_pj["region"].unique()

    # melt the dataframe
    for scen in scenarios:
        scen_consumption_pj = consumption_pj[consumption_pj["scen"] == scen]
        scen_production_mt = production_mt[production_mt["scen"] == scen]
        for region in regions:
            region_production_mt = scen_production_mt[scen_production_mt["region"] == region]
            region_consumption_pj = scen_consumption_pj[scen_consumption_pj["region"] == region]
            for subsector in subsectors:
                sector_prod_varbl = ind2_varbl_process_mapping[subsector]
                sector_production_mt = region_production_mt[(region_production_mt["subsector_p"] == subsector) & (region_production_mt["varbl"] == sector_prod_varbl)]
                sector_consumption_pj = region_consumption_pj[region_consumption_pj["subsector_p"] == subsector]

                baseyear_production_mt = sector_production_mt[(sector_production_mt["year"] == years[0])]
                baseyear_consumption_pj = sector_consumption_pj[(sector_consumption_pj["year"] == years[0])]

                # Get baseline fuel mix
                if subsector == "Alumina":
                    electrification_strings = ["electric"] 
                    process_groups = ["calcination"]
                    for process_group in process_groups:
                        # get the process group
                        process_group_consumption_pj = baseyear_consumption_pj[baseyear_consumption_pj["process"].str.lower().str.contains(process_group)]
                        # remove rows with 0 value from process group
                        process_group_consumption_pj = process_group_consumption_pj[process_group_consumption_pj["value"] != 0]
                        # get the electrification processes
                        electrification_processes = process_group_consumption_pj[process_group_consumption_pj["process"].str.lower().str.contains("|".join(electrification_strings))]
                        if electrification_processes.empty:
                            logger.info(f"No electrification found in {process_group} group for {scen} {region} {subsector}")
                        else:
                            logger.info(f"Electrification found in {process_group} group for {scen} {region} {subsector}")
                            # check if all consumption is in the electric process
                            if process_group_consumption_pj.equals(electrification_processes):
                                logger.info(f"All consumption is in the electric process for {scen} {region} {subsector}")
                            else:
                                logger.error(f"The electrification process is not the only process for {scen} {region} {subsector}")

                    print("---")

                baseline_fuel_mix = baseyear_consumption_pj.groupby(_cols, as_index=False).sum()
                for year in ["2060"]:
                    year_production_mt = sector_production_mt[(sector_production_mt["year"] == year)]
                    year_consumption_pj = sector_consumption_pj[(sector_consumption_pj["year"] == year)]
                    grouped = year_consumption_pj.groupby(_cols, as_index=False)
                    # loop over each group and print the group
                    for index, group in grouped:
                        print(group)
                        if subsector == "Alumina":
                            # Calcination
                            print("---")

    # Create the growth for the industry2 sector
    growth = df[df["is_ind2_p"] == "yes"]
    growth = growth[growth["varbl"].isin(["feedstock_consumption"])]
    growth = growth[_cols+years]
    # melt the dataframe
    growth = growth.melt(id_vars=_cols, value_vars=years, var_name="year")
    # group by the scenario, region, subsector_p and year and sum the value
    growth = growth.groupby(_cols + ["year"]).sum().reset_index()
    # pivot back to wide format
    growth = growth.pivot(index=_cols, columns="year", values="value").reset_index()
    # for each row, divide all year columns by the 2025 column
    for index, row in growth.iterrows():
        baseline_value = row[years[0]]
        for year in years:
            row[year] = row[year] / baseline_value
        growth.loc[index] = row

    # Create the growth for the industry2 sector based on only the specific commodity production
    growth2 = df[df["is_ind2_p"] == "yes"]
    growth2 = growth2[growth2["varbl"].isin(ind2_varbl_process_mapping.keys())]
    growth2 = growth2[_cols+years]
    # melt the dataframe
    growth2 = growth2.melt(id_vars=_cols, value_vars=years, var_name="year")
    # group by the scenario, region, subsector_p and year and sum the value
    growth2 = growth2.groupby(_cols + ["year"]).sum().reset_index()
    # pivot back to wide format
    growth2 = growth2.pivot(index=_cols, columns="year", values="value").reset_index()
    # for each row, divide all year columns by the 2025 column
    for index, row in growth2.iterrows():
        baseline_value = row[years[0]]
        for year in years:
            # log the row
            logger.info(f"Row: {row}")
            logger.info(f"Year: {year}, Value: {row[year]}, Baseline Value: {baseline_value}")
            row[year] = row[year] / baseline_value
        growth2.loc[index] = row

    # Create a group for each scen, region, subsector_p and year and then iterate through each group
    grouped = growth2.groupby(_cols)
    for index, group in grouped:
        print(index)
        print(group)
        print("---")


    # Create the baseline fuel consumption of the industry2 sector
    actual = df[df["is_ind2_p"] == "yes"]
    actual = actual[actual["varbl"].isin(["FinEn_consumed"]) & ~actual["subsector_p"].isin(["Feed Stock"])]
    actual = actual[_cols+["fuel"]+years]
    actual = actual.groupby(_cols+["fuel"], as_index=False).sum()
    # set all year columns equal to the first year
    baseline = actual.copy()
    for year in years:
        baseline[year] = baseline[years[0]]
    # group by the scenario, region, subsector_p and transform by dividing by the sum of the groupby
    grouped = baseline.groupby(_cols)
    for index, group in grouped:
        print(index)
        this_growth = growth.set_index(_cols).loc[index]
        mask = (baseline[_cols] == index).all(axis=1)
        for year in years:
            group[year] = group[year] * this_growth[year] 
        baseline.loc[mask] = group
        print(group.to_string())
        print(baseline.loc[mask].to_string())
        print("---")

    # create a change dataframe, where the year columns are the difference between the actual and baseline
    change = actual.copy()
    for year in years:
        change[year] = actual[year] - baseline[year]

    change_long = change.melt(id_vars=_cols+["fuel"], value_vars=years, var_name="year")
    actual_long = actual.melt(id_vars=_cols+["fuel"], value_vars=years, var_name="year")
    baseline_long = baseline.melt(id_vars=_cols+["fuel"], value_vars=years, var_name="year")

    # write the change, actual, and baseline to csv
    change_long.to_csv("change.csv", index=False)
    actual_long.to_csv("actual.csv", index=False)
    baseline_long.to_csv("baseline.csv", index=False)

    # create empty df for fuel switching results with the following columns:
    df_fuel_switch_all = pd.DataFrame(columns=csv_cols+["value"])
    # for each row in change_long, create a new row in df_fuel_switch_all
    grouped = change_long.groupby(_cols)
    for index, group in grouped:
        print(index)
        print(group)
        print("---")


    for index, row in change_long.iterrows():
 
        change_row = row.copy()
        actual_row = actual_long.iloc[index]
        baseline_row = baseline_long.iloc[index]

        # assert that all columns are the same except for value
        assert all(change_row.iloc[:-1] == actual_row.iloc[:-1])

        new_row = row.copy()

        new_row["hydrogen_source"] = None
        new_row["source_p"] = None
        new_row["sector"] = "Industry"
        new_row["process_name"] = row["subsector_p"]
        new_row["subsectorgroup_c"] = row["subsector_p"]
        new_row["fuel-switched-to"] = row["fuel"]
        new_row["fuel-switched-from"] = None 
        new_row["unit"] = "PJ"
        if new_row["fuel-switched-to"] == "Hydrogen":
            new_row["hydrogen_source"] = "Direct supply"
 
        baseline_value = baseline_row["value"]
        change_value = change_row["value"]

        remaining_row = new_row.copy()
        switch_row = new_row.copy()

        if change_value > 0:
            remaining_row["value"] = baseline_value
            switch_row["value"] = change_value
        else:
            remaining_row["value"] = baseline_value + change_value
            switch_row["value"] = 0

        remaining_row["entry_type"] = "remaining-consumption"
        switch_row["entry_type"] = "fuel-switch"

        if switch_row["fuel-switched-to"] == "Electricity":
            switch_row["entry_type"] = "electrification"

        # drop columns that are not in the csv_cols
        remaining_row = remaining_row[csv_cols+["value"]]
        switch_row = switch_row[csv_cols+["value"]]

        df_fuel_switch_all = pd.concat([df_fuel_switch_all, pd.DataFrame([remaining_row])], ignore_index=True)
        df_fuel_switch_all = pd.concat([df_fuel_switch_all, pd.DataFrame([switch_row])], ignore_index=True)

    # check for duplicates (ignoring the value column)
    if df_fuel_switch_all[csv_cols].duplicated().any():
        logger.warning("Duplicate rows found in the dataframe")
        # print the duplicate rows
        print(df_fuel_switch_all[df_fuel_switch_all[csv_cols].duplicated()])
        raise ValueError("Duplicate rows found in the dataframe")

    # switch back to wide format
    df_fuel_switch_all = df_fuel_switch_all.pivot(index=[col for col in csv_cols if col != "year"], columns="year", values="value").reset_index()

    # add empty columns for "commodity", "process", "varbl", and "fuel"
    df_fuel_switch_all["commodity"] = None
    df_fuel_switch_all["process"] = None
    df_fuel_switch_all["varbl"] = None
    df_fuel_switch_all["fuel"] = None

    return df_fuel_switch_all

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

        # filter out varbl = ["FinEn_AEMO", "FinEn_AEMO_eneff", "FinEn_enser", "FinEn_consumed","feedstock_consumption"]+ind2_varbl_process_mapping.keys()
        if not all(varbl in df["varbl"].unique() for varbl in ind2_output_varbls):
            logger.warning("No industry2 output varbls found in the dataframe")
            logger.warning(f"Unique varbls: {df['varbl'].unique()}")
            logger.warning(f"ind2_output_varbls: {ind2_output_varbls}")
            raise ValueError("No industry2 output varbls found in the dataframe")
        df = df[df["varbl"].isin(["FinEn_AEMO", "FinEn_AEMO_eneff", "FinEn_enser", "FinEn_consumed","feedstock_consumption"]+ind2_output_varbls)]

        # Cache the dataframe
        logger.info(f"Caching data to: {cache_path}")
        df.to_pickle(cache_path)

    # Varbl long descriptions from lmadefs
    # FinEn_AEMO (): Total production of energy services for Industry and Buildings. OK to check fuel mixes, but absolute values miss energy efficiency etc. Transport OK.
    # FinEn_AEMO_eneff (p,c): Production of energy services for Buildings and Industry - ONLY from EE, BFL, IFL, and ETI sources.
    # FinEn_enser (p,c): Production of energy services for Buildings and Industry - EXCEPT from EE, BFL, IFL, and ETI sources.
    # FinEn_consumed (p,c): Complete final energy - consumption of sector fuels. Hence, not very disaggregated for Industry and Buildings

    years = ["2025", "2030", "2035", "2040", "2045", "2050", "2055", "2060"]

    cols_to_keep = ["scen", "region", "source_p", "subsectorgroup_c", "hydrogen_source", "unit"]
    cols_we_use = ["process", "commodity", "varbl", "fuel"]

    # check to see if cols_to_keep + cols_we_use are in the df, and if not, log which are missing
    for col in cols_to_keep + cols_we_use:
        if col not in df.columns:
            logger.warning(f"Column {col} not found in the dataframe")

    new_cols = ["fuel-switched-from", "fuel-switched-to", "sector", "process_name", "entry_type"]

    df_original = df.copy()

    # Retain only the relevant columns
    cols = cols_to_keep + cols_we_use 
    df = df[cols + years]

    # Groupby the relevant columns and sum the values
    df = df.groupby(cols).sum().reset_index()

    final_cols = cols_to_keep + cols_we_use + new_cols + years
    csv_cols = cols_to_keep + new_cols + ["year"] 
    df_fuel_switch_all = pd.DataFrame(columns=final_cols)

    df_ind2 = create_industry2_df(df_original, years, csv_cols)

    # Get a list of all the processes
   # Strip the `-?` or `-??` suffix and remove duplicates
    #processes = [re.sub(r"-.{1,2}$", "", p) for p in processes]
    #processes = list(set(processes))
    # Loop through each process and calculate the fuel switching

    # sectors to process
    sectors = []#["Industry", "Commercial", "Residential"]
    sector_prefix_mapping = {
        "Industry": "ES",
        "Transport": "TR",
        "Commercial": "CS",
        "Residential": "RS",
        "Industry2": "IND2",
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
            df_process = df_process[df_process["varbl"].isin(this_sector_structure["varbl_filter"])]
            if sector == "Industry2":
                # Filter for column "is_ind2" = "yes"
                df_process = df_process[df_process["is_ind2"] == "yes"]



            # Extract the process name and fuel suffix
            if sector == "Industry":
                process_name_no_prefix = process.replace(process_prefix+"_", "")
                from_fuel_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(f"-{from_fuel_suffix}", "")
            elif sector == "Commercial":
                process_name_no_prefix = process.replace(process_prefix+"_", "")
                complete_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel_suffix = complete_suffix[0]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(f"-{complete_suffix}", "")
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
                    if entry_type not in ["remaining-consumption", "energy-efficiency", "automation", "demand-reduction"]:
                        raise ValueError(f"Entry type is not consumption or energy-efficiency (is {entry_type}) for {supply_process} -> {process} with from_fuel {from_fuel} and to_fuel {to_fuel}")
                if entry_type in ["fuel-switch", "electrification"]:
                    if to_fuel in ["Coal", "Natural Gas", "LPG", "Wood", "Oil", "Brown Coal"]:
                        logger.warning(f"Entry type is {entry_type} for {supply_process} -> {process} with from_fuel {from_fuel} and to_fuel {to_fuel}")
                        raise ValueError(f"Fuel switch to {to_fuel} is not allowed")

                df_fuel_switch_all = pd.concat([df_fuel_switch_all, pd.DataFrame([new_row])], ignore_index=True)


            cnt += 1

    # concat df_fuel_switch_all and df_ind2
    df_fuel_switch_all = pd.concat([df_fuel_switch_all, df_ind2], ignore_index=True)

    # For ES, CS, RS we use FinEn_AEMO_eneff + FinEn_enser to get the baseline energy demand

    # Save output to same directory as input
    output_path = (
        input_path.parent / f"{input_path.stem}_fuel_switching.csv"
    )
    # melt to long format
    df_fuel_switch_all = df_fuel_switch_all.melt(id_vars=cols_to_keep+cols_we_use+new_cols, value_vars=years, var_name="year", value_name="value")
    # fill mising indice with "-"
    df_fuel_switch_all = df_fuel_switch_all.fillna("-")
    # find rows with sector = "Commercial" and "fuel-switched-to" = "Hydrogen" and set "hydrogen_source" = "Blended"
    df_fuel_switch_all.loc[(df_fuel_switch_all["sector"] == "Commercial") & (df_fuel_switch_all["fuel-switched-to"] == "Hydrogen"), "hydrogen_source"] = "Blending"
    # remove rows where value is 0
    df_fuel_switch_all = df_fuel_switch_all[df_fuel_switch_all["value"] != 0]
    # remove rows where entry_type is not in ["remaining-consumption", "fuel-switch", "electrification"]
    df_fuel_switch_all = df_fuel_switch_all[df_fuel_switch_all["entry_type"].isin(["remaining-consumption", "fuel-switch", "electrification"])]
    # drop the "source_p" column
    df_fuel_switch_all = df_fuel_switch_all.drop(columns=["source_p","process","commodity","varbl","fuel"])
    # rename the subsectorgroup_c column to subsector
    df_fuel_switch_all = df_fuel_switch_all.rename(columns={"subsectorgroup_c": "subsector"})
    # groupby csv_cols and sum the value
    _final_cols = [col for col in df_fuel_switch_all.columns if col != "value"]
    df_fuel_switch_all = df_fuel_switch_all.groupby(_final_cols).sum().reset_index()
    # drop the cols not grouped by
    df_fuel_switch_all = df_fuel_switch_all.drop(columns = [col for col in df_fuel_switch_all.columns if col not in _final_cols+["value"]])
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
