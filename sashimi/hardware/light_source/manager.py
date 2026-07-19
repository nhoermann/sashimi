from sashimi.hardware.light_source import light_source_class_dict


class LightSourceManager:
    """Owns all configured laser units. Each unit may expose multiple
    independently-controllable channels (e.g. a Toptica CLE/MLE combiner) or
    just itself (e.g. Cobolt) - see AbstractLightSource.channels. This class
    exposes the flattened list of channels that the rest of sashimi
    (state.py, the GUI) actually controls, so callers don't need to know
    which channels belong to which physical unit.
    """

    def __init__(self, light_source_configs):
        self.units = [
            light_source_class_dict[cfg["name"]](
                port=cfg["port"], intensity_units=cfg.get("intensity_units")
            )
            for cfg in light_source_configs
        ]

    @property
    def channels(self):
        flattened = []
        for unit in self.units:
            flattened.extend(unit.channels)
        return flattened

    def get_channel(self, label):
        for channel in self.channels:
            if channel.label == label:
                return channel
        raise KeyError(f"No light source channel labeled {label!r}")

    def close(self):
        for unit in self.units:
            unit.close()
