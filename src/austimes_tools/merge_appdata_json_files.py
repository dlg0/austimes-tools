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


def merge_appdata_json_files(
    from_dir, prefix, into, confirm_merge=False, show_views=False
):
    """Merge AppData JSON files from one directory into another."""
    from_dir = Path(from_dir)
    into_dir = Path(into)

    if show_views:
        show_views_comparison(from_dir, into_dir, prefix)
        return

    # Define the file pairs to process
    file_pairs = [
        {
            "type": "Results",
            "views": "ResultViews.json",
            "details": "ResultViewsDetails.json",
        },
        {
            "type": "Reports",
            "views": "ReportTables.json",
            "details": "ReportTablesDetails.json",
        },
    ]

    # Format all source files first
    print("\nFormatting all source files...")
    files_to_format = []
    for pair in file_pairs:
        files_to_format.extend(
            [
                into_dir / pair["views"],
                into_dir / pair["details"],
                from_dir / f"{prefix}{pair['views']}",
                from_dir / f"{prefix}{pair['details']}",
            ]
        )

    for file in files_to_format:
        if file.exists():
            format_json_file(file)

    # Process each pair
    for pair in file_pairs:
        print(f"\nProcessing {pair['type']}...")
        base_views = into_dir / pair["views"]
        base_details = into_dir / pair["details"]

        # Get new paired entries
        views_entries, details_entries = get_new_paired_entries(
            prefix, from_dir, pair["views"], pair["details"]
        )

        # Preview new entries
        if preview_new_entries(views_entries, details_entries, pair["type"]):
            if confirm_merge:
                # Merge views
                merge_json_files(views_entries, str(base_views))
                # Merge details
                merge_json_files(details_entries, str(base_details))
            else:
                print(
                    "\nPreview mode: Use --confirm-merge to execute the merge operation"
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


def get_new_entries(source_file, base_file):
    """
    Compare source and base files to find new entries.
    Returns a list of new entries (those in source but not in base).
    """
    try:
        with open(source_file, "r", encoding="utf-8") as f:
            source_data = json.load(f)
        with open(base_file, "r", encoding="utf-8") as f:
            target_data = json.load(f)

        # Create sets of names for quick comparison
        target_names = {item["Name"] for item in target_data}
        source_names = {item["Name"] for item in source_data}
        new_entries = [item for item in source_data if item["Name"] not in target_names]

        logger.info(f"Comparing {source_file.name} with {base_file.name}")
        logger.info(f"Found {len(new_entries)} new entries")
        logger.debug("Target names: {}", target_names)
        logger.debug("New entries: {}", new_entries)

        return new_entries
    except Exception as e:
        logger.error(f"Error comparing files: {e}")
        return []


def preview_new_entries(views_entries, details_entries, type):
    """Show preview of new entries that would be merged."""
    if views_entries:
        print(f"\nNew {type} entries found:")
        # Sort entries by Name before displaying
        sorted_entries = sorted(views_entries, key=lambda x: x["Name"])
        for entry in sorted_entries:
            print(f"  - {entry['Name']}")
    else:
        print(f"\nNo new {type} entries found to merge.")

    return bool(views_entries)


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


def merge_json_files(new_entries, target_file_path):
    """Merge new entries into target file."""
    try:
        target_path = Path(target_file_path)
        print(f"\nMerging into target file: {target_path}")

        # Create backup
        backup_path = (
            target_path.parent / f"{target_path.stem}.backup{target_path.suffix}"
        )
        import shutil

        shutil.copy2(target_path, backup_path)
        print(f"Created backup file: {backup_path}")

        # Read target file
        with open(target_file_path, "r", encoding="utf-8") as f:
            target_data = json.load(f)

        # Add new entries and sort
        target_data.extend(new_entries)
        target_data.sort(key=lambda x: x["Name"])

        # Write merged result
        with open(target_file_path, "w", encoding="utf-8") as f:
            json.dump(target_data, f, indent=2, sort_keys=True)

        print(f"Successfully merged {len(new_entries)} new entries into: {target_path}")

    except Exception as e:
        print(f"Error merging files: {e}")


def show_views_comparison(from_dir: Path, into_dir: Path, prefix: str):
    """Display a comparison table of views in source and target directories."""
    file_pairs = [("Results", "ResultViews.json"), ("Reports", "ReportTables.json")]

    for type_name, filename in file_pairs:
        try:
            source_file = from_dir / f"{prefix}{filename}"
            target_file = into_dir / filename

            with open(source_file, "r", encoding="utf-8") as f:
                source_views = {item["Name"] for item in json.load(f)}
            with open(target_file, "r", encoding="utf-8") as f:
                target_views = {item["Name"] for item in json.load(f)}

            # Create comparison data
            all_views = sorted(source_views | target_views)
            table_data = []
            for view in all_views:
                source_mark = "✓" if view in source_views else ""
                target_mark = "✓" if view in target_views else ""
                table_data.append([view, source_mark, target_mark])

            # Print table
            headers = ["View Name", "Source", "Target"]
            print(f"\n{type_name} Views Comparison:")
            print(tabulate(table_data, headers=headers, tablefmt="grid"))

            # Print summary
            only_in_source = source_views - target_views
            only_in_target = target_views - source_views
            print(f"\nSummary:")
            print(f"  Views only in source: {len(only_in_source)}")
            print(f"  Views only in target: {len(only_in_target)}")
            print(f"  Views in both: {len(source_views & target_views)}")

        except FileNotFoundError as e:
            print(f"\nSkipping {type_name} - Could not find required files")
        except json.JSONDecodeError as e:
            print(f"\nError: Invalid JSON in {type_name} file - {e}")


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
    help="Optional prefix of the ResultViews files to merge (e.g., 'Transport' for TransportResultViews.json)",
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
    "--show-views",
    is_flag=True,
    help="Show a comparison table of views present in source and target directories",
)
def merge_appdata_json_files_cli(from_dir, prefix, into, confirm_merge, show_views):
    """Merge AppData JSON files from one directory into another.

    FROM_DIR is the source AppData directory containing the JSON files you want to merge from.
    """
    merge_appdata_json_files(from_dir, prefix, into, confirm_merge, show_views)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        merge_appdata_json_files_cli()
    else:
        # For development testing, call the function directly
        from_dir = Path("/Users/gre538/code/Model_Aus_TIMES/AppData")
        into_dir = Path("/Users/gre538/code/Model_Aus_TIMES_copy/AppData")
        prefix = ""
        show_views = False
        confirm_merge = False
        merge_appdata_json_files(from_dir, prefix, into_dir, confirm_merge, show_views)
