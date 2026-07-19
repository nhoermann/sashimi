from typing import Optional
from abc import ABC, abstractmethod


class AbstractComm(ABC):
    def __init__(self, address):
        self.address = address

    @abstractmethod
    def trigger_and_receive_duration(self, config) -> Optional[dict]:
        """Send `config` to the external program and wait for its reply.

        Returns a dict with at least a "duration" key (seconds, or None if
        the reply didn't include one) and a "tracking_data_path" key
        (str/None - where the external program saved its own experiment
        data for this run, if it reports one), or None if there was no
        reply at all (e.g. timeout).
        """
        return None
