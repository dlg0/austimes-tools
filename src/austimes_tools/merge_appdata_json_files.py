import json
from pathlib import Path
import xml.dom.minidom
import click
import xml.parsers.expat
from tabulate import tabulate

@click.command()
@click.argument('from_dir', type=click.Path(exists=True))
@click.option('--prefix', type=str, default="",
              help="Optional prefix of the ResultViews files to merge (e.g., 'Transport' for TransportResultViews.json)")
@click.option('--into', type=click.Path(exists=True), default="./",
              help="Target AppData directory to merge into (defaults to current directory)")
@click.option('--confirm-merge', is_flag=True, 
              help="Confirm and execute the merge operation. Without this flag, only preview mode is run")
@click.option('--show-views', is_flag=True,
              help="Show a comparison table of views present in source and target directories")
def merge_appdata_json_files(from_dir, prefix, into, confirm_merge, show_views):
    """Merge AppData JSON files from one directory into another.
    
    FROM_DIR is the source AppData directory containing the JSON files you want to merge from.
    """
    # Convert paths to Path objects
    from_dir = Path(from_dir)
    into_dir = Path(into)
    
    if show_views:
        show_views_comparison(from_dir, into_dir, prefix)
        return
    
    # Find all relevant JSON files, excluding the base files
    base_views = into_dir / 'ResultViews.json'
    base_details = into_dir / 'ResultViewsDetails.json'
    
    # Format all source files first
    print("\nFormatting all source files...")
    files_to_format = [
        base_views, 
        base_details,
        from_dir / f"{prefix}ResultViews.json",
        from_dir / f"{prefix}ResultViewsDetails.json"
    ]
    
    for file in files_to_format:
        if file.exists():
            format_json_file(file)
    
    # Get new paired entries
    views_entries, details_entries = get_new_paired_entries(prefix, from_dir)
    
    # Preview new entries
    if preview_new_entries(views_entries, details_entries):
        if confirm_merge:
            # Merge ResultViews
            merge_json_files(views_entries, str(base_views))
            # Merge ResultViewsDetails
            merge_json_files(details_entries, str(base_details))
        else:
            print("\nPreview mode: Use --confirm-merge to execute the merge operation")

def format_details_field(details_str):
    """Format the Details field which may contain JSON or XML content."""
    # Remove escaped quotes and newlines if present
    details_str = details_str.replace('\\"', '"').replace('\\r\\n', '\n')
    
    # Try parsing as JSON first
    try:
        # If it's JSON-encoded string, parse it
        data = json.loads(details_str)
        
        # Check if there's a PivotLayout field that contains XML
        if isinstance(data, dict) and 'PivotLayout' in data:
            data['PivotLayout'] = format_xml_string(data['PivotLayout'])
            
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
        formatted_xml = dom.toprettyxml(indent='  ')
        # Remove empty lines that minidom sometimes adds
        formatted_xml = '\n'.join([line for line in formatted_xml.split('\n') if line.strip()])
        return formatted_xml
    except xml.parsers.expat.ExpatError:
        return xml_str

