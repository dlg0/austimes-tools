import rich_click as click
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from loguru import logger
import sys
import re
import plotly.express as px
from tabulate import tabulate
import numpy as np
# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, level="INFO")  # Add handler with stderr as sink

ind2_varbl_process_mapping = {
    "Alumina": "UCrepI_Activity-Alum",
    "Aluminum": "UCrepI_Activity-Al",
    "Cement+": "UCrepI_Activity-Cem",
    "PetChem": "UCrepI_Activity-Che",
    "Iron and Steel": "UCrepI_Activity-IronSteel",
}
ind2_output_varbls = list(ind2_varbl_process_mapping.values())
extra_ind2_output_varbls = ["UCrepI_Activity-Che-ammonia", "UCrepI_Activity-Che-methanol"]

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
        "varbl_filter": ["FinEn_AEMO_eneff", "FinEn_enser"],
    },
    "TR": {
        "process_name_col": TR_process_name_col,
        "process_prefix": TR_process_prefix,
        "from_fuel_mapping": TR_from_fuel_mapping,
        "varbl_filter": ["FinEn_AEMO_eneff", "FinEn_enser"],
    },
    "CS": {
        "process_name_col": CS_process_name_col,
        "process_prefix": CS_process_prefix,
        "from_fuel_mapping": CS_from_fuel_mapping,
        "varbl_filter": ["FinEn_AEMO_eneff", "FinEn_enser"],
    },
    "RS": {
        "process_name_col": RS_process_name_col,
        "process_prefix": RS_process_prefix,
        "from_fuel_mapping": RS_from_fuel_mapping,
        "varbl_filter": ["FinEn_AEMO_eneff", "FinEn_enser"],
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
    # row_variable = row["varbl"]

    if supply_process.startswith("EE"):
        logger.info(f"Supply process: {supply_process} is EE")
        to_fuel_suffix = supply_process.split("-")[-1]
        to_fuel = from_fuel  # this is an energy efficiency process
        entry_type = "energy-efficiency"

    elif supply_process.startswith("ETI_EE"):
        logger.info(f"Supply process: {supply_process} is ETI_EE")
        to_fuel = from_fuel  # this is an energy efficiency process
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
        to_fuel = from_fuel  # these are all automation, etc type processes which can remove any fuel type
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
        to_fuel = from_fuel  # these are all energy efficiency processes
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
        to_fuel = from_fuel  # these are all energy efficiency processes

    elif supply_process.startswith("RTS"):
        logger.info(f"Supply process: {supply_process} is RTS")
        to_fuel_suffix = supply_process.split("-")[-1]
        if to_fuel_suffix in ["g2e", "w2e", "l2e"]:
            to_fuel = "Electricity"
            entry_type = "electrification"
        elif to_fuel_suffix in ["e", "g", "l", "w"]:
            to_fuel = from_fuel  # these are all energy efficiency processes
            entry_type = "remaining-consumption"
        else:
            raise ValueError(f"Unknown process: {supply_process}")

    elif supply_process.startswith("REE"):
        logger.info(f"Supply process: {supply_process} is REE")
        entry_type = "energy-efficiency"
        to_fuel = from_fuel  # these are all energy efficiency processes

    else:
        raise ValueError(f"Unknown process: {supply_process}")

    return to_fuel, entry_type


def create_industry2_df(
    df: pd.DataFrame, years: list[str], csv_cols: list[str], input_dir: Path
) -> pd.DataFrame:
    _cols = ["scen", "region", "subsector_p"]

    # check if pickle exists
    pickle_path = input_dir / "ind2-fuel-switch.pkl"
    if pickle_path.exists():
        return pd.read_pickle(pickle_path)

    # find all entries of df["fuel] == "Natural gas" and set them to "Natural Gas"
    df.loc[df["fuel"] == "Natural gas", "fuel"] = "Natural Gas"

    # alumina production
    subsectors = ["Alumina", "Aluminum", "Cement+", "PetChem", "Iron and Steel"]
    # melt the dataframe
    all_cols_not_years = [col for col in df.columns if col not in years]

    #consumption_pj = df[
    #    (df["varbl"].isin(["FinEn_consumed"]) & (df["is_ind2_p"].isin(["yes"])))
    #]
    consumption_pj = df[ df["varbl"].isin(["FinEn_consumed"])]
    consumption_pj = consumption_pj.melt( id_vars=all_cols_not_years, value_vars=years, var_name="year")
    consumption_pj = consumption_pj.groupby(all_cols_not_years + ["year"]).sum().reset_index()

    production_mt = df[df["varbl"].isin(ind2_output_varbls+extra_ind2_output_varbls)]
    production_mt = production_mt.melt(id_vars=all_cols_not_years, value_vars=years, var_name="year")
    production_mt = (production_mt.groupby(all_cols_not_years + ["year"]).sum().reset_index())

    cols_to_keep = _cols + ["year", "fuel", "value", "varbl", "process"]

    consumption_pj = consumption_pj[cols_to_keep]
    production_mt = production_mt[cols_to_keep].copy()

    # Group by all columns except 'varbl' and 'value' to maintain the structure
    grouping_cols = [col for col in production_mt.columns if col not in ['varbl', 'value']]

    # Get the ammonia and methanol values, maintaining the structure
    ammonia_mt = production_mt[production_mt['varbl'] == 'UCrepI_Activity-Che-ammonia'].copy()
    methanol_mt = production_mt[production_mt['varbl'] == 'UCrepI_Activity-Che-methanol'].copy()

    # Log the totals of the ammonia and methanol
    logger.info(f"Ammonia MT: {ammonia_mt['value'].sum()}")
    logger.info(f"Methanol MT: {methanol_mt['value'].sum()}")

    # Sum the totals for verification
    ammonia_total = ammonia_mt['value'].sum()
    methanol_total = methanol_mt['value'].sum()

    # Add methanol values to matching ammonia rows
    ammonia_mt_with_methanol = ammonia_mt.copy()
    ammonia_mt_with_methanol.set_index(grouping_cols, inplace=True)
    methanol_mt.set_index(grouping_cols, inplace=True)

    # Add the methanol values to the corresponding ammonia rows
    ammonia_mt_with_methanol['value'] += methanol_mt['value']

    # Reset index and rename varbl to UCrepI_Activity-Che
    ammonia_mt_with_methanol.reset_index(inplace=True)
    ammonia_mt_with_methanol['varbl'] = 'UCrepI_Activity-Che'

    # Remove original ammonia and methanol rows and add the combined rows
    production_mt = production_mt[~production_mt['varbl'].isin(['UCrepI_Activity-Che-ammonia', 'UCrepI_Activity-Che-methanol'])]
    production_mt = pd.concat([production_mt, ammonia_mt_with_methanol])

    # Verify the totals match
    che_total = production_mt[production_mt['varbl'] == 'UCrepI_Activity-Che']['value'].sum()
    assert np.isclose(che_total, ammonia_total + methanol_total), f"Che total: {che_total} is not equal to the sum of ammonia and methanol: {ammonia_total + methanol_total}"

    # Log the totals
    logger.info(f"Che total: {che_total}")
    logger.info(f"Sum of ammonia and methanol: {ammonia_total + methanol_total}")

    # Create reverse mapping once outside the loop
    rev_mapping = {v: k for k, v in ind2_varbl_process_mapping.items()}
    # Use vectorized operation to set the subsector_p column
    production_mt["subsector_p"] = production_mt["varbl"].map(rev_mapping)


    production_mt = production_mt.drop(columns=["varbl","process","fuel"])
    consumption_pj = consumption_pj.drop(columns=["varbl"])

    scenarios = consumption_pj["scen"].unique()
    regions = consumption_pj["region"].unique()

    final_df = pd.DataFrame()

    for scen in scenarios:
        scen_consumption_pj = consumption_pj[consumption_pj["scen"] == scen]
        scen_production_mt = production_mt[production_mt["scen"] == scen]

        for region in regions:
            region_production_mt = scen_production_mt[scen_production_mt["region"] == region]
            region_consumption_pj = scen_consumption_pj[scen_consumption_pj["region"] == region]

            for subsector in subsectors:
                sector_production_mt = region_production_mt[region_production_mt["subsector_p"] == subsector]
                sector_consumption_pj = region_consumption_pj[region_consumption_pj["subsector_p"] == subsector]

                if len(sector_production_mt) == 0:
                    logger.warning(f"No production found for {scen} {region} {subsector}")
                    assert len(sector_consumption_pj) == 0
                    continue

                for year in years:

                    baseyear_production_mt = float(sector_production_mt[(sector_production_mt["year"] == years[0])]["value"].values[0])
                    thisyear_production_mt = float(sector_production_mt[(sector_production_mt["year"] == year)]["value"].values[0])

                    baseyear_consumption_pj = sector_consumption_pj[(sector_consumption_pj["year"] == years[0])]
                    thisyear_consumption_pj = sector_consumption_pj[(sector_consumption_pj["year"] == year)]

                    sets_of_fuels_allowed_to_be_switched_from = {
                        "fossil":["Coal","Natural Gas","Hydrogen","Oil"],
                        "all":["Coal","Natural Gas","Hydrogen","Oil","Electricity"]
                        }

                    multi_to_multi_rules = {"blr": [("Coal","Electricity"),("Natural Gas","Hydrogen")]}

                    # this is a list of tuples, where the first element is the process group and the second element is the process group typeo
                    # if we need to add a negative match, then the first element of the group is a tuple where the second element is the negative match
                    subsector_process_groups = {
                        "Alumina": [
                            #((["blr"],[]),"fossil"),
                            #((["calcination"],[]),"fossil"),
                            #((["mining"],[]),"fossil"),
                            #((["bayer"],[]),"fossil"),
                            ((["all","blr","calcination","mining","bayer"],[]),"fossil"),
                        ],
                        "Aluminum": [
                            #((["blr"],[]),"fossil"),
                            #((["calcination"],[]),"fossil"),
                            #((["hall"],[]),"fossil"),
                            #((["coking"],[]),"fossil"),
                            #((["distillation"],[]),"fossil"),
                            #((["anode"],["hall"]),"fossil"),
                            ((["all","hall","coking","distillation","anode"],[]),"fossil"),
                        ],
                        "Iron and Steel 2": [
                            # iron
                            ((["dri"],["pelletizing","cooling","reformer","sintering"]),"fossil"),
                            ((["cooling"],[]),"fossil"),
                            ((["pelletizing"],["stl"]),"fossil"),
                            ((["sintering"],[]),"fossil"),
                            ((["excavators"],[]),"fossil"),
                            ((["beneficiation"],[]),"fossil"),
                            ((["crushers"],[]),"fossil"),
                            # steel
                            ((["casting"],[]),"fossil"),
                            ((["furnace"],["ladle"]),"fossil"),
                            ((["bof","ladle"],[]),"fossil"),
                            ((["coke"],[]),"fossil"),
                            ((["bf"],[]),"fossil"),
                            ((["grate"],[]),"fossil"),
                        ],
                        "Iron and Steel 2": [ # the above does not work because DRI replaces some of the other processes? 
                            # simplified iron
                            ((["iron","dri","cooling","pelletizing","sintering","excavators","beneficiation","crushers"],[]),"fossil"),
                            # simplified steel
                            ((["steel", "casting","furnace","bof","ladle","coke","bf","grate"],[]),"fossil"),
                        ],
                        "Iron and Steel": [ # the above does not work because DRI replaces some of the other processes? 
                            # simplified iron
                            ((["all","dri","cooling","pelletizing","sintering","excavators","beneficiation","crushers","steel", "casting","furnace","bof","ladle","coke","bf","grate"],[]),"fossil"),
                        ],
                        "Cement+": [
                            #((["blr"],[]),"fossil"),
                            #((["soda ash"],[]),"fossil"),
                            #((["kiln"],[]),"fossil"),
                            #((["mill"],["milling"]),"fossil"),
                            #((["precalcination"],[]),"fossil"),
                            #((["ball milling","jet milling"],[]),"fossil"),
                            #((["drying"],[]),"fossil"),
                            #((["crushing"],[]),"fossil"),
                            #((["extrusion"],[]),"fossil"),
                            #((["pressing"],[]),"fossil"),
                            #((["molding"],[]),"fossil"),
                            #((["casting"],[]),"fossil"),
                            #((["mixing"],[]),"fossil"),
                            #((["fiberizing"],[]),"fossil"),
                            #((["annealing"],[]),"fossil"),
                            #((["attenuation"],[]),"fossil"),
                            #((["bath"],[]),"fossil"),
                            #((["furnace"],[]),"fossil"),
                            #((["nnpb"],[]),"fossil"),
                            #((["blow"],[]),"fossil"),
                            #((["spinning"],[]),"fossil"),
                            ((["all","soda ash","kiln","mill","precalcination","ball milling","jet milling","drying","crushing","extrusion","pressing","molding","casting","mixing","fiberizing","annealing","attenuation","bath","furnace","nnpb","blow","spinning"],[]),"fossil"),
                        ],
                        "PetChem": [
                            #((["hydrogen","naptha","co process","cell process","dehydrogenation","steam cracking"],["blr"]),"fossil"),
                            #((["blr"],[]),"fossil"),
                            #((["cell process"],[]),"fossil"),
                            #((["ammonia"],[]),"fossil"),
                            #((["methanol"],[]),"fossil"),
                            #((["urea"],[]),"fossil"),
                            #((["other","2-eh","acet","polymerization","process","edc","emul","ethyl","fract","hdpe","hda","hydrotreating","isobut","ldpe","liquid","lldpe","oxyc","pdh","propg","pvc","tdp","vcm","zieg"],[]),"fossil"),
                            ((["all","blr","hydrogen","naptha","co process","cell process","dehydrogenation","steam cracking","ammonia","methanol","urea","other","2-eh","acet","polymerization","process","edc","emul","ethyl","fract","hdpe","hda","hydrotreating","isobut","ldpe","liquid","lldpe","oxyc","pdh","propg","pvc","tdp","vcm","zieg"],[]),"fossil"),
                        ],
                    }

                    # TODO: Do a check to see if there are any processes either in the baseyear or thisyear that are not in the subsector_process_groups
                    #baseyear_process_groups = baseyear_consumption_pj["process"].unique()
                    #thisyear_process_groups = thisyear_consumption_pj["process"].unique()
                    #all_process_groups = np.unique(baseyear_process_groups + thisyear_process_groups)
                    #for process_group in all_process_groups:
                    #    if process_group not in subsector_process_groups[subsector]:
                    #        logger.warning(f"Process group {process_group} not found in subsector {subsector}")


                    # Get baseline fuel mix
                    if subsector in ["Alumina", "Aluminum", "Iron and Steel", "Cement+", "PetChem"]:
                        process_groups = subsector_process_groups[subsector]
                        for process_group, process_group_type in process_groups:
                            logger.info("==================================================================================================")
                            logger.info(f"Processing group: {process_group}")
                            logger.info("==================================================================================================")
                            # get the process group
                            # Generalized to work with the new form of the subsector_process_groups
                            if isinstance(process_group, tuple):
                                # Extract the lists of strings to match and not to match
                                match_strings, not_match_strings = process_group
                                # Create masks for both DataFrames separately
                                baseyear_mask = baseyear_consumption_pj["process"].str.lower().str.contains("|".join(match_strings))
                                thisyear_mask = thisyear_consumption_pj["process"].str.lower().str.contains("|".join(match_strings))
                                
                                # Apply not_match conditions
                                for not_match in not_match_strings:
                                    baseyear_mask &= ~baseyear_consumption_pj["process"].str.lower().str.contains(not_match)
                                    thisyear_mask &= ~thisyear_consumption_pj["process"].str.lower().str.contains(not_match)
                                
                                # Apply the masks
                                baseyear_group_consumption_pj = baseyear_consumption_pj[baseyear_mask]
                                thisyear_group_consumption_pj = thisyear_consumption_pj[thisyear_mask]
                                process_group = process_group[0][0]  # Update process_group to the first element of the first tuple element
                            else:
                                baseyear_group_consumption_pj = baseyear_consumption_pj[ baseyear_consumption_pj["process"].str.lower().str.contains(process_group)]
                                thisyear_group_consumption_pj = thisyear_consumption_pj[ thisyear_consumption_pj["process"].str.lower().str.contains(process_group)]
                            # if the baseyear_group_consumption_pj is empty, continue and log a warning
                            if baseyear_group_consumption_pj.empty:
                                logger.warning(f"No consumption found for {scen} {region} {subsector} {process_group}")
                                continue

                            baseyear_by_fuel = baseyear_group_consumption_pj.groupby("fuel", as_index=False).sum().drop(columns=["scen","region","process","subsector_p","year"])
                            thisyear_by_fuel = thisyear_group_consumption_pj.groupby("fuel", as_index=False).sum().drop(columns=["scen","region","process","subsector_p","year"])

                            baseline_fuel_consumption = baseyear_by_fuel.copy()
                            baseline_fuel_consumption["value"] = baseline_fuel_consumption["value"] * thisyear_production_mt / baseyear_production_mt

                            diff = baseline_fuel_consumption.copy()
                            diff["value"] = thisyear_by_fuel["value"] - baseline_fuel_consumption["value"]
                            diff.set_index("fuel", inplace=True)
                            diff_switch_fuels = diff.copy()

                            fuels_allowed_to_be_switched_from = sets_of_fuels_allowed_to_be_switched_from[process_group_type]
                            
                            # filter for values less than 0
                            from_fuels = diff_switch_fuels[diff_switch_fuels.index.isin(fuels_allowed_to_be_switched_from)]
                            from_fuels = from_fuels[from_fuels["value"] < 0]
                            to_fuels = diff_switch_fuels[diff_switch_fuels["value"] > 0]

                            # get the fractional version of the to_fuels (this could be efficiency based, but this will do for now)
                            to_fuels_fraction = to_fuels.copy()
                            to_fuels_fraction["value"] = to_fuels["value"] / to_fuels["value"].sum()

                            from_fuels_fraction = from_fuels.copy()
                            from_fuels_fraction["value"] = from_fuels["value"] / from_fuels["value"].sum()

                            logger.info( f"base year:\n{tabulate(baseyear_group_consumption_pj, headers='keys', tablefmt='pretty', showindex=False)}")
                            logger.info( f"base year fuel:\n{tabulate(baseyear_by_fuel, headers='keys', tablefmt='pretty', showindex=False)}")
                            logger.info( f"this year:\n{tabulate(thisyear_group_consumption_pj, headers='keys', tablefmt='pretty', showindex=False)}")
                            logger.info( f"this year fuel:\n{tabulate(thisyear_by_fuel, headers='keys', tablefmt='pretty', showindex=False)}")
                            logger.info( f"baseline fuel:\n{tabulate(baseline_fuel_consumption, headers='keys', tablefmt='pretty', showindex=False)}")
                            logger.info( f"diff:\n{tabulate(diff.reset_index(), headers='keys', tablefmt='pretty', showindex=False)}")
                            #logger.info( f"diff switch fuels:\n{tabulate(diff_switch_fuels.reset_index(), headers='keys', tablefmt='pretty', showindex=False)}")
                            #logger.info(f"Switch fuels: {switch_fuels}")

                            # this block just creates the switched and unswitched dataframes with the default being zero switched and all unswitched
                            switched = thisyear_group_consumption_pj.copy().groupby(["scen","region","subsector_p","year","fuel"], as_index=False).sum(numeric_only=True)
                            switched["entry_type"] = "fuel-switch"
                            switched["fuel-switched-from"] = switched["fuel"]
                            switched["fuel-switched-to"] = switched["fuel"]
                            switched["process-group"] = subsector.lower() + "-" + process_group
                            switched.set_index("fuel", inplace=True)
                            final_cols = ["scen","region","subsector_p","process-group","year","fuel-switched-from","fuel-switched-to","value","entry_type"]
                            switched = switched[final_cols]
                            unswitched = switched.copy()
                            unswitched["entry_type"] = "remaining-consumption"
                            switched["value"] = 0.0 

                            # Keep only the first row in switched
                            template_row = switched.iloc[[0]]
                            template_index = template_row.index[0]
                            switched = switched.drop(index=template_row.index)
                            # add a row for each from_fuel / to_fuel pair
                            for from_fuel in from_fuels.reset_index()["fuel"].values:
                                # add an energy efficiency row for each from_fuel
                                new_row = template_row.loc[template_index].copy()
                                new_row["fuel-switched-to"] = from_fuel
                                new_row["fuel-switched-from"] = from_fuel
                                new_row["value"] = 0.0
                                new_row["entry_type"] = "efficiency-improvement"
                                switched = pd.concat([switched, new_row.to_frame().T])
                                for to_fuel in to_fuels.reset_index()["fuel"].values:
                                    # add a fuel switch row for each from_fuel / to_fuel pair
                                    new_row = template_row.loc[template_index].copy()
                                    new_row["fuel-switched-to"] = to_fuel
                                    new_row["fuel-switched-from"] = from_fuel
                                    new_row["value"] = 0.0
                                    new_row["entry_type"] = "fuel-switch"
                                    switched = pd.concat([switched, new_row.to_frame().T])
                            switched = switched.reset_index(drop=True)
                            switched.set_index(["fuel-switched-from","fuel-switched-to"], inplace=True)

                            switched = switched.sort_index()
                            unswitched = unswitched.sort_index()

                            diff_backup = diff.copy()

                            multi_to_multi = (len(from_fuels) > 1 and len(to_fuels) > 1)

                            good_baseyear = True
                            if baseyear_production_mt <= 1e-3:
                                good_baseyear = False
                                logger.warning(f"Base year production is too small for {scen} {region} {subsector} {process_group}")
                                logger.warning(f"Base year production: {baseyear_production_mt}")
                                logger.warning(f"Base year consumption: {baseyear_consumption_pj}")
                                logger.warning(f"This year production: {thisyear_production_mt}")
                                logger.warning(f"This year consumption: {thisyear_consumption_pj}")
                                logger.info(f"switched:\n{tabulate(switched.reset_index()[final_cols], headers='keys', tablefmt='pretty', showindex=False)}")
                                logger.info(f"unswitched:\n{tabulate(unswitched[final_cols], headers='keys', tablefmt='pretty', showindex=False)}")
                                print("---")

                            if ((len(from_fuels) == 1 and len(to_fuels) >= 1) or (len(from_fuels) > 1 and len(to_fuels) == 1) or multi_to_multi) and good_baseyear: # TODO: or (len(from_fuels) > 0 and len(to_fuels) == 0):
                                logger.info(f"GOOD FUEL SWITCH: {len(from_fuels)} FROM, {len(to_fuels)} TO")
                                for from_fuel in from_fuels.reset_index()["fuel"].values:
                                    for to_fuel in to_fuels.reset_index()["fuel"].values:

                                        fraction_of_from_fuel = to_fuels_fraction.loc[to_fuel, "value"]
                                        fraction_of_to_fuel = from_fuels_fraction.loc[from_fuel, "value"]
 
                                        #if multi_to_multi:
                                        #    # when there is no way to split the fuel, we just assume some rules
                                        #    fraction_of_from_fuel = 1.0
                                        #    fraction_of_to_fuel = 1.0
                                        #    if (from_fuel, to_fuel) not in multi_to_multi_rules[process_group]:
                                        #        
                                        #        logger.error(f"No way to split fuel {from_fuel} to {to_fuel} for process group {process_group}")
                                        #        raise ValueError(f"No way to split fuel {from_fuel} to {to_fuel} for process group {process_group}")

                                        all_to_fuel_switched_value = -diff_switch_fuels.loc[from_fuel, "value"]
                                        from_switched_value = all_to_fuel_switched_value*fraction_of_from_fuel
                                        assert from_switched_value > 0
                                        to_switched_value = diff_backup.loc[to_fuel, "value"]*fraction_of_to_fuel
                                        assert to_switched_value > 0
                                        logger.info(f"Switching {fraction_of_from_fuel*100:.0f}% of {all_to_fuel_switched_value:.2f} ({from_switched_value:.2f} PJ) of {from_fuel} to {to_fuel}")
                                        # add the value to the switch
                                        switched.loc[(from_fuel, to_fuel), "value"] += from_switched_value
                                        logger.info(f"Added {from_switched_value:.2f} PJ to switched {from_fuel} to {to_fuel}")
                                        # remove the to_switched_value from the unswitched
                                        unswitched.loc[to_fuel, "value"] -= to_switched_value
                                        logger.info(f"Removed {to_switched_value:.2f} PJ from unswitched {to_fuel}")
                                        # add the switch from the diff (not diff_switch_fuels) such that what remains must be energy efficiency related
                                        diff.loc[from_fuel, "value"] += from_switched_value
                                        diff.loc[to_fuel, "value"] -= to_switched_value
                                        logger.info( f"remaining diff:\n{tabulate(diff.reset_index(), headers='keys', tablefmt='pretty', showindex=False)}")
                                        # If to_fuel is Electricity, then set entry_type to electrification
                                        if to_fuel == "Electricity":
                                            switched.loc[(from_fuel, to_fuel), "entry_type"] = "electrification"


                                # for each non-zero entry remaining in diff, index into switched as (from_fuel, from_fuel) and set the value to the remaining diff and entry_type to efficiency-improvement
                                for fuel in diff.reset_index()["fuel"].values:
                                    if not np.isclose(diff.loc[fuel, "value"], 0, atol=1e-12):
                                        efficiency_value = -diff.loc[fuel, "value"]
                                        assert efficiency_value > 0
                                        switched.loc[(fuel, fuel), "value"] = efficiency_value
                                        switched.loc[(fuel, fuel), "entry_type"] = "efficiency-improvement"
                                        # add this into diff
                                        diff.loc[fuel, "value"] += efficiency_value

                                # assert that all values in diff are zero
                                assert np.isclose(diff["value"], 0, atol=1e-12).all()

                                # Drop rows with zero value in switched
                                switched = switched[switched["value"] != 0]

                                logger.info(f"switched:\n{tabulate(switched.reset_index()[final_cols], headers='keys', tablefmt='pretty', showindex=False)}")
                                logger.info(f"unswitched:\n{tabulate(unswitched[final_cols], headers='keys', tablefmt='pretty', showindex=False)}")

                                # Set any values within an atol of 1e-12 to zero
                                switched.loc[np.isclose(switched["value"], 0, atol=1e-12), "value"] = 0
                                unswitched.loc[np.isclose(unswitched["value"], 0, atol=1e-12), "value"] = 0

                                # Assert all values are positive in switched and unswitched
                                assert (switched["value"] >= 0).all()
                                assert (unswitched["value"] >= 0).all()
                                # Check we counted everything
                                left_sum = switched["value"].sum() + unswitched["value"].sum()
                                right_sum = baseline_fuel_consumption.set_index("fuel")["value"].sum()
                                if not np.isclose(left_sum, right_sum, rtol=1e-8):
                                    print(f"Left side: {left_sum}")
                                    print(f"Right side: {right_sum}")
                                    print(f"Difference: {left_sum - right_sum}")
                                    logger.error("Fuel switching totals do not match within the relative tolerance")
                                    raise ValueError("Fuel switching totals do not match within the relative tolerance")

                            elif len(from_fuels) == 1 and len(to_fuels) > 1:
                                logger.warning("BAD FUEL SWITCH LEVEL 1")
                                logger.info(f"Final switch:\n{tabulate(switched, headers='keys', tablefmt='pretty', showindex=False)}")
                                logger.info(f"Final remain:\n{tabulate(unswitched, headers='keys', tablefmt='pretty', showindex=False)}")
                                print("---")
                            elif len(from_fuels) > 1 and len(to_fuels) >= 1:
                                logger.warning("BAD FUEL SWITCH LEVEL 2")
                                logger.info(f"Final switch:\n{tabulate(switched, headers='keys', tablefmt='pretty', showindex=False)}")
                                logger.info(f"Final remain:\n{tabulate(unswitched, headers='keys', tablefmt='pretty', showindex=False)}")
                                print("---")
                            elif len(from_fuels) > 0 and len(to_fuels) == 0:
                                logger.info("EFFICIENCY IMPROVEMENT")
                                logger.info(f"Final switch:\n{tabulate(switched, headers='keys', tablefmt='pretty', showindex=False)}")
                                logger.info(f"Final remain:\n{tabulate(unswitched, headers='keys', tablefmt='pretty', showindex=False)}")
                                print("---")
                            else:
                                logger.info("NO CHANGE")
                                logger.info(f"Final switch:\n{tabulate(switched, headers='keys', tablefmt='pretty', showindex=False)}")
                                logger.info(f"Final remain:\n{tabulate(unswitched, headers='keys', tablefmt='pretty', showindex=False)}")
                                print("---")

                            final_df = pd.concat([final_df, switched.reset_index()[final_cols], unswitched.reset_index()[final_cols]])
                            print("---")

                        print("---")

    # save the final_df to a csv
    final_df.to_csv(input_dir / "ind2-fuel-switch.csv", index=False)
    # save as a pickle
    final_df.to_pickle(input_dir / "ind2-fuel-switch.pkl")

    return final_df


def calculate_fuel_switching_logic(file_path: Path | str) -> None:
    """Calculate fuel switching metrics from a CSV or Excel file.

    Args:
        file_path: Path to the CSV or Excel file containing fuel switching data
    """
    input_path = Path(file_path).resolve()
    input_dir = input_path.parent
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
            logger.error(f"The missing varbls are: {set(ind2_output_varbls) - set(df['varbl'].unique())}")

        df = df[
            df["varbl"].isin(
                [
                    "FinEn_AEMO",
                    "FinEn_AEMO_eneff",
                    "FinEn_enser",
                    "FinEn_consumed",
                    "feedstock_consumption",
                ]
                + ind2_output_varbls + extra_ind2_output_varbls
            )
        ]

        # Cache the dataframe
        logger.info(f"Caching data to: {cache_path}")
        df.to_pickle(cache_path)

    # Varbl long descriptions from lmadefs
    # FinEn_AEMO (): Total production of energy services for Industry and Buildings. OK to check fuel mixes, but absolute values miss energy efficiency etc. Transport OK.
    # FinEn_AEMO_eneff (p,c): Production of energy services for Buildings and Industry - ONLY from EE, BFL, IFL, and ETI sources.
    # FinEn_enser (p,c): Production of energy services for Buildings and Industry - EXCEPT from EE, BFL, IFL, and ETI sources.
    # FinEn_consumed (p,c): Complete final energy - consumption of sector fuels. Hence, not very disaggregated for Industry and Buildings

    years = ["2025", "2030", "2035", "2040", "2045", "2050", "2055", "2060"]

    # drop 2015 and 2020 columns
    df = df.drop(columns=["2015", "2020"])


    cols_to_keep = [
        "scen",
        "region",
        "source_p",
        "subsectorgroup_c",
        "hydrogen_source",
        "unit",
    ]
    cols_we_use = ["process", "commodity", "varbl", "fuel"]

    # check to see if cols_to_keep + cols_we_use are in the df, and if not, log which are missing
    for col in cols_to_keep + cols_we_use:
        if col not in df.columns:
            logger.warning(f"Column {col} not found in the dataframe")

    new_cols = [
        "fuel-switched-from",
        "fuel-switched-to",
        "sector",
        "process_name",
        "entry_type",
    ]

    df_original = df.copy()

    # Retain only the relevant columns
    cols = cols_to_keep + cols_we_use
    df = df[cols + years]

    # Groupby the relevant columns and sum the values
    df = df.groupby(cols).sum().reset_index()

    final_cols = cols_to_keep + cols_we_use + new_cols + years
    csv_cols = cols_to_keep + new_cols + ["year"]
    df_fuel_switch_all = pd.DataFrame(columns=final_cols)

    df_ind2 = create_industry2_df(df_original, years, csv_cols, input_dir)

    # Get a list of all the processes
    # Strip the `-?` or `-??` suffix and remove duplicates
    # processes = [re.sub(r"-.{1,2}$", "", p) for p in processes]
    # processes = list(set(processes))
    # Loop through each process and calculate the fuel switching

    # sectors to process
    sectors = ["Industry", "Commercial", "Residential"]
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
            df_process = df_process[
                df_process["varbl"].isin(this_sector_structure["varbl_filter"])
            ]
            if sector == "Industry2":
                # Filter for column "is_ind2" = "yes"
                df_process = df_process[df_process["is_ind2"] == "yes"]

            # Extract the process name and fuel suffix
            if sector == "Industry":
                process_name_no_prefix = process.replace(process_prefix + "_", "")
                from_fuel_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(
                    f"-{from_fuel_suffix}", ""
                )
            elif sector == "Commercial":
                process_name_no_prefix = process.replace(process_prefix + "_", "")
                complete_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel_suffix = complete_suffix[0]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(f"-{complete_suffix}", "")
            elif sector == "Residential":
                process_name_no_prefix = process.replace(process_prefix, "")
                from_fuel_suffix = process_name_no_prefix.split("-")[-1]
                from_fuel = from_fuel_mapping[from_fuel_suffix]
                process_name = process_name_no_prefix.replace(
                    f"-{from_fuel_suffix}", ""
                )

            # Log the process name, from_fuel, and from_fuel_suffix
            logger.info(
                f"Process: {process_name}, From Fuel: {from_fuel}, From Fuel Suffix: {from_fuel_suffix}"
            )
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
                    if entry_type not in [
                        "remaining-consumption",
                        "energy-efficiency",
                        "automation",
                        "demand-reduction",
                    ]:
                        raise ValueError(
                            f"Entry type is not consumption or energy-efficiency (is {entry_type}) for {supply_process} -> {process} with from_fuel {from_fuel} and to_fuel {to_fuel}"
                        )
                if entry_type in ["fuel-switch", "electrification"]:
                    if to_fuel in [
                        "Coal",
                        "Natural Gas",
                        "LPG",
                        "Wood",
                        "Oil",
                        "Brown Coal",
                    ]:
                        logger.warning(
                            f"Entry type is {entry_type} for {supply_process} -> {process} with from_fuel {from_fuel} and to_fuel {to_fuel}"
                        )
                        raise ValueError(f"Fuel switch to {to_fuel} is not allowed")

                df_fuel_switch_all = pd.concat(
                    [df_fuel_switch_all, pd.DataFrame([new_row])], ignore_index=True
                )

            cnt += 1

    # For ES, CS, RS we use FinEn_AEMO_eneff + FinEn_enser to get the baseline energy demand

    # Save output to same directory as input
    output_path = input_path.parent / f"{input_path.stem}_fuel_switching.csv"
    # melt to long format
    df_fuel_switch_all = df_fuel_switch_all.melt(
        id_vars=cols_to_keep + cols_we_use + new_cols,
        value_vars=years,
        var_name="year",
        value_name="value",
    )
    # fill mising indice with "-"
    df_fuel_switch_all = df_fuel_switch_all.fillna("-")
    # find rows with sector = "Commercial" and "fuel-switched-to" = "Hydrogen" and set "hydrogen_source" = "Blended"
    df_fuel_switch_all.loc[
        (df_fuel_switch_all["sector"] == "Commercial")
        & (df_fuel_switch_all["fuel-switched-to"] == "Hydrogen"),
        "hydrogen_source",
    ] = "Blending"
    # remove rows where value is 0
    df_fuel_switch_all = df_fuel_switch_all[df_fuel_switch_all["value"] != 0]
    # remove rows where entry_type is not in ["remaining-consumption", "fuel-switch", "electrification"]
    df_fuel_switch_all = df_fuel_switch_all[
        df_fuel_switch_all["entry_type"].isin(
            ["remaining-consumption", "fuel-switch", "electrification"]
        )
    ]
    # drop the "source_p" column
    df_fuel_switch_all = df_fuel_switch_all.drop(
        columns=["source_p", "process", "commodity", "varbl", "fuel"]
    )
    # rename the subsectorgroup_c column to subsector
    df_fuel_switch_all = df_fuel_switch_all.rename(
        columns={"subsectorgroup_c": "subsector"}
    )
    # groupby csv_cols and sum the value
    _final_cols = [col for col in df_fuel_switch_all.columns if col != "value"]
    df_fuel_switch_all = df_fuel_switch_all.groupby(_final_cols).sum().reset_index()
    # drop the cols not grouped by
    df_fuel_switch_all = df_fuel_switch_all.drop(
        columns=[
            col
            for col in df_fuel_switch_all.columns
            if col not in _final_cols + ["value"]
        ]
    )

    # add a unit column to df_ind2
    df_ind2["unit"] = "PJ"
    # add a hydrogen_source column which is "Direct supply" for any row where "fuel-switched-to" = "Hydrogen" or "fuel-switched-from" = "Hydrogen"
    df_ind2["hydrogen_source"] = None
    df_ind2.loc[
        (df_ind2["fuel-switched-to"] == "Hydrogen") | (df_ind2["fuel-switched-from"] == "Hydrogen"),
        "hydrogen_source",
    ] = "Direct supply"
    # rename subsector_p to subsector
    df_ind2 = df_ind2.rename(columns={"subsector_p": "subsector"})
    # drop rows where entry_type is "efficiency-improvement"
    df_ind2 = df_ind2[df_ind2["entry_type"] != "efficiency-improvement"]

    # rename cols of df_fuel_switch_all as process_name to process-group
    df_fuel_switch_all = df_fuel_switch_all.rename(columns={"process_name": "process-group"})

    col_order = ['scen', 'region', 'subsector', 'process-group', 'year', 'unit', 'hydrogen_source', 'fuel-switched-from', 'fuel-switched-to', 'value', 'entry_type']
    df_ind2 = df_ind2[col_order]
    df_fuel_switch_all = df_fuel_switch_all[col_order]
    # concat df_fuel_switch_all and df_ind2
    df_fuel_switch_all = pd.concat([df_fuel_switch_all, df_ind2], ignore_index=True)

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
    # file_path = Path("~/scratch/processed_view_2024-12-06T09.14_MSM24.csv").expanduser()
    file_path = Path("~/scratch/raw_view_old_only-wide.xlsx").expanduser()
    calculate_fuel_switching_logic(file_path)
