from multiprocessing import Queue
from sashimi.processes.logging import LoggingProcess
from sashimi.utilities import clean_json, get_last_parameters
from sashimi.events import LoggedEvent
from sashimi.config import read_config
from sashimi.hardware.external_trigger import external_comm_class_dict
from queue import Empty
from multiprocessing import Event

conf = read_config()


class ExternalComm(LoggingProcess):
    def __init__(
        self,
        stop_event: LoggedEvent,
        experiment_start_event: LoggedEvent,
        is_saving_event: LoggedEvent,
        is_waiting_event: LoggedEvent,
        duration_queue: Queue,
        address=conf["external_communication"]["address"],
        scanning_trigger=True,
    ):
        super().__init__(name="external_comm")
        self.current_settings_queue = Queue()
        self.current_settings = None
        # Protocol/tracking config for the external program (e.g. stytra's
        # visual-stimuli + tail/heart/fin tracking), sent alongside the
        # lightsheet settings on every trigger - see convert_stytra_config
        # in sashimi/state.py.
        self.stytra_config_queue = Queue()
        self.current_stytra_config = None
        # Where the external program's own reply says it saved this run's
        # data, if it reports one (see AbstractComm.trigger_and_receive_duration).
        self.tracking_data_queue = Queue()
        self.start_comm = experiment_start_event.new_reference(self.logger)
        self.stop_event = stop_event.new_reference(self.logger)
        self.saving_event = is_saving_event.new_reference(self.logger)
        self.is_triggered_event = Event()
        self.duration_queue = duration_queue
        self.address = address
        if conf["scopeless"]:
            self.comm = external_comm_class_dict["mock"]()
        else:
            self.comm = external_comm_class_dict[
                conf["external_communication"]["name"]
            ](self.address)
        self.scanning_trigger = scanning_trigger
        if self.scanning_trigger:
            self.waiting_event = is_waiting_event.new_reference(self.logger)

    def trigger_condition(self):
        if self.scanning_trigger:
            return (
                self.start_comm.is_set()
                and self.saving_event.is_set()
                and self.is_triggered_event.is_set()
                and not self.waiting_event.is_set()
            )

    def run(self):
        self.logger.log_message("started")
        while not self.stop_event.is_set():
            while True:
                try:
                    self.current_settings = self.current_settings_queue.get(
                        timeout=0.00001
                    )
                except Empty:
                    break

            new_stytra_config = get_last_parameters(self.stytra_config_queue)
            if new_stytra_config is not None:
                self.current_stytra_config = new_stytra_config

            if self.trigger_condition():
                current_config = dict(
                    lightsheet=clean_json(self.current_settings),
                    # Tells stytra's ZmqTrigger it's safe to reply with the
                    # newer {"duration", "tracking_data_path"} dict instead
                    # of a bare duration number - see
                    # stytra/triggering/__init__.py's ZmqTrigger.check_trigger.
                    supports_tracking_data_path=True,
                )
                if self.current_stytra_config is not None:
                    current_config["stytra"] = clean_json(self.current_stytra_config)

                response = self.comm.trigger_and_receive_duration(current_config)
                if response is not None:
                    duration = response.get("duration")
                    if duration is not None:
                        self.duration_queue.put(duration)
                    self.tracking_data_queue.put(response.get("tracking_data_path"))

                self.logger.log_message("sent communication")
                self.start_comm.clear()
        self.close_log()
