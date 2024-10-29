import logging
import threading

import h5pyd
from dranspose.replay import replay


def test_replay():
    stop_event = threading.Event()
    done_event = threading.Event()

    thread = threading.Thread(
        target=replay,
        args=(
            "src.worker:FluorescenceWorker",
            "src.reducer:FluorescenceReducer",
            None,
            "src.hdf5_sources:FluorescenceSource",
            "params.json",
        ),
        kwargs={"port": 5010, "stop_event": stop_event, "done_event": done_event},
    )
    thread.start()

    # do live queries

    done_event.wait()

    f = h5pyd.File("http://localhost:5010/", "r")
    logging.info("file %s", list(f.keys()))
    logging.info("azint %s", f["azint/data"])
    assert list(f["azint/data"].shape) == [10, 100]

    stop_event.set()

    thread.join()
