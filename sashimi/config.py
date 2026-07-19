import copy
from pathlib import Path
import click
import toml

CONFIG_FILENAME = "hardware_config.toml"
CONFIG_DIR_PATH = Path.home() / ".sashimi"
CONFIG_DIR_PATH.mkdir(exist_ok=True)
PRESETS_DIR_PATH = Path.home() / "presets"
PRESETS_DIR_PATH.mkdir(exist_ok=True)
LOGS_DIR_PATH = Path.home() / "logs"
LOGS_DIR_PATH.mkdir(exist_ok=True)
SCOPE_INSTRUCTIONS_PATH = Path()

CONFIG_PATH = CONFIG_DIR_PATH / CONFIG_FILENAME

# 2 level dictionary for sections and values:
# TODO this will obviously have to change to fit scanning declarations
TEMPLATE_CONF_DICT = {
    "scanning": "mock",
    "scopeless": True,
    "sample_rate": 40000,
    "voxel_size": {
        "x": 0.3,
        "y": 0.3,
    },
    "default_paths": {
        "data": str(Path.home()),
        "presets": str(PRESETS_DIR_PATH),
        "log": str(LOGS_DIR_PATH),
        "scope_instructions": str(SCOPE_INSTRUCTIONS_PATH),
    },
    "z_board": {
        "read": {
            "channel": "Dev1/ai0:0",
            "min_val": 0,
            "max_val": 10,
        },
        "write": {
            "channel": "Dev1/ao0:3",
            "min_val": -5,
            "max_val": 10,
        },
        "sync": {"channel": "/Dev1/ao/StartTrigger"},
        # Software safety limits (see sashimi/hardware/scanning/galvo.py's
        # GalvoAxis) checked before each value is written to hardware, on top
        # of the AO task's own hardware range above ("write.min_val"/"max_val").
        # Defaults match that hardware range so nothing previously allowed is
        # newly rejected - narrow these to your actual safe per-channel travel.
        "voltage_limits": {
            "piezo": {"min_val": -5, "max_val": 10},
            "lateral": {"min_val": -5, "max_val": 10},
            "frontal": {"min_val": -5, "max_val": 10},
            "camera_trigger": {"min_val": -5, "max_val": 10},
        },
    },
    "piezo": {
        "scale": 1 / 40,
    },
    "email": {"user": "foo", "password": "foo"},
    "xy_board": {
        "write": {
            "channel": "Dev2/ao0:1",
            "min_val": -5,
            "max_val": 10,
        },
        "voltage_limits": {
            "lateral": {"min_val": -5, "max_val": 10},
            "frontal": {"min_val": -5, "max_val": 10},
        },
    },
    # Optogenetics stimulation galvo pair + laser gate, on a dedicated NI card
    # separate from z_board/xy_board (see sashimi/hardware/optogenetics/).
    # "name" selects the driver from opto_conf_dict (sashimi/processes/optogenetics.py):
    # "ni" or "mock".
    "opto_board": {
        "name": "mock",
        "write": {
            "x_channel": "Dev3/ao0",
            "y_channel": "Dev3/ao1",
            "gate_channel": "Dev3/port0/line0",
        },
        "voltage_limits": {
            "x": {"min_val": -5, "max_val": 5},
            "y": {"min_val": -5, "max_val": 5},
        },
    },
    # "name" selects the driver from camera_class_dict (sashimi/hardware/cameras/__init__.py):
    # "hamamatsu" (generic DCAM API, works with any Orca model), "kinetix" (Teledyne
    # Photometrics, requires pyvcam + the PVCAM SDK), or "mock".
    "camera": {
        "id": 0,
        "name": "mock",
        "max_sensor_resolution": [2048, 2048],
        "default_exposure": 60,
        "default_binning": 1,
    },
    # A list of laser units (not a single laser): most units expose exactly one
    # controllable channel (e.g. Cobolt), but combiner units such as Toptica
    # CLE/MLE expose several channels over one connection - see
    # sashimi/hardware/light_source/manager.py. "name" selects the driver from
    # light_source_class_dict: "cobolt", "toptica_cle", "toptica_mle", or "mock".
    "light_sources": [{"name": "mock", "port": "COM4", "intensity_units": "mock"}],
    "external_communication": {"name": "stytra", "address": "tcp://O1-589:5555"},
    "notifier": "none",
    "notifier_options": {},
    "array_ram_MB": 450,
}


