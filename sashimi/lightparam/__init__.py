# Vendored from lightparam (https://github.com/portugueslab/lightparam),
# MIT License, Copyright (c) 2018 Portugues lab, via stytra's own vendored
# copy (https://github.com/portugueslab/stytra) which fixed it for Python 3.12.
__version__ = "0.4.6"
__author__ = "Vilim Stich, Luigi Petrucco"

from sashimi.lightparam.core import (
    Param,
    ParamContainer,
    ParameterTree,
    Parametrized,
    get_nested,
    set_nested,
    visit_dict,
)
