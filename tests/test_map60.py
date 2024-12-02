import logging
import cbor2
import threading
import time
from glob import glob

import h5pyd
import pytest
from dranspose.replay import replay


@pytest.mark.skipif(
    "not config.getoption('long')",
    reason="explicitly enable --long running tests",
)
def test_map(tmp_path):
    stop_event = threading.Event()
    done_event = threading.Event()

    bin_file = tmp_path / "binparams.cbor"

    with open(bin_file, "wb") as f:
        with open("data/0001_setup_000060.cfg", "rb") as cf:
            cbor2.dump(
                [{"name": "mca_config", "data": cf.read()}],
                f,
            )

    thread = threading.Thread(
        target=replay,
        args=(
            "src.worker:FluorescenceWorker",
            "src.reducer:FluorescenceReducer",
            None,
            "src.xrf_source:XRFSourceFly60",
            bin_file,
        ),
        kwargs={"port": 5010, "stop_event": stop_event, "done_event": done_event},
    )
    thread.start()

    # do live queries

    done_event.wait()

    time.sleep(1000)  # let the last timer run

    stop_event.set()

    thread.join()
