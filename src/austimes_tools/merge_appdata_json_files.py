import json
from pathlib import Path
import xml.dom.minidom
import click
import xml.parsers.expat
from tabulate import tabulate
from loguru import logger
import os
import shutil
from datetime import datetime
import orjson  # Add this to imports at top of file

# Configure logger
logger.remove()  # Remove default handler
logger.add("merge_appdata_json_files.log", rotation="10 MB", level="INFO")

# Update file_pairs to include all types
FILE_TYPES = {
    "results": {
        "type": "Results",
        "files": {"views": "ResultViews.json", "details": "ResultViewsDetails.json"},
        "has_details": True,
        "name_field": "Name",
    },
    "reports": {
        "type": "Reports",
        "files": {"views": "ReportTables.json", "details": "ReportTablesDetails.json"},
        "has_details": True,
        "name_field": "Name",
    },
    "cases": {
        "type": "Cases",
        "files": {"views": "Cases.json", "details": None},
        "has_details": False,
        "name_field": "Name",
    },
    "groups": {
        "type": "Groups",
        "files": {"views": "Groups.json", "details": None},
        "has_details": False,
        "name_field": "GroupName",
    },
}


def get_current_timestamp():
    """Get current timestamp in the required format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def update_timestamp(entries, type_info):
    """Update timestamp field for entries based on their type."""
    timestamp = get_current_timestamp()
    time_field = "CreatedOn" if type_info["type"] == "Groups" else "EditedOn"

    for entry in entries:
        entry[time_field] = timestamp

    return entries


def preprocess_data(data, file_name):
    """Ensure all entries have required fields and valid values."""
    for item in data:
        if "UserName" not in item:
            # logger.warning(f"Entry from {file_name} has no UserName, setting to 'gre538'")
            item["UserName"] = "gre538"
    return data


def get_filtered_entries(
    from_dir, into_dir, prefix, type_info, username=None, entry_name=None
):
    """Get filtered entries based on all criteria."""
    source_file = from_dir / f"{prefix}{type_info['files']['views']}"
    target_file = into_dir / type_info["files"]["views"]
    name_field = type_info["name_field"]

    # Load source and target data
    with open(source_file, "r", encoding="utf-8") as f:
        source_data = preprocess_data(json.load(f), source_file.name)
    with open(target_file, "r", encoding="utf-8") as f:
        target_data = preprocess_data(json.load(f), target_file.name)

    # Apply filters
    if username:
        source_data = [item for item in source_data if item["UserName"] == username]
        target_data = [item for item in target_data if item["UserName"] == username]

    if entry_name:
        source_data = [item for item in source_data if item[name_field] == entry_name]
        target_data = [item for item in target_data if item[name_field] == entry_name]

    return source_data, target_data


def show_type_comparison(
    type_info: dict,
    entries_to_merge: list,
    entries_to_update: list,
    username=None,
    entry_name=None,
    update_timestamp=False,
):
    """Display a comparison table of entries that will be merged and/or updated."""
    try:
        name_field = type_info["name_field"]
        time_field = "CreatedOn" if type_info["type"] == "Groups" else "EditedOn"
        new_timestamp = get_current_timestamp() if update_timestamp else None

        # Create comparison data
        table_data = []

        # Add entries to be merged
        for entry in entries_to_merge:
            name = entry[name_field]
            user = entry["UserName"]
            current_timestamp = entry.get(time_field, "")

            row = [
                name,
                user,
                "Merge",
                current_timestamp,
            ]
            if update_timestamp:
                row.append(new_timestamp)
            table_data.append(row)

        # Add entries to be updated
        for entry in entries_to_update:
            name = entry[name_field]
            user = entry["UserName"]
            current_timestamp = entry.get(time_field, "")

            row = [
                name,
                user,
                "Update",
                current_timestamp,
            ]
            if update_timestamp:
                row.append(new_timestamp)
            table_data.append(row)

        # Sort the table data
        table_data.sort(key=lambda x: (x[0], x[1]))  # Sort by name and username

        # Print table header
        print(f"\n{type_info['type']} Entries to Process:")
        if username:
            print(f"Filtered by username: {username}")
        if entry_name:
            print(f"Filtered by name: {entry_name}")
        if update_timestamp:
            print(f"New timestamp will be: {new_timestamp}")

        # Always print the table, even if empty
        headers = ["Name", "User", "Action", "Current Timestamp"]
        if update_timestamp:
            headers.append("New Timestamp")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

    except Exception as e:
        print(f"Error showing comparison: {e}")


def get_entries_to_update(
    target_data: list, type_info: dict, username=None, entry_name=None
):
    """Get entries from target that match filters and need timestamp update."""
    name_field = type_info["name_field"]
    filtered_entries = target_data.copy()

    if username:
        filtered_entries = [
            item for item in filtered_entries if item["UserName"] == username
        ]
    if entry_name:
        filtered_entries = [
            item for item in filtered_entries if item[name_field] == entry_name
        ]

    return filtered_entries


def load_and_preprocess_files(from_dir, into_dir, prefix, type_info):
    """Load and preprocess both source and target files."""
    source_file = from_dir / f"{prefix}{type_info['files']['views']}"
    target_file = into_dir / type_info["files"]["views"]

    with open(source_file, "r", encoding="utf-8") as f:
        source_data = preprocess_data(json.load(f), source_file.name)
    with open(target_file, "r", encoding="utf-8") as f:
        target_data = preprocess_data(json.load(f), target_file.name)

    return source_data, target_data, source_file, target_file


def merge_appdata_json_files(
    from_dir,
    prefix,
    into,
    confirm_merge=False,
    results_only=True,
    reports_only=True,
    cases_only=True,
    groups_only=True,
    username=None,
    update_timestamp=False,
    entry_name=None,
):
    """Merge AppData JSON files from one directory into another."""
    from_dir = Path(from_dir)
    into_dir = Path(into)

    # Load all data upfront (only views files, not details)
    loaded_data = {}
    enabled_types = set()

    for type_key, type_info in FILE_TYPES.items():
        # Skip types that aren't requested
        if (
            (type_key == "results" and not results_only)
            or (type_key == "reports" and not reports_only)
            or (type_key == "cases" and not cases_only)
            or (type_key == "groups" and not groups_only)
        ):
            continue

        # Only load the views files
        source_file = from_dir / f"{prefix}{type_info['files']['views']}"
        target_file = into_dir / type_info["files"]["views"]

        with open(source_file, "r", encoding="utf-8") as f:
            source_data = preprocess_data(json.load(f), source_file.name)
        with open(target_file, "r", encoding="utf-8") as f:
            target_data = preprocess_data(json.load(f), target_file.name)

        loaded_data[type_key] = (source_data, target_data, source_file, target_file)
        enabled_types.add(type_key)

    # Show initial comparison using loaded data
    show_initial_comparison(loaded_data)

    # Process each enabled type
    for type_key, type_info in FILE_TYPES.items():
        if type_key not in enabled_types:
            continue

        source_data, target_data, source_file, target_file = loaded_data[type_key]

        # Filter the data based on username and entry_name
        filtered_source = filter_data(source_data, type_info, username, entry_name)
        filtered_target = filter_data(target_data, type_info, username, entry_name)

        # Get entries to merge
        views_to_merge = get_new_entries_from_data(
            filtered_source, filtered_target, name_field=type_info["name_field"]
        )

        # Get entries to update timestamps (in target)
        entries_to_update = (
            []
            if not update_timestamp
            else get_entries_to_update(filtered_target, type_info, username, entry_name)
        )

        # Show comparison and perform merge
        show_type_comparison(
            type_info,
            views_to_merge,
            entries_to_update,
            username,
            entry_name,
            update_timestamp,
        )

        if confirm_merge:
            perform_merge(
                views_to_merge, from_dir, into_dir, prefix, type_info, update_timestamp
            )


def filter_data(data, type_info, username=None, entry_name=None):
    """Filter data based on username and entry_name."""
    filtered = data.copy()
    name_field = type_info["name_field"]

    if username:
        filtered = [item for item in filtered if item["UserName"] == username]
    if entry_name:
        filtered = [
            item for item in filtered if item[name_field].lower() == entry_name.lower()
        ]

    return filtered


def get_new_entries_from_data(source_data, target_data, name_field="Name"):
    """Compare source and target data to find new entries."""
    target_keys = {(item[name_field], item["UserName"]) for item in target_data}

    new_entries = [
        item
        for item in source_data
        if (item[name_field], item["UserName"]) not in target_keys
    ]

    return sorted(new_entries, key=lambda x: (x[name_field], x["UserName"]))


def show_initial_comparison(loaded_data):
    """Show a comparison table of all entries using pre-loaded data."""
    print("\nComparing entries in source and target directories:")
    all_data = []

    for type_key, (
        source_data,
        target_data,
        source_file,
        target_file,
    ) in loaded_data.items():
        type_info = FILE_TYPES[type_key]
        name_field = type_info["name_field"]

        # Create sets of (name, username) tuples for comparison
        source_entries = {(item[name_field], item["UserName"]) for item in source_data}
        target_entries = {(item[name_field], item["UserName"]) for item in target_data}

        # Get all unique entries
        all_entries = source_entries | target_entries

        # Add rows to table data
        for name, username in sorted(all_entries):
            in_source = "✓" if (name, username) in source_entries else " "
            in_target = "✓" if (name, username) in target_entries else " "
            all_data.append([type_info["type"], name, username, in_source, in_target])

    # Print the table
    headers = ["Type", "Name", "User", "In Source", "In Target"]
    print(tabulate(all_data, headers=headers, tablefmt="grid"))


def format_nested_json(data):
    """Recursively format any JSON strings found in the data structure."""
    if isinstance(data, dict):
        return {key: format_nested_json(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [format_nested_json(item) for item in data]
    elif isinstance(data, str):
        try:
            # For Filter fields, log the attempt
            is_filter = any(k == "Filter" for k, v in locals().items() if v is data)
            
            # Try to parse string as JSON
            parsed = orjson.loads(data)
            
            # If successful and this is a Filter field, log success
            if is_filter:
                logger.info("Parse and format a Filter JSON field: SUCCESS")
            
            # Recursively format the parsed data
            return orjson.dumps(
                format_nested_json(parsed),
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
            ).decode('utf-8')
        except (orjson.JSONDecodeError, ValueError):
            # If parsing failed and this is a Filter field, log the failure
            if is_filter:
                logger.warning("Parse and format a Filter JSON field: FAILED")
            return data
    else:
        return data

def format_json_file(file_path, in_place=False):
    """Format and sort a JSON file, detecting and formatting any nested JSON strings."""
    try:
        # Read the file
        with open(file_path, "r", encoding="utf-8") as f:
            data = orjson.loads(f.read())

        # Sort by Name if applicable
        if isinstance(data, list) and all("Name" in item for item in data):
            data.sort(key=lambda x: x["Name"])

        # Recursively format any nested JSON strings
        formatted_data = format_nested_json(data)

        # Determine output path
        output_path = file_path if in_place else file_path.parent / f"{file_path.stem}-formatted{file_path.suffix}"
        
        # Write the formatted JSON
        with open(output_path, "wb") as f:
            f.write(orjson.dumps(
                formatted_data,
                option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
            ))

        if not in_place:
            print(f"Created formatted file: {output_path}")

    except Exception as e:
        logger.error(f"Error formatting {file_path}: {e}")


def get_new_entries(
    source_file, base_file, name_field="Name", username=None, entry_name=None
):
    """
    Compare source and base files to find new entries.
    Returns a list of new entries (those in source but not in base).
    """
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            source_data = preprocess_data(json.load(f), source_file.name)
        with open(base_file, "r", encoding="utf-8") as f:
            target_data = preprocess_data(json.load(f), base_file.name)

        # Create composite keys (name + username) for comparison
        target_keys = {(item[name_field], item["UserName"]) for item in target_data}

        # Filter source data
        filtered_source = source_data
        if username:
            filtered_source = [
                item for item in filtered_source if item["UserName"] == username
            ]
        if entry_name:
            filtered_source = [
                item
                for item in filtered_source
                if item[name_field].lower() == entry_name.lower()
            ]

        # Find new entries
        new_entries = [
            item
            for item in filtered_source
            if (item[name_field], item["UserName"]) not in target_keys
        ]

        # Sort by name and username
        new_entries.sort(key=lambda x: (x[name_field], x["UserName"]))

        return new_entries
    except Exception as e:
        logger.error(f"Error comparing files: {e}")
        return []


def preview_new_entries(views_entries, details_entries=None, type_name=""):
    """Show preview of new entries that would be merged."""
    if not views_entries:
        print(f"\nNo new {type_name} entries found to merge.")
        return False

    print(f"\nNew {type_name} entries found:")
    # Use GroupName for Groups, Name for others
    name_field = "GroupName" if type_name == "Groups" else "Name"
    sorted_entries = sorted(views_entries, key=lambda x: (x[name_field], x["UserName"]))
    for entry in sorted_entries:
        print(f"  - {entry[name_field]} (User: {entry['UserName']})")

    return True


def get_new_paired_entries(
    prefix, appdata_dir, views_file, details_file, entry_name=None
):
    """Find new entries in views that have matching entries in details."""
    base_views_path = appdata_dir / views_file
    base_details_path = appdata_dir / details_file
    prefixed_views_path = appdata_dir / f"{prefix}{views_file}"
    prefixed_details_path = appdata_dir / f"{prefix}{details_file}"

    try:
        # Get new entries using the existing function
        views_entries = get_new_entries(
            prefixed_views_path, base_views_path, entry_name=entry_name
        )

        # Load details file to match wTrueith new views
        with open(prefixed_details_path, "r", encoding="utf-8") as f:
            prefixed_details = json.load(f)

        # Create lookup for details
        details_lookup = {item["Name"]: item for item in prefixed_details}

        # Match views with details
        views_to_merge = []
        details_to_merge = []
        missing_details = []

        for view_entry in views_entries:
            name = view_entry["Name"]
            if name in details_lookup:
                views_to_merge.append(view_entry)
                details_to_merge.append(details_lookup[name])
            else:
                missing_details.append(name)

        # Log warnings for missing pairs (sorted)
        if missing_details:
            print("\nWARNING: The following entries have no matching details:")
            for name in sorted(missing_details):
                print(f"  - {name}")

        return views_to_merge, details_to_merge

    except FileNotFoundError as e:
        logger.error(f"Error reading files: {e}")
        return [], []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        return [], []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return [], []


def merge_json_files(
    new_entries,
    target_file_path,
    name_field="Name",
    type_info=None,
    update_timestamp_flag=False,
):
    """Merge new entries into target file."""
    # try:
    target_path = Path(target_file_path)
    print(f"\nMerging into target file: {target_path}")

    # Create backup
    backup_path = backup_file(str(target_path))
    print(f"Created backup file: {backup_path}")

    # Read target file
    with open(target_file_path, "r", encoding="utf-8") as f:
        target_data = json.load(f)

    # Update timestamps if requested and this is a views file (not details)
    if (
        update_timestamp_flag
        and type_info
        and not type_info["files"]["views"].endswith("Details.json")
    ):
        new_entries = update_timestamp(new_entries, type_info)

    # Add new entries and sort by name and username
    target_data.extend(new_entries)
    target_data.sort(key=lambda x: (x[name_field], x.get("UserName", "")))
    # Write merged result
    with open(target_file_path, "w", encoding="utf-8") as f:
        json.dump(target_data, f, indent=2, sort_keys=True)

    print(f"Successfully merged {len(new_entries)} new entries into: {target_path}")

    # except Exception as e:
    #    print(f"Error merging files: {e}")


def get_unique_backup_path(file_path: str) -> str:
    """Generate a unique backup file path by adding a counter if needed."""
    backup_path = f"{file_path}.bak"
    counter = 1

    while os.path.exists(backup_path):
        backup_path = f"{file_path}.bak.{counter}"
        counter += 1

    return backup_path


def backup_file(file_path: str) -> str:
    """Create a backup of the file with a unique name."""
    backup_path = get_unique_backup_path(file_path)
    shutil.copy2(file_path, backup_path)
    return backup_path


def perform_merge(
    views_entries, from_dir, into_dir, prefix, type_info, update_timestamp
):
    """Perform the actual merge operation, loading details files only when needed."""
    if not views_entries:
        return

    # Merge views entries
    target_views_path = into_dir / type_info["files"]["views"]
    merge_json_files(
        views_entries,
        target_views_path,
        type_info["name_field"],
        type_info,
        update_timestamp,
    )
    # Format the merged file in place
    format_json_file(target_views_path, in_place=True)

    # If this type has details, handle them now
    if type_info["has_details"] and type_info["files"]["details"]:
        # Load source details file
        source_details_path = from_dir / f"{prefix}{type_info['files']['details']}"
        target_details_path = into_dir / type_info["files"]["details"]

        try:
            with open(source_details_path, "r", encoding="utf-8") as f:
                source_details = json.load(f)

            # Find matching details entries based on name only
            details_to_merge = []
            source_details_dict = {item["Name"]: item for item in source_details}

            for view_entry in views_entries:
                view_name = view_entry[type_info["name_field"]]
                if view_name in source_details_dict:
                    details_to_merge.append(source_details_dict[view_name])
                else:
                    logger.warning(f"No matching details found for view: {view_name}")

            # Merge details entries if any were found
            if details_to_merge:
                merge_json_files(
                    details_to_merge,
                    target_details_path,
                    "Name",
                    None,  # Don't pass type_info for details files
                    False,  # Don't update timestamps for details files
                )
                # Format the merged details file in place
                format_json_file(target_details_path, in_place=True)
        except Exception as e:
            logger.error(f"Error processing details file: {e}")
            raise


@click.command()
@click.argument("from_dir", type=click.Path(exists=True))
@click.option(
    "--prefix",
    type=str,
    default="",
    help="Optional prefix of the files to merge (e.g., 'Transport' for TransportResultViews.json)",
)
@click.option(
    "--into",
    type=click.Path(exists=True),
    default="./",
    help="Target AppData directory to merge into (defaults to current directory)",
)
@click.option(
    "--confirm-merge",
    is_flag=True,
    help="Confirm and execute the merge operation. Without this flag, only preview mode is run",
)
@click.option(
    "--results-only",
    is_flag=True,
    help="Only process Results views",
)
@click.option(
    "--reports-only",
    is_flag=True,
    help="Only process Reports",
)
@click.option(
    "--cases-only",
    is_flag=True,
    help="Only process Cases",
)
@click.option(
    "--groups-only",
    is_flag=True,
    help="Only process Groups",
)
@click.option(
    "--username",
    type=str,
    help="Filter operations to only include entries for a specific username",
)
@click.option(
    "--update-timestamp",
    is_flag=True,
    help="Update the timestamp of merged entries to current date/time",
)
@click.option(
    "--entry-name",
    type=str,
    help="Filter operations to only include entries with this specific name",
)
def merge_appdata_json_files_cli(
    from_dir,
    prefix,
    into,
    confirm_merge,
    results_only,
    reports_only,
    cases_only,
    groups_only,
    username,
    update_timestamp,
    entry_name,
):
    """Merge AppData JSON files from one directory into another.

    FROM_DIR is the source AppData directory containing the JSON files you want to merge from.
    """
    # If no specific type is selected, process all types
    if not any([results_only, reports_only, cases_only, groups_only]):
        results_only = reports_only = cases_only = groups_only = True

    merge_appdata_json_files(
        from_dir,
        prefix,
        into,
        confirm_merge,
        results_only,
        reports_only,
        cases_only,
        groups_only,
        username=username,
        update_timestamp=update_timestamp,
        entry_name=entry_name,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        merge_appdata_json_files_cli()
    else:
        # For development testing, call the function directly
        from_dir = Path("/Users/gre538/code/Model_Aus_TIMES_copy/AppData")
        into_dir = Path("/Users/gre538/code/Model_Aus_TIMES/AppData")
        prefix = ""
        results_only = False
        reports_only = True
        cases_only = False
        groups_only = False
        confirm_merge = True
        update_timestamp = False
        entry_name = None
        merge_appdata_json_files(
            from_dir,
            prefix,
            into_dir,
            confirm_merge,
            results_only,
            reports_only,
            cases_only,
            groups_only,
            username=None,
            update_timestamp=update_timestamp,
            entry_name=entry_name,
        )