def write_default_config(file_path=CONFIG_PATH, template=TEMPLATE_CONF_DICT):
    """Write configuration file at first repo usage. In this way,
    we don't need to keep a confusing template config file in the repo.

    Parameters
    ----------
    file_path : Path object
        Path of the config file (optional).
    template : dict
        Template of the config file to be written (optional).

    """

    with open(file_path, "w") as f:
        toml.dump(template, f)


def _migrate_config(conf, file_path):
    """Upgrade a config dict written by an older sashimi version in place,
    persisting the change so this only runs once per config file.

    Currently handles:
    - single `light_source` dict -> `light_sources` list (support for
      multiple simultaneous laser units, e.g. Toptica CLE/MLE).
    - missing `z_board`/`xy_board` `voltage_limits` (per-channel software
      safety limits, see sashimi/hardware/scanning/galvo.py's GalvoAxis) -
      defaulted to that board's existing hardware write range, so nothing
      previously allowed is newly rejected.
    - missing `opto_board` (added for the optogenetics stimulation
      subsystem) - defaulted to the mock driver, so existing configs don't
      need real optogenetics hardware to keep working.
    """
    migrated = False

    if "light_source" in conf and "light_sources" not in conf:
        conf["light_sources"] = [conf.pop("light_source")]
        migrated = True

    board_channels = {
        "z_board": ["piezo", "lateral", "frontal", "camera_trigger"],
        "xy_board": ["lateral", "frontal"],
    }
    for board, channel_names in board_channels.items():
        if board in conf and "voltage_limits" not in conf[board]:
            default_limits = {
                "min_val": conf[board]["write"]["min_val"],
                "max_val": conf[board]["write"]["max_val"],
            }
            conf[board]["voltage_limits"] = {
                name: dict(default_limits) for name in channel_names
            }
            migrated = True

    if "opto_board" not in conf:
        conf["opto_board"] = copy.deepcopy(TEMPLATE_CONF_DICT["opto_board"])
        migrated = True

    if migrated:
        with open(file_path, "w") as f:
            toml.dump(conf, f)

    return conf


def read_config(file_path=CONFIG_PATH):
    """Read Sashimi config.

    Parameters
    ----------
    file_path : Path object
        Path of the config file (optional).

    Returns
    -------
    ConfigParser object
        sashimi configuration
    """

    # If no config file exists yet, write the default one:
    if not file_path.exists():
        write_default_config()

    return _migrate_config(toml.load(file_path), file_path)


def _get_nested(d, path):
    """Like lightparam's get_nested, but also accepts integer path segments
    (as strings, e.g. "0") to index into lists - needed since
    hardware_config.toml has list-valued sections (e.g. `light_sources`).
    """
    current = d
    for key in path:
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


def _set_nested(d, path, val):
    parent = _get_nested(d, path[:-1])
    last_key = path[-1]
    if isinstance(parent, list):
        parent[int(last_key)] = val
    else:
        parent[last_key] = val


def write_config_value(dict_path, val, file_path=CONFIG_PATH):
    """Write a new value in the config file. To make things simple, ignore
    sections and look directly for matching parameters names.

    Parameters
    ----------
    dict_path : str or list of strings
        Full path of the section to configure
        (e.g., ["piezo", "position_read", "min_val"], or ["light_sources", "0", "port"])
    val :
        New value.
    file_path : Path object
        Path of the config file (optional).

    """
    # Ensure path to entry is always a string:
    if type(dict_path) is str:
        dict_path = [dict_path]

    # Read and set:
    conf = read_config(file_path=file_path)
    _set_nested(conf, dict_path, val)

    # Write:
    with open(file_path, "w") as f:
        toml.dump(conf, f)


@click.command()
@click.argument("command")
@click.option("-n", "--name", help="Path (section/name) of parameter to be changed")
@click.option("-v", "--val", help="Value of parameter to be changed")
@click.option(
    "-p",
    "--file_path",
    default=CONFIG_PATH,
    help="Path to the config file (optional)",
)
def cli_modify_config(command, name=None, val=None, file_path=CONFIG_PATH):
    file_path = Path(file_path)
    if command == "edit":
        cli_edit_config(name, val, file_path)

    elif command == "show":
        click.echo(_print_config(file_path=file_path))


def cli_edit_config(name=None, val=None, file_path=CONFIG_PATH):
    conf = read_config(file_path=file_path)

    # Cast the type of the previous variable
    # (to avoid overwriting values with strings)
    dict_path = name.split(".")
    old_val = _get_nested(conf, dict_path)
    val = type(old_val)(val)  # Convert to keep the same type

    write_config_value(dict_path, val, file_path)


def _print_config(file_path=CONFIG_PATH):
    """Return configuration string for printing."""
    config = read_config(file_path=file_path)
    return toml.dumps(config)
