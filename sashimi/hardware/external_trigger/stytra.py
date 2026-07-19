from sashimi.hardware.external_trigger.interface import AbstractComm
import zmq
from typing import Optional


class StytraComm(AbstractComm):
    def __init__(self, address):
        super().__init__(address)
        self.address = address

    def trigger_and_receive_duration(self, config) -> Optional[dict]:
        zmq_context = zmq.Context()
        with zmq_context.socket(zmq.REQ) as zmq_socket:
            zmq_socket.connect(self.address)
            zmq_socket.send_json(config)
            poller = zmq.Poller()
            poller.register(zmq_socket, zmq.POLLIN)
            response = None
            if poller.poll(1000):
                response = self._normalize_reply(zmq_socket.recv_json())

        zmq_context.destroy()
        return response

    @staticmethod
    def _normalize_reply(reply) -> dict:
        """Stytra's reply may be a bare number (older stytra versions, or a
        receiver that only ever sent back a duration) or a dict with
        "duration"/"tracking_data_path" keys (once stytra's zmq receiver
        reports where it saved this run's tracking data) - support both, so
        this doesn't break against an unmodified stytra receiver.
        """
        if isinstance(reply, dict):
            return {
                "duration": reply.get("duration"),
                "tracking_data_path": reply.get("tracking_data_path"),
            }
        return {"duration": reply, "tracking_data_path": None}
