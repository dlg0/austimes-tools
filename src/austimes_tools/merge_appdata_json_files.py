import json
from pathlib import Path
import xml.dom.minidom
import click
import xml.parsers.expat
from tabulate import tabulate
from loguru import logger
import os
import shutil

# Configure logger
logger.remove()  # Remove default handler
logger.add("merge_appdata_json_files.log", rotation="10 MB", level="INFO")

# Update file_pairs to include all types
FILE_TYPES = {
    "results": {
        "type": "Results",
        "files": {
            "views": "ResultViews.json",
            "details": "ResultViewsDetails.json"
        },
        "has_details": True,
        "name_field": "Name"
    },
    "reports": {
        "type": "Reports",
        "files": {
            "views": "ReportTables.json",
            "details": "ReportTablesDetails.json"
        },
        "has_details": True,
        "name_field": "Name"
    },
    "cases": {
        "type": "Cases",
        "files": {
            "views": "Cases.json",
            "details": None
        },
        "has_details": False,
        "name_field": "Name"
    },
    "groups": {
        "type": "Groups",
        "files": {
            "views": "Groups.json",
            "details": None
        },
        "has_details": False,
        "name_field": "GroupName"
    }
}

def merge_appdata_json_files(
    from_dir, 
    prefix, 
    into, 
    confirm_merge=False, 
    show_results=False,
    show_reports=False,
    show_cases=False,
    show_groups=False,
    file_type=None,
    username=None
):
    """Merge AppData JSON files from one directory into another."""
    from_dir = Path(from_dir)
    into_dir = Path(into)

    # Handle show comparisons
    if any([show_results, show_reports, show_cases, show_groups]):
        if show_results:
            show_type_comparison(from_dir, into_dir, prefix, FILE_TYPES['results'], username)
        if show_reports:
            show_type_comparison(from_dir, into_dir, prefix, FILE_TYPES['reports'], username)
        if show_cases:
            show_type_comparison(from_dir, into_dir, prefix, FILE_TYPES['cases'], username)
        if show_groups:
            show_type_comparison(from_dir, into_dir, prefix, FILE_TYPES['groups'], username)
        return

    # Filter file types if specified
    file_types_to_process = {}
    if file_type:
        if file_type not in FILE_TYPES:
            print(f"Error: Unknown file type '{file_type}'. Valid types are: {', '.join(FILE_TYPES.keys())}")
            return
        file_types_to_process = {file_type: FILE_TYPES[file_type]}
    else:
        file_types_to_process = FILE_TYPES

    # Format all source files first
    print("\nFormatting all source files...")
    files_to_format = []
    for type_info in file_types_to_process.values():
        files_to_format.append(into_dir / type_info['files']['views'])
        if type_info['has_details']:
            files_to_format.append(into_dir / type_info['files']['details'])
        files_to_format.append(from_dir / f"{prefix}{type_info['files']['views']}")
        if type_info['has_details']:
            files_to_format.append(from_dir / f"{prefix}{type_info['files']['details']}")

    for file in files_to_format:
        if file.exists():
            format_json_file(file)

    # Process each type
    for type_key, type_info in file_types_to_process.items():
        print(f"\nProcessing {type_info['type']}...")
        base_views = into_dir / type_info['files']['views']

        if type_info['has_details']:
            base_details = into_dir / type_info['files']['details']
            # Get new paired entries
            views_entries, details_entries = get_new_paired_entries(
                prefix, from_dir, type_info['files']['views'], type_info['files']['details']
            )
        else:
            # Get new unpaired entries
            views_entries = get_new_entries(
                from_dir / f"{prefix}{type_info['files']['views']}", 
                base_views,
                name_field=type_info['name_field'],
                username=username
            )
            details_entries = None

        # Preview and merge
        if type_info['has_details']:
            if preview_new_entries(views_entries, details_entries, type_info['type']):
                if confirm_merge:
                    merge_json_files(views_entries, str(base_views))
                    merge_json_files(details_entries, str(base_details))
                else:
                    print("\nPreview mode: Use --confirm-merge to execute the merge operation")
        else:
            if preview_new_entries(views_entries, None, type_info['type']):
                if confirm_merge:
                    merge_json_files(views_entries, str(base_views), name_field=type_info['name_field'])
                else:
                    print("\nPreview mode: Use --confirm-merge to execute the merge operation")

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
        print(f"\nReading source file: {file_path}")
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

