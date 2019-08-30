import argparse
from pathlib import Path
import string

import pkg_resources

parser = argparse.ArgumentParser("RuTracker search plugin installation.")

parser.add_argument("--ini", required=True, type=Path, help="Path to store ini file")
parser.add_argument("--dest", required=True, type=Path, help="Search plugins directory")


args = parser.parse_args()

if not args.ini.exists():
    ini_str = pkg_resources.resource_string(__name__, "rutracker.ini")
    print("Creating ini file in", args.ini)
    args.ini.write_bytes(ini_str)
else:
    print("Config already exists, skipping.")

png = pkg_resources.resource_string(__name__, "rutracker.png")
plugin_raw = pkg_resources.resource_string(__name__, "rutracker.py.txt").decode()
plugin = string.Template(plugin_raw)

import_path = Path(__file__).parent.parent
print("Using import path:", import_path)

plugin = plugin.substitute(ini=args.ini.absolute(), import_path=import_path)

print("Writing plugin link to the", args.dest)
args.dest.joinpath("rutracker.png").write_bytes(png)
args.dest.joinpath("rutracker.py").write_text(plugin)
print("Plugin installed succesfully.")
