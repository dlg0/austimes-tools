import click
from austimes_tools.load_luto_data import load_luto_data
from austimes_tools.merge_appdata_json_files import merge_appdata_json_files_cli
from austimes_tools.pivot_year import pivot_file


@click.group()
def cli():
    """Austimes Tools CLI - A collection of data processing utilities"""
    pass


# Register commands
cli.add_command(load_luto_data, name="load-luto")
cli.add_command(merge_appdata_json_files_cli, name="merge-appdata")
cli.add_command(pivot_file, name="pivot-year")

if __name__ == "__main__":
    cli()
