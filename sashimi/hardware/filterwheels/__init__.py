from sashimi.hardware.filterwheels.mock import MockFilterWheel
from sashimi.hardware.filterwheels.thorlabs import FW102C_FilterWheel

# Update this dictionary and add the import above when adding a new laser
filterwheel_class_dict = dict(
    mock=MockFilterWheel,
    thorlabsFW102C=FW102C_FilterWheel,
)