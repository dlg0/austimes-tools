import json
from pathlib import Path
import xml.dom.minidom
import click

@click.command()
@click.option('--appdata-dir', type=click.Path(exists=True), help="AppData directory containing JSON files")
@click.option('--interactive/--non-interactive', default=True, help="Run in interactive mode")
def merge_appdata_json_files(appdata_dir, interactive):
    """Merge AppData JSON files for result views."""
    if not appdata_dir:
        script_dir = Path(__file__).parent
        appdata_dir = script_dir.parent / 'AppData'
    else:
        appdata_dir = Path(appdata_dir)
    
    # Find all relevant JSON files, excluding the base files
    base_views = appdata_dir / 'ResultViews.json'
    base_details = appdata_dir / 'ResultViewsDetails.json'
    
    # Get all prefixed files (excluding base files and formatted versions)
    prefixed_views = [f for f in appdata_dir.glob('*ResultViews.json') 
                     if f != base_views and 'formatted' not in f.name]
    
    # Extract unique prefixes from the ResultViews files
    prefixes = []
    for file in prefixed_views:
        prefix = file.name.replace('ResultViews.json', '')
        if prefix:  # Only add non-empty prefixes
            prefixes.append(prefix)
    
    # Format all source files first
    print("\nFormatting all source files...")
    files_to_format = [base_views, base_details]
    for prefix in prefixes:
        files_to_format.extend([
            appdata_dir / f"{prefix}ResultViews.json",
            appdata_dir / f"{prefix}ResultViewsDetails.json"
        ])
    
    for file in files_to_format:
        if file.exists():
            format_json_file(file)
    
    # Show available prefixes for merging
    if not prefixes:
        print("\nNo prefixed files found to merge.")
        return
    
    print("\nAvailable file pairs:")
    for i, prefix in enumerate(prefixes):
        print(f"{i + 1}. {prefix}ResultViews.json and {prefix}ResultViewsDetails.json")
    
    # Get user selection
    print("\nEnter the number of the file pair you want to merge or press Enter to skip:")
    selection = input("File pair to merge: ").strip()
    
    if selection:
        try:
            idx = int(selection) - 1
            if 0 <= idx < len(prefixes):
                prefix = prefixes[idx]
                
                # Get new paired entries
                views_entries, details_entries = get_new_paired_entries(prefix, appdata_dir)
                
                # Preview new entries
                if preview_new_entries(views_entries, details_entries):
                    proceed = input("\nProceed with merge? (y/n): ").lower().strip()
                    if proceed == 'y':
                        # Merge ResultViews
                        merge_json_files(views_entries, str(base_views))
                        # Merge ResultViewsDetails
                        merge_json_files(details_entries, str(base_details))
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input. Please enter a number.")

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
        except:
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
    except:
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

if __name__ == "__main__":
    merge_appdata_json_files()