def get_new_entries(source_file, base_file, name_field="Name", username=None):
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

        # Create composite keys (name + username) for comparison
        target_keys = {(item[name_field], item["UserName"]) for item in target_data}
        new_entries = [
            item for item in source_data 
            if (item[name_field], item["UserName"]) not in target_keys
        ]

        # Sort by name and username
        new_entries.sort(key=lambda x: (x[name_field], x["UserName"]))

        logger.info(f"Comparing {source_file.name} with {base_file.name}")
        logger.info(f"Found {len(new_entries)} new entries")
        if username:
            logger.info(f"Filtered by username: {username}")
        
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

def get_new_paired_entries(prefix, appdata_dir, views_file, details_file):
    """Find new entries in views that have matching entries in details."""
    base_views_path = appdata_dir / views_file
    base_details_path = appdata_dir / details_file
    prefixed_views_path = appdata_dir / f"{prefix}{views_file}"
    prefixed_details_path = appdata_dir / f"{prefix}{details_file}"

    try:
        print(f"\nReading source views: {prefixed_views_path}")
        print(f"Reading source details: {prefixed_details_path}")
        print(f"Reading target views: {base_views_path}")
        print(f"Reading target details: {base_details_path}")

        # Get new entries using the existing function
        views_entries = get_new_entries(prefixed_views_path, base_views_path)

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
        print(f"Error reading files: {e}")
        return [], []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return [], []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return [], []

def merge_json_files(new_entries, target_file_path, name_field="Name"):
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

        # Add new entries and sort by name and username
        target_data.extend(new_entries)
        target_data.sort(key=lambda x: (x[name_field], x["UserName"]))

        # Write merged result
        with open(target_file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=2, sort_keys=True)

        print(f"Successfully merged {len(new_entries)} new entries into: {target_path}")

    except Exception as e:
        print(f"Error merging files: {e}")

def show_type_comparison(from_dir: Path, into_dir: Path, prefix: str, type_info: dict, username=None):
    """Display a comparison table of entries in source and target directories for a specific type."""
    try:
        source_file = from_dir / f"{prefix}{type_info['files']['views']}"
        target_file = into_dir / type_info['files']['views']
        name_field = type_info['name_field']

        with open(source_file, "r", encoding="utf-8") as f:
            source_data = json.load(f)
        with open(target_file, "r", encoding="utf-8") as f:
            target_data = json.load(f)

        # Filter by username if specified
        if username:
            source_data = [item for item in source_data if item["UserName"] == username]
            target_data = [item for item in target_data if item["UserName"] == username]

        # Create composite keys (name + username)
        source_entries = {(item[name_field], item["UserName"]) for item in source_data}
        target_entries = {(item[name_field], item["UserName"]) for item in target_data}

        # Create comparison data
        all_entries = sorted(source_entries | target_entries)
        table_data = []
        for name, user in all_entries:
            source_mark = "✓" if (name, user) in source_entries else ""
            target_mark = "✓" if (name, user) in target_entries else ""
            table_data.append([name, user, source_mark, target_mark])

        # Print table
        headers = [f"{type_info['type']} Name", "User", "Source", "Target"]
        print(f"\n{type_info['type']} Comparison:")
        if username:
            print(f"Filtered by username: {username}")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))

        # Print summary
        only_in_source = source_entries - target_entries
        only_in_target = target_entries - source_entries
        print(f"\nSummary:")
        print(f"  Entries only in source: {len(only_in_source)}")
        print(f"  Entries only in target: {len(only_in_target)}")
        print(f"  Entries in both: {len(source_entries & target_entries)}")

    except FileNotFoundError as e:
        print(f"\nSkipping {type_info['type']} - Could not find required files")
    except json.JSONDecodeError as e:
        print(f"\nError: Invalid JSON in {type_info['type']} file - {e}")

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
    type=click.Choice(['results', 'reports', 'cases', 'groups'], case_sensitive=False),
    help="Specify which type of files to merge (default: all types)",
)
@click.option(
    "--username",
    type=str,
    help="Filter operations to only include entries for a specific username",
)
def merge_appdata_json_files_cli(
    from_dir, 
    prefix, 
    into, 
    confirm_merge, 
    show_results,
    show_reports,
    show_cases,
    show_groups,
    file_type,
    username
):
    """Merge AppData JSON files from one directory into another.

    FROM_DIR is the source AppData directory containing the JSON files you want to merge from.
    """
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
        username
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
        merge_appdata_json_files(from_dir, prefix, into_dir, confirm_merge, show_results, show_reports, show_cases, show_groups)
