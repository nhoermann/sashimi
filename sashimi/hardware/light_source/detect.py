"""On-demand auto-detection of laser units on candidate serial/VISA ports.

Not run automatically at boot (see sashimi/state.py) - probing every port on
every startup is slow and can disturb hardware that's already mid-operation.
Invoke this from a GUI action or the CLI instead.
"""

from sashimi.hardware.light_source import light_source_class_dict


def list_candidate_ports():
    """Return the serial/VISA resource names currently visible on this
    machine, using pyvisa's own resource listing. Returns an empty list if
    pyvisa isn't installed or no resources are found.
    """
    try:
        import pyvisa

        return list(pyvisa.ResourceManager().list_resources())
    except Exception:
        return []


def probe_light_sources(candidate_ports=None):
    """Try each registered light-source driver's `probe()` classmethod
    against each candidate port.

    Parameters
    ----------
    candidate_ports : list of str, optional
        Ports to probe. Defaults to `list_candidate_ports()`.

    Returns
    -------
    list of dict
        One entry per detected unit: {"name": <light_source_class_dict key>,
        "port": <port>, **<extra info from that driver's probe()>}.
    """
    if candidate_ports is None:
        candidate_ports = list_candidate_ports()

    matches = []
    for port in candidate_ports:
        for name, cls in light_source_class_dict.items():
            if name == "mock":
                continue
            result = cls.probe(port)
            if result is not None:
                matches.append(dict(name=name, port=port, **result))
                break  # first matching driver claims this port
    return matches
