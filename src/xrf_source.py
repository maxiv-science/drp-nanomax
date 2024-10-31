import itertools
import logging
import os.path
import zipfile

import numpy as np
from dranspose.event import InternalWorkerMessage, StreamData
from dranspose.data.xspress3 import XspressStart, XspressImage, XspressEnd
from dranspose.data.contrast import ContrastStarted, ContrastRunning, ContrastFinished

import h5py


class XRFSource:
    def __init__(self):
        if not os.path.exists("data/scan_000008_xspress3.hdf5"):
            with zipfile.ZipFile("data/smallspec.zip") as zf:
                zf.extract("scan_000008_xspress3.hdf5", path="data")

        self.fd = h5py.File("data/000008.h5")

    def get_source_generators(self):
        return [self.xspress_source(), self.contrast_source()]

    def xspress_source(self):
        start = XspressStart(filename="")
        yield InternalWorkerMessage(
            event_number=0,
            streams={"xspress3": start.to_stream_data()},
        )

        frameno = 0

        for image in self.fd["/entry/measurement/xspress3/data"]:
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
            self.fd["/entry/measurement/pseudo/x"],
            self.fd["/entry/measurement/pseudo/y"],
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
