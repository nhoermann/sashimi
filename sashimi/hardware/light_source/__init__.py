from sashimi.hardware.light_source.mock import MockLaser
from sashimi.hardware.light_source.cobolt import CoboltLaser
from sashimi.hardware.light_source.toptica import TopticaCLE, TopticaMLE

# Update this dictionary and add the import above when adding a new laser
light_source_class_dict = dict(
    cobolt=CoboltLaser,
    toptica_cle=TopticaCLE,
    toptica_mle=TopticaMLE,
    mock=MockLaser,
)
