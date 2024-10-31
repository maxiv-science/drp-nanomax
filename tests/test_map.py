import logging
import pickle
import threading
import time
from glob import glob

import h5pyd
from dranspose.replay import replay


def test_map(tmp_path):
    stop_event = threading.Event()
    done_event = threading.Event()

    bin_file = tmp_path / "binparams.pkl"

    with open(bin_file, "wb") as f:
        with open(
            "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg", "rb"
        ) as cf:
            pickle.dump(
                [{"name": "mca_config", "data": cf.read()}],
                f,
            )

    thread = threading.Thread(
        target=replay,
        args=(
            "src.worker:FluorescenceWorker",
            "src.reducer:FluorescenceReducer",
            None,
            "src.xrf_source:XRFSource",
            bin_file,
        ),
        kwargs={"port": 5010, "stop_event": stop_event, "done_event": done_event},
    )
    thread.start()

    # do live queries

    done_event.wait()

    time.sleep(1)  # let the last timer run

    slicelen = 10

    f = h5pyd.File("http://localhost:5010/", "r")
    logging.info("file %s", list(f.keys()))
    logging.info("map %s", f["map"])
    # logging.info("map x %s", f["map/x"])
    # logging.info("map y %s", f["map/y"])
    # logging.info("map v %s", f["map/values"])
    # logging.info("map v %s", f["map/x"][:])
    assert list(f["map/massfractions/Fe K/values"].shape) == [slicelen]
    assert list(f["map/massfractions/Ar K/x"].shape) == [slicelen]
    assert list(f["map/massfractions/Ga K/y"].shape) == [slicelen]

    stop_event.set()

    thread.join()
