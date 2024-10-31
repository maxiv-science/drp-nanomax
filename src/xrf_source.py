import datetime
import itertools
import logging

import numpy as np
from dranspose.event import InternalWorkerMessage, StreamData
from dranspose.data.xspress3 import XspressStart, XspressImage, XspressEnd
from dranspose.data.contrast import ContrastStarted, ContrastRunning, ContrastFinished
from dranspose.data.positioncap import (
    PositionCapStart,
    PositionCapField,
    PositionCapValues,
    PositionCapEnd,
)

import h5py


class XRFSource:
    def __init__(self):
        self.fd = h5py.File("data/000008.h5")
        self.slice = slice(10)

    def get_source_generators(self):
        return [self.xspress_source(), self.contrast_source(), self.pcap_source()]

    def xspress_source(self):
        start = XspressStart(filename="")
        yield InternalWorkerMessage(
            event_number=0,
            streams={"xspress3": start.to_stream_data()},
        )

        frameno = 0

        for image in self.fd["/entry/measurement/xspress3/data"][self.slice]:
            img = XspressImage(
                frame=frameno,
                shape=image.shape,
                compression="none",
                type=str(image.dtype),
                data=image,
                meta={},
            )
            yield InternalWorkerMessage(
                event_number=frameno + 1,
                streams={"xspress3": img.to_stream_data()},
            )
            frameno += 1

        end = XspressEnd()
        yield InternalWorkerMessage(
            event_number=frameno,
            streams={"xspress3": end.to_stream_data()},
        )

    def contrast_source(self):
        start = ContrastStarted(path="./", scannr=0, description="test")
        yield InternalWorkerMessage(
            event_number=0,
            streams={"contrast": start.to_stream_data()},
        )

        frameno = 0

        for x, y in zip(
            self.fd["/entry/measurement/pseudo/x"][self.slice],
            self.fd["/entry/measurement/pseudo/y"][self.slice],
        ):
            img = ContrastRunning(
                dt=0.1, pseudo={"x": np.array([x]), "y": np.array([y])}
            )
            yield InternalWorkerMessage(
                event_number=frameno + 1,
                streams={"contrast": img.to_stream_data()},
            )
            frameno += 1

        end = ContrastFinished(path="./", scannr=0, description="test")
        yield InternalWorkerMessage(
            event_number=frameno,
            streams={"contrast": end.to_stream_data()},
        )

    def pcap_source(self):
        fields = [
            PositionCapField(name="INENC2.VAL.Mean", type="double"),
            PositionCapField(name="INENC3.VAL.Mean", type="double"),
            PositionCapField(name="PCAP.TS_TRIG.Value", type="double"),
        ]
        start = PositionCapStart(arm_time=datetime.datetime.utcnow())
        yield InternalWorkerMessage(
            event_number=0,
            streams={"pcap": start.to_stream_data(fields)},
        )

        frameno = 0
        for data in zip(
            self.fd["/entry/measurement/panda0/INENC2.VAL_Mean"][self.slice],
            self.fd["/entry/measurement/panda0/INENC3.VAL_Mean"][self.slice],
            self.fd["/entry/measurement/panda0/PCAP.TS_TRIG_Value"][self.slice],
        ):
            for f, d in zip(fields, data):
                f.value = d

            logging.warning("fields are %s", fields)
            val = PositionCapValues(fields={f.name: f for f in fields})
            yield InternalWorkerMessage(
                event_number=frameno + 1,
                streams={"pcap": val.to_stream_data()},
            )
            frameno += 1

        end = PositionCapEnd()
        yield InternalWorkerMessage(
            event_number=frameno,
            streams={"pcap": end.to_stream_data()},
        )
