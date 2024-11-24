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


def get_filtered_entries(
    from_dir, into_dir, prefix, type_info, username=None, entry_name=None
):
    """Get filtered entries based on all criteria."""
    source_file = from_dir / f"{prefix}{type_info['files']['views']}"
    target_file = into_dir / type_info["files"]["views"]
    name_field = type_info["name_field"]

    # Load source and target data
    with open(source_file, "r", encoding="utf-8") as f:
        source_data = json.load(f)
    with open(target_file, "r", encoding="utf-8") as f:
        target_data = json.load(f)

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
                new_timestamp if update_timestamp else "",
            ]
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
                new_timestamp if update_timestamp else "",
            ]
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
        headers = [f"{type_info['type']} Name", "User", "Action", "Current Timestamp"]
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


def merge_appdata_json_files(
    from_dir,
    prefix,
    into,
    confirm_merge=False,
    show_results=True,
    show_reports=True,
    show_cases=True,
    show_groups=True,
    file_type=None,
    username=None,
    update_timestamp=False,
    entry_name=None,
):
    """Merge AppData JSON files from one directory into another."""
    from_dir = Path(from_dir)
    into_dir = Path(into)

    # Always show initial comparison first
    show_initial_comparison(from_dir, into_dir, prefix)

    # Filter file types if specified
    file_types_to_process = (
        {file_type: FILE_TYPES[file_type]} if file_type else FILE_TYPES
    )

    # Process each type
    for type_key, type_info in file_types_to_process.items():
        # Get filtered entries
        source_data, target_data = get_filtered_entries(
            from_dir, into_dir, prefix, type_info, username, entry_name
        )

        # Get entries to merge (from source to target)
        if type_info["has_details"]:
            views_to_merge, details_to_merge = get_new_paired_entries(
                prefix,
                from_dir,
                type_info["files"]["views"],
                type_info["files"]["details"],
                entry_name,
            )
        else:
            views_to_merge = get_new_entries(
                from_dir / f"{prefix}{type_info['files']['views']}",
                into_dir / type_info["files"]["views"],
                name_field=type_info["name_field"],
                username=username,
                entry_name=entry_name,
            )

        # Get entries to update timestamps (in target)
        entries_to_update = (
            []
            if not update_timestamp
            else get_entries_to_update(target_data, type_info, username, entry_name)
        )

        # Always show comparison table, even if empty
        show_type_comparison(
            type_info,
            views_to_merge,
            entries_to_update,
            username,
            entry_name,
            update_timestamp,
        )

        # Only perform merge if confirmed
        if confirm_merge:
            # Perform the actual merge for this type
            if type_info["has_details"]:
                if views_to_merge:
                    merge_json_files(
                        views_to_merge,
                        into_dir / type_info["files"]["views"],
                        type_info["name_field"],
                        type_info,
                        update_timestamp,
                    )
                    merge_json_files(
                        details_to_merge,
                        into_dir / type_info["files"]["details"],
                        type_info["name_field"],
                    )
            else:
                if views_to_merge:
                    merge_json_files(
                        views_to_merge,
                        into_dir / type_info["files"]["views"],
                        type_info["name_field"],
                        type_info,
                        update_timestamp,
                    )


def format_details_field(details_str):
    """Format the Details field which may contain JSON or XML content."""
    # Remove escaped quotes and newlines if present
    details_str = details_str.replace('\\"', '"').replace("\\r\\n", "\n")

    # Try parsing as JSON first
    try:
        # If it's JSON-encoded string, parse it
        data = json.loads(details_str)

        # Check if there's a PivotLayout field that contains XML
        if isinstance(data, dict) and "PivotLayout" in data:
            data["PivotLayout"] = format_xml_string(data["PivotLayout"])

        return json.dumps(data, indent=2)
    except json.JSONDecodeError:
        # If not JSON, try formatting as XML
        try:
            return format_xml_string(details_str)
        except xml.parsers.expat.ExpatError:
            # If neither JSON nor XML, return original string
            return details_str


def format_xml_string(xml_str):
    """Format XML string with proper indentation."""
    try:
        # Parse and format XML
        dom = xml.dom.minidom.parseString(xml_str)
        formatted_xml = dom.toprettyxml(indent="  ")
        # Remove empty lines that minidom sometimes adds
        formatted_xml = "\n".join(
            [line for line in formatted_xml.split("\n") if line.strip()]
        )
        return formatted_xml
    except xml.parsers.expat.ExpatError:
        return xml_str


