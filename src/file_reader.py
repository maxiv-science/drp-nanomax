import json

import h5py
import zmq
from h5py import Dataset

from dranspose.event import StreamData, EventData

from worker import FluorescenceWorker
from reducer import FluorescenceReducer

def build_frame(dsets: list[Dataset]):
    frame = {}
    i = 0
    while True:
        for dset in dsets:
            name = dset.name[len(dset.parent.name)+1:]
            try:
                data = dset[i]
            except IndexError:
                return
            frame[name] = data

        yield frame
        i+=1

with h5py.File("../000008.h5") as f:
    #print(f["entry/measurement"].keys())
    #print(f["entry/measurement/xspress3/data"][0].shape)
    pseudo = f["entry/measurement/pseudo"]

    positiongen = build_frame([f["entry/measurement/pseudo/x"],
                         f["entry/measurement/pseudo/y"],
                         f["entry/measurement/pseudo/z"]])
    energygen = build_frame([f["entry/measurement/xspress3/data"]])


    worker = FluorescenceWorker()
    reducer = FluorescenceReducer()

    i = 0
    while True:
        try:
            pos = next(positiongen)
            energy = next(energygen)
        except StopIteration:
            break

        ehdr = {"dtype":str(energy["data"].dtype), "shape": energy["data"].shape}

        posframe = zmq.Frame(json.dumps(pos).encode("utf8"))

        energyframes = [zmq.Frame(json.dumps(ehdr).encode("utf8")),
                        zmq.Frame(energy["data"].data)]

        ms = StreamData(typ="motors", frames=[posframe])
        xs = StreamData(typ="xspress3", frames=energyframes)
        ev = EventData(event_number=i, streams={"position":ms, "energy":xs})

        data = worker.process_event(ev)

        reducer.process_data(data)

        i+=1

