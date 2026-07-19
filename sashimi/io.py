"""Thin HDF5 save helper, replacing the ``flammkuchen`` dependency.

sashimi's actual usage of flammkuchen was narrow - a flat dict holding a
single ndarray, with optional blosc compression - so rather than depend on
flammkuchen's general-purpose (sparse matrices, pickling fallback, arbitrary
nesting) serializer, this wraps ``tables`` (PyTables, the package flammkuchen
itself sits on top of) directly for that one shape. Mirrors stytra's own
``stytra/io.py``, which replaced flammkuchen the same way.

Files written here remain readable by flammkuchen's ``load``/``aslice`` for a
plain numeric array: for a non-string, non-object dtype, flammkuchen's
``_save_ndarray`` reduces to the same ``create_carray``/``create_array`` call
made below.
"""

import numpy as np
import tables


def save_h5_dict(path, data, compression=None):
    """Save a flat dict of ndarray-like values to an HDF5 file."""
    filters = (
        tables.Filters(complib=compression, complevel=5, shuffle=True)
        if compression
        else None
    )
    with tables.open_file(str(path), mode="w") as f:
        for key, value in data.items():
            value = np.asarray(value)
            if filters is not None:
                f.create_carray(f.root, key, obj=value, filters=filters)
            else:
                f.create_array(f.root, key, obj=value)
