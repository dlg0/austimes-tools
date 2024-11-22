import click
from austimes_tools.load_luto_data import load_luto_data
from austimes_tools.merge_appdata_json_files import merge_appdata_json_files_cli
from austimes_tools.pivot_csv import pivot_csv


@click.group()
def cli():
    """Austimes Tools CLI - A collection of data processing utilities"""
    pass


# Register commands
cli.add_command(load_luto_data, name="load-luto")
cli.add_command(merge_appdata_json_files_cli, name="merge-appdata")
cli.add_command(pivot_csv, name="pivot-csv")

if __name__ == "__main__":
    cli()