def format_json_file(file_path):
    """Format and sort a JSON file, saving a formatted version with '-formatted' suffix."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # If data is a list and contains dictionaries with 'Name' field, sort by Name
        if isinstance(data, list) and all("Name" in item for item in data):
            data.sort(key=lambda x: x["Name"])

        # If this is a ResultViewsDetails file, format the Details fields
        if "ResultViewsDetails" in file_path.name:
            for item in data:
                if "Details" in item:
                    item["Details"] = format_details_field(item["Details"])

        # Create formatted version
        formatted_path = (
            file_path.parent / f"{file_path.stem}-formatted{file_path.suffix}"
        )
        with open(formatted_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

        print(f"Created formatted file: {formatted_path}")
    except json.JSONDecodeError as e:
        print(f"Error formatting {file_path}: {e}")
    except Exception as e:
        print(f"Unexpected error formatting {file_path}: {e}")


def get_new_entries(
    source_file, base_file, name_field="Name", username=None, entry_name=None
):
    """
    Compare source and base files to find new entries.
    Returns a list of new entries (those in source but not in base).
    """
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            source_data = json.load(f)
        with open(base_file, "r", encoding="utf-8") as f:
            target_data = json.load(f)

        # Filter by username if specified
        if username:
            source_data = [item for item in source_data if item["UserName"] == username]
            target_data = [item for item in target_data if item["UserName"] == username]

        # Filter by entry name if specified
        if entry_name:
            source_data = [
                item for item in source_data if item[name_field] == entry_name
            ]
            target_data = [
                item for item in target_data if item[name_field] == entry_name
            ]

        # Create composite keys (name + username) for comparison
        target_keys = {(item[name_field], item["UserName"]) for item in target_data}
        new_entries = [
            item
            for item in source_data
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

        # Load details file to match with new views
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
    try:
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
        target_data.sort(key=lambda x: (x[name_field], x["UserName"]))

        # Write merged result
        with open(target_file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=2, sort_keys=True)

        print(f"Successfully merged {len(new_entries)} new entries into: {target_path}")

    except Exception as e:
        print(f"Error merging files: {e}")


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


def show_initial_comparison(from_dir, into_dir, prefix):
    """Show a comparison table of all entries in source and target directories."""
    print("\nComparing entries in source and target directories:")

    all_data = []

    for type_key, type_info in FILE_TYPES.items():
        source_file = Path(from_dir) / f"{prefix}{type_info['files']['views']}"
        target_file = Path(into_dir) / type_info["files"]["views"]
        name_field = type_info["name_field"]

        try:
            with open(source_file, "r", encoding="utf-8") as f:
                source_data = json.load(f)
            with open(target_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)

            # Create sets of (name, username) tuples for comparison
            source_entries = {
                (item[name_field], item["UserName"]) for item in source_data
            }
            target_entries = {
                (item[name_field], item["UserName"]) for item in target_data
            }

            # Get all unique entries
            all_entries = source_entries | target_entries

            # Add rows to table data
            for name, username in sorted(all_entries):
                in_source = "✓" if (name, username) in source_entries else " "
                in_target = "✓" if (name, username) in target_entries else " "
                all_data.append(
                    [type_info["type"], name, username, in_source, in_target]
                )

        except FileNotFoundError:
            print(f"Warning: Could not find {source_file} or {target_file}")
        except json.JSONDecodeError:
            print(f"Warning: Error parsing JSON in {source_file} or {target_file}")

    # Print the table
    headers = ["Type", "Name", "User", "In Source", "In Target"]
    print(tabulate(all_data, headers=headers, tablefmt="grid"))


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
    "--show-all",
    is_flag=True,
    help="Show comparison tables for all file types",
)
@click.option(
    "--show-results",
    is_flag=True,
    help="Show a comparison table of Results views in source and target directories",
)
@click.option(
    "--show-reports",
    is_flag=True,
    help="Show a comparison table of Reports in source and target directories",
)
@click.option(
    "--show-cases",
    is_flag=True,
    help="Show a comparison table of Cases in source and target directories",
)
@click.option(
    "--show-groups",
    is_flag=True,
    help="Show a comparison table of Groups in source and target directories",
)
@click.option(
    "--type",
    "file_type",
    type=click.Choice(["results", "reports", "cases", "groups"], case_sensitive=False),
    help="Specify which type of files to merge (default: all types)",
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
    show_all,
    show_results,
    show_reports,
    show_cases,
    show_groups,
    file_type,
    username,
    update_timestamp,
    entry_name,
):
    """Merge AppData JSON files from one directory into another.

    FROM_DIR is the source AppData directory containing the JSON files you want to merge from.
    """
    # If show_all is True, set all show flags to True
    if show_all:
        show_results = True
        show_reports = True
        show_cases = True
        show_groups = True

    merge_appdata_json_files(
        from_dir,
        prefix,
        into,
        confirm_merge,
        show_results,
        show_reports,
        show_cases,
        show_groups,
        file_type,
        username,
        update_timestamp,
        entry_name,
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        merge_appdata_json_files_cli()
    else:
        # For development testing, call the function directly
        from_dir = Path("/Users/gre538/code/Model_Aus_TIMES/AppData")
        into_dir = Path("/Users/gre538/code/Model_Aus_TIMES_copy/AppData")
        prefix = ""
        show_results = False
        show_reports = False
        show_cases = False
        show_groups = False
        confirm_merge = False
        merge_appdata_json_files(
            from_dir,
            prefix,
            into_dir,
            confirm_merge,
            show_results,
            show_reports,
            show_cases,
            show_groups,
        )
