import logging
import cbor2
import threading
import time
from glob import glob

import h5pyd
from dranspose.replay import replay


def test_pilatus():
    stop_event = threading.Event()
    done_event = threading.Event()

    thread = threading.Thread(
        target=replay,
        args=(
            "src.worker:FluorescenceWorker",
            "src.reducer:FluorescenceReducer",
            None,
            "src.hdf5_sources:PilatusSource",
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


def test_contrast(tmp_path):
    stop_event = threading.Event()
    done_event = threading.Event()

    bin_file = tmp_path / "binparams.pkl"

    with open(bin_file, "wb") as f:
        with open(
            "data/fit_config_scan_000027_0.1_second_some_elements_removed.cfg", "rb"
        ) as cf:
            cbor2.dump(
                [{"name": "mca_config", "data": cf.read()}],
                f,
            )

    thread = threading.Thread(
        target=replay,
        args=(
            "src.worker:FluorescenceWorker",
            "src.reducer:FluorescenceReducer",
            glob("data/*_ingest.pkls"),
            None,
            bin_file,
        ),
        kwargs={"port": 5010, "stop_event": stop_event, "done_event": done_event},
    )
    thread.start()

    # do live queries

    done_event.wait()

    f = h5pyd.File("http://localhost:5010/", "r")
    logging.info("file %s", list(f.keys()))

    stop_event.set()

    thread.join()
