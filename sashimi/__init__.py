__version__ = "0.2.1"

import numpy as _np

# arrayqueues (a direct dependency) and flammkuchen (still used at runtime by
# the external split_dataset reader, see sashimi/io.py) call aliases removed
# in NumPy 2.0; restore them so ArrayQueue.put and split_dataset's flammkuchen
# reads still work until those packages release fixed versions on PyPI.
if not hasattr(_np, "product"):
    _np.product = _np.prod
if not hasattr(_np, "unicode_"):
    _np.unicode_ = _np.str_
if not hasattr(_np, "string_"):
    _np.string_ = _np.bytes_

from sashimi.main import main
from sys import argv

if __name__ == "__main__":
    main(argv[1:])
