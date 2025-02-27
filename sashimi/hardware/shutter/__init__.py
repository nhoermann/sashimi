from sashimi.hardware.shutter.mock import MockShutter
#from sashimi.hardware.shutter.ni import NIShutter

# Update this dictionary and add the import above when adding a new laser
shutter_class_dict = dict(
    #ni=NIShutter,
    mock=MockShutter,
)