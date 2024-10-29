import json
import pickle
import random
import uuid

import h5py
import numpy as np
import zmq
from PyMca5.PyMcaIO import ConfigDict
from h5py import Dataset

from dranspose.event import StreamData, EventData, ResultData
from dranspose.data.contrast import ContrastStarted
from dranspose.protocol import WorkParameter

from worker import FluorescenceWorker
from reducer import FluorescenceReducer


def build_frame(dsets: list[Dataset]):
    frame = {}
    i = 0
    while True:
        for dset in dsets:
            name = dset.name[len(dset.parent.name) + 1 :]
            try:
                data = dset[i]
            except IndexError:
                return
            frame[name] = data

        yield frame
        i += 1


# cfg = ConfigDict.ConfigDict()
with open("../fit_config_scan_000027_0.1_second_some_elements_removed.cfg", "rb") as f:
    content = f.read()
# ffile =
# cfg.read(ffile)


parameters = {"mca_config_file": WorkParameter(name="mca_config_file", data=content)}

with h5py.File("../000008.h5") as f:
    # print(f["entry/measurement"].keys())
    # print(f["entry/measurement/xspress3/data"][0].shape)
    pseudo = f["entry/measurement/pseudo"]

    positiongen = build_frame(
        [
            f["entry/measurement/pseudo/x"],
            f["entry/measurement/pseudo/y"],
            f["entry/measurement/pseudo/z"],
        ]
    )
    energygen = build_frame([f["entry/measurement/xspress3/data"]])

    workers = [FluorescenceWorker(parameters=parameters) for _ in range(2)]
    reducer = FluorescenceReducer(parameters=parameters)

    i = 0

    contrast_start = pickle.dumps(
        ContrastStarted(path="", scannr=4, description="stepscan")
    )
    contrast = StreamData(typ="contrast", frames=[contrast_start])
    xspress_start = json.dumps({"htype": "header", "filename": ""})
    xspress = StreamData(typ="xspress", frames=[xspress_start])
    ev = EventData(event_number=i, streams={"contrast": contrast, "x3mini": xspress})

    for wi, worker in enumerate(workers):
        data = worker.process_event(ev, parameters=parameters)
        rd = ResultData(
            event_number=i,
            worker=f"worker{wi}",
            payload=data,
            parameters_hash="asd",
        )

        reducer.process_result(rd, parameters=parameters)

    i += 1
    while True:
        try:
            pos = next(positiongen)
            energy = next(energygen)
        except StopIteration:
            break

        ehdr = {
            "htype": "image",
            "type": str(energy["data"].dtype),
            "shape": energy["data"].shape,
            "frame": i - 1,
        }

        energyframes = [
            zmq.Frame(json.dumps(ehdr).encode("utf8")),
            zmq.Frame(energy["data"].data),
            zmq.Frame(pickle.dumps(["bla"])),
        ]

        # posframe = zmq.Frame(json.dumps(pos).encode("utf8"))
        ctr = {
            "pseudo": {k: np.array([v]) for k, v in pos.items()},
            "status": "running",
            "dt": 0.4,
        }

        ms = StreamData(typ="contrast", frames=[zmq.Frame(pickle.dumps(ctr))])
        xs = StreamData(typ="xspress", frames=energyframes)
        ev = EventData(event_number=i, streams={"contrast": ms, "x3mini": xs})

        wi = random.randint(0, len(workers) - 1)
        data = workers[wi].process_event(ev, parameters=parameters)

        rd = ResultData(
            event_number=i,
            worker=f"worker{wi}",
            payload=data,
            parameters_hash="asd",
        )

        reducer.process_result(rd, parameters=parameters)

        i += 1
        if i == 3:
            # break
            pass

    contrast_end = pickle.dumps({"status": "finished"})
    contrast = StreamData(typ="contrast", frames=[contrast_end])
    xspress_end = json.dumps({"htype": "series_end"})
    xspress = StreamData(typ="xspress", frames=[xspress_end])
    ev = EventData(event_number=i, streams={"contrast": contrast, "x3mini": xspress})

    for wi, worker in enumerate(reversed(workers)):
        data = worker.process_event(ev, parameters=parameters)

        rd = ResultData(
            event_number=i,
            worker=b"development",
            payload=data,
            parameters_hash="asd",
        )

        reducer.process_result(rd, parameters=parameters)

    [worker.finish(parameters=parameters) for worker in workers]
    reducer.finish(parameters=parameters)
