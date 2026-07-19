import pytest
import tempfile
from pathlib import Path
import shutil
from sashimi import config
from click.testing import CliRunner


@pytest.fixture
def conf_path():
    temp_dir = Path(tempfile.mkdtemp())
    conf_path = temp_dir / config.CONFIG_FILENAME
    config.write_default_config(conf_path)

    yield conf_path

    shutil.rmtree(temp_dir)


def test_config_creation(conf_path):
    conf = config.read_config(file_path=conf_path)
    assert conf == config.TEMPLATE_CONF_DICT


def test_write_config_val(conf_path):
    val = 6
    config.write_config_value(["z_board", "read", "min_val"], val, file_path=conf_path)
    conf = config.read_config(file_path=conf_path)
    assert conf["z_board"]["read"]["min_val"] == val


def test_config_cli_show(conf_path):
    runner = CliRunner()
    result = runner.invoke(config.cli_modify_config, ["show", "-p", str(conf_path)])
    assert result.exit_code == 0
    assert result.output == config._print_config(file_path=conf_path) + "\n"


def test_config_cli_edit(conf_path):
    runner = CliRunner()
    runner.invoke(
        config.cli_modify_config,
        ["edit", "-n", "z_board.read.min_val", "-v", "7", "-p", str(conf_path)],
    )
    conf = config.read_config(conf_path)
    assert conf["z_board"]["read"]["min_val"] == 7


def test_write_config_val_list_index(conf_path):
    """light_sources is a list of unit dicts; dict_path entries addressing a
    list must accept an integer index (as in "light_sources.0.port")."""
    config.write_config_value(
        ["light_sources", "0", "port"], "COM7", file_path=conf_path
    )
    conf = config.read_config(file_path=conf_path)
    assert conf["light_sources"][0]["port"] == "COM7"


def test_config_cli_edit_list_index(conf_path):
    runner = CliRunner()
    runner.invoke(
        config.cli_modify_config,
        ["edit", "-n", "light_sources.0.port", "-v", "COM7", "-p", str(conf_path)],
    )
    conf = config.read_config(conf_path)
    assert conf["light_sources"][0]["port"] == "COM7"


def test_migrate_old_light_source_config(conf_path):
    """Configs written by older sashimi versions have a single `light_source`
    dict rather than a `light_sources` list; reading them should upgrade the
    schema in place rather than crash."""
    old_style_conf = dict(config.TEMPLATE_CONF_DICT)
    del old_style_conf["light_sources"]
    old_style_conf["light_source"] = {
        "name": "cobolt",
        "port": "COM9",
        "intensity_units": "mW",
    }
    config.write_default_config(file_path=conf_path, template=old_style_conf)

    conf = config.read_config(file_path=conf_path)
    assert "light_source" not in conf
    assert conf["light_sources"] == [
        {"name": "cobolt", "port": "COM9", "intensity_units": "mW"}
    ]

    # Migration is persisted, not just applied in-memory:
    reloaded = config.read_config(file_path=conf_path)
    assert reloaded["light_sources"] == conf["light_sources"]


def test_migrate_missing_voltage_limits(conf_path):
    """Configs written before GalvoAxis existed have no `voltage_limits`
    sub-key on z_board/xy_board; reading them should default it from that
    board's existing hardware write range rather than crash."""
    import copy

    old_style_conf = copy.deepcopy(config.TEMPLATE_CONF_DICT)
    del old_style_conf["z_board"]["voltage_limits"]
    del old_style_conf["xy_board"]["voltage_limits"]
    config.write_default_config(file_path=conf_path, template=old_style_conf)

    conf = config.read_config(file_path=conf_path)
    assert conf["z_board"]["voltage_limits"]["piezo"] == {
        "min_val": conf["z_board"]["write"]["min_val"],
        "max_val": conf["z_board"]["write"]["max_val"],
    }
    assert conf["xy_board"]["voltage_limits"]["lateral"] == {
        "min_val": conf["xy_board"]["write"]["min_val"],
        "max_val": conf["xy_board"]["write"]["max_val"],
    }

    # Migration is persisted, not just applied in-memory:
    reloaded = config.read_config(file_path=conf_path)
    assert reloaded["z_board"]["voltage_limits"] == conf["z_board"]["voltage_limits"]


def test_migrate_missing_opto_board(conf_path):
    """Configs written before the optogenetics subsystem existed have no
    `opto_board` key at all; reading them should default it to the mock
    driver rather than crash."""
    import copy

    old_style_conf = copy.deepcopy(config.TEMPLATE_CONF_DICT)
    del old_style_conf["opto_board"]
    config.write_default_config(file_path=conf_path, template=old_style_conf)

    conf = config.read_config(file_path=conf_path)
    assert conf["opto_board"] == config.TEMPLATE_CONF_DICT["opto_board"]

    # Migration is persisted, not just applied in-memory:
    reloaded = config.read_config(file_path=conf_path)
    assert reloaded["opto_board"] == conf["opto_board"]
