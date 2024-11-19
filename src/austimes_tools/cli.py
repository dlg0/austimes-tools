import click
from austimes_tools.load_luto_data import load_luto_data
from austimes_tools.merge_appdata_json_files import merge_appdata_json_files

@click.group()
def cli():
    """Austimes Tools CLI - A collection of data processing utilities"""
    pass

# Register commands
cli.add_command(load_luto_data, name='load-luto')
cli.add_command(merge_appdata_json_files, name='merge-appdata')

if __name__ == '__main__':
    cli() 