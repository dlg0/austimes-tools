import rich_click as click
from austimes_tools.load_luto_data import load_luto_data
from austimes_tools.merge_appdata_json_files import merge_appdata_json_files_cli
from austimes_tools.pivot_year import pivot_file
from austimes_tools.create_msm22_csvs import process_msm22_files


@click.group()
def cli():
    """Austimes Tools CLI - A collection of data processing utilities"""
    pass


# Register commands
cli.add_command(load_luto_data, name="load-luto")
cli.add_command(merge_appdata_json_files_cli, name="merge-appdata")
cli.add_command(pivot_file, name="pivot-year")
cli.add_command(process_msm22_files, name="process-msm22")

if __name__ == "__main__":
    cli()
