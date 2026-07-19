from sashimi.state import (
    StytraSettings,
    StytraCameraRoleSettings,
    convert_stytra_config,
)
from sashimi.hardware.external_trigger.stytra import StytraComm
from sashimi.hardware.external_trigger.mock import MockComm


def test_convert_stytra_config_includes_only_enabled_roles():
    settings = StytraSettings()
    settings.protocol_name = "gratings_heart_tail_tracking"

    tail = StytraCameraRoleSettings(role_name="tail_cam")
    tail.enabled = True
    tail.tracking_method = "tail"

    heart = StytraCameraRoleSettings(role_name="heart_cam")
    heart.enabled = True
    heart.tracking_method = "heart_rate"

    fin = StytraCameraRoleSettings(role_name="fin_cam")
    fin.enabled = False  # disabled - should be excluded
    fin.tracking_method = "pectoral_fin"

    config = convert_stytra_config(settings, [tail, heart, fin])

    assert config["protocol_name"] == "gratings_heart_tail_tracking"
    cameras = config["stytra_config"]["cameras"]
    assert cameras == [
        dict(role="tail_cam", tracking=dict(method="tail")),
        dict(role="heart_cam", tracking=dict(method="heart_rate")),
    ]


def test_convert_stytra_config_excludes_method_none():
    settings = StytraSettings()
    role = StytraCameraRoleSettings(role_name="fin_cam")
    role.enabled = True
    role.tracking_method = "none"

    config = convert_stytra_config(settings, [role])
    assert config["stytra_config"]["cameras"] == []


def test_convert_stytra_config_no_roles_enabled():
    settings = StytraSettings()
    roles = [StytraCameraRoleSettings(role_name=r) for r in ["tail_cam", "heart_cam"]]
    config = convert_stytra_config(settings, roles)
    assert config["stytra_config"]["cameras"] == []


def test_stytra_comm_normalize_reply_accepts_bare_number():
    # Current stytra ZmqTrigger reply shape (a plain duration number):
    normalized = StytraComm._normalize_reply(12.5)
    assert normalized == {"duration": 12.5, "tracking_data_path": None}


def test_stytra_comm_normalize_reply_accepts_dict():
    # Updated stytra ZmqTrigger reply shape (see stytra/triggering/__init__.py):
    normalized = StytraComm._normalize_reply(
        {"duration": 8.0, "tracking_data_path": "/tmp/exp/240101_f0/120000_"}
    )
    assert normalized == {
        "duration": 8.0,
        "tracking_data_path": "/tmp/exp/240101_f0/120000_",
    }


def test_stytra_comm_normalize_reply_accepts_dict_missing_keys():
    normalized = StytraComm._normalize_reply({})
    assert normalized == {"duration": None, "tracking_data_path": None}


def test_mock_comm_returns_none():
    assert MockComm().trigger_and_receive_duration({"lightsheet": {}}) is None
