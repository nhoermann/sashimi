from sashimi.hardware.cameras.mock import MockCamera
from sashimi.hardware.cameras.hamamatsu import HamamatsuCamera
from sashimi.hardware.cameras.kinetix import KinetixCamera

# Update this dictionary and add the import above when adding a new camera
camera_class_dict = dict(
    hamamatsu=HamamatsuCamera,
    kinetix=KinetixCamera,
    mock=MockCamera,
)