def format_json_file(file_path):
    """Format and sort a JSON file, saving a formatted version with '-formatted' suffix."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # If data is a list and contains dictionaries with 'Name' field, sort by Name
        if isinstance(data, list) and all('Name' in item for item in data):
            data.sort(key=lambda x: x['Name'])
        
        # If this is a ResultViewsDetails file, format the Details fields
        if 'ResultViewsDetails' in file_path.name:
            for item in data:
                if 'Details' in item:
                    item['Details'] = format_details_field(item['Details'])
        
        # Create formatted version
        formatted_path = file_path.parent / f"{file_path.stem}-formatted{file_path.suffix}"
        with open(formatted_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        
        print(f"Created formatted version: {formatted_path.name}")
    except json.JSONDecodeError as e:
        print(f"Error formatting {file_path.name}: {e}")
    except Exception as e:
        print(f"Unexpected error formatting {file_path.name}: {e}")

def get_new_entries(source_file, base_file):
    """
    Compare source and base files to find new entries.
    Returns a list of new entries (those in source but not in base).
    """
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            source_data = json.load(f)
        with open(base_file, 'r', encoding='utf-8') as f:
            base_data = json.load(f)
            
        # Create sets of names for quick comparison
        base_names = {item['Name'] for item in base_data}
        new_entries = [item for item in source_data if item['Name'] not in base_names]
        
        return new_entries
    except Exception as e:
        print(f"Error comparing files: {e}")
        return []

def preview_new_entries(views_entries, details_entries):
    """Show preview of new entries that would be merged."""
    if views_entries:
        print("\nNew paired entries found:")
        # Sort entries by Name before displaying
        sorted_entries = sorted(views_entries, key=lambda x: x['Name'])
        for entry in sorted_entries:
            print(f"  - {entry['Name']}")
    else:
        print("\nNo new paired entries found to merge.")
    
    return bool(views_entries)

def get_new_paired_entries(prefix, appdata_dir):
    """
    Find new entries in ResultViews that have matching entries in ResultViewsDetails.
    Returns tuple of (views_entries, details_entries) that are paired and ready to merge.
    """
    base_views_path = appdata_dir / "ResultViews.json"
    base_details_path = appdata_dir / "ResultViewsDetails.json"
    prefixed_views_path = appdata_dir / f"{prefix}ResultViews.json"
    prefixed_details_path = appdata_dir / f"{prefix}ResultViewsDetails.json"
    
    try:
        # Load all required files
        with open(base_views_path, 'r', encoding='utf-8') as f:
            base_views = json.load(f)
        with open(prefixed_views_path, 'r', encoding='utf-8') as f:
            prefixed_views = json.load(f)
        with open(prefixed_details_path, 'r', encoding='utf-8') as f:
            prefixed_details = json.load(f)
            
        # Create lookup dictionaries
        base_view_names = {item['Name'] for item in base_views}
        details_lookup = {item['Name']: item for item in prefixed_details}
        
        # Find new entries that have matching details
        views_to_merge = []
        details_to_merge = []
        missing_details = []
        
        for view_entry in prefixed_views:
            name = view_entry['Name']
            if name not in base_view_names:
                if name in details_lookup:
                    views_to_merge.append(view_entry)
                    details_to_merge.append(details_lookup[name])
                else:
                    missing_details.append(name)
        
        # Log warnings for missing pairs (sorted)
        if missing_details:
            print("\nWARNING: The following entries in ResultViews have no matching ResultViewsDetails:")
            for name in sorted(missing_details):
                print(f"  - {name}")
        
        return views_to_merge, details_to_merge
        
    except Exception as e:
        print(f"Error comparing files: {e}")
        return [], []

def merge_json_files(new_entries, target_file_path):
    """
    Merge new entries into target file.
    Only adds complete entries that don't exist in the target file.
    """
    try:
        # Read target file
        with open(target_file_path, 'r', encoding='utf-8') as f:
            target_data = json.load(f)
        
        # Add new entries
        target_data.extend(new_entries)
            
        # Sort by Name
        target_data.sort(key=lambda x: x['Name'])
        
        # Write merged result
        with open(target_file_path, 'w', encoding='utf-8') as f:
            json.dump(target_data, f, indent=2, sort_keys=True)
        
        print(f"Successfully merged {len(new_entries)} new entries into {Path(target_file_path).name}")
            
    except Exception as e:
        print(f"Error merging files: {e}")

def show_views_comparison(from_dir: Path, into_dir: Path, prefix: str):
    """Display a comparison table of views in source and target directories."""
    try:
        # Load source and target views
        source_file = from_dir / f"{prefix}ResultViews.json"
        target_file = into_dir / "ResultViews.json"
        
        with open(source_file, 'r', encoding='utf-8') as f:
            source_views = {item['Name'] for item in json.load(f)}
        with open(target_file, 'r', encoding='utf-8') as f:
            target_views = {item['Name'] for item in json.load(f)}
        
        # Create comparison data
        all_views = sorted(source_views | target_views)
        table_data = []
        for view in all_views:
            source_mark = "✓" if view in source_views else ""
            target_mark = "✓" if view in target_views else ""
            table_data.append([view, source_mark, target_mark])
        
        # Print table
        headers = ["View Name", "Source", "Target"]
        print("\nViews Comparison:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Print summary
        only_in_source = source_views - target_views
        only_in_target = target_views - source_views
        print(f"\nSummary:")
        print(f"  Views only in source: {len(only_in_source)}")
        print(f"  Views only in target: {len(only_in_target)}")
        print(f"  Views in both: {len(source_views & target_views)}")
        
    except FileNotFoundError as e:
        print(f"Error: Could not find views file - {e}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in views file - {e}")

if __name__ == "__main__":
    merge_appdata_json_files()
