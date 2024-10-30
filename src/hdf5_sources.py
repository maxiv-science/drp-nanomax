import itertools

import numpy as np
from dranspose.event import InternalWorkerMessage, StreamData
from dranspose.data.stream1 import Stream1Start, Stream1Data, Stream1End
import h5py
from bitshuffle import decompress_lz4, compress_lz4


class PilatusSource:
    def __init__(self):
        # self.fd = h5py.File("../000008.h5")
        pass

    def get_source_generators(self):
        return [self.pilatus_source()]

    def pilatus_source(self):
        msg_number = itertools.count(0)

        stins_start = Stream1Start(
            htype="header", filename="", msg_number=next(msg_number)
        ).model_dump_json()
        start = InternalWorkerMessage(
            event_number=0,
            streams={"pilatus": StreamData(typ="STINS", frames=[stins_start])},
        )
        yield start

        frameno = 0
        images = np.zeros((10, 1043, 981), dtype=np.int32)

        for image in images:  # self.fd["/entry/measurement/pilatus/frames"]:
            stins = Stream1Data(
                htype="image",
                msg_number=next(msg_number),
                frame=frameno,
                shape=image.shape,
                compression="bslz4",
                type=str(image.dtype),
            ).model_dump_json()
            dat = compress_lz4(image)
            img = InternalWorkerMessage(
                event_number=frameno + 1,
                streams={
                    "pilatus": StreamData(typ="STINS", frames=[stins, dat.tobytes()])
                },
            )
            yield img
            frameno += 1

        stins_end = Stream1End(
            htype="series_end", msg_number=next(msg_number)
        ).model_dump_json()
        end = InternalWorkerMessage(
            event_number=frameno,
            streams={"pilatus": StreamData(typ="STINS", frames=[stins_end])},
        )
        yield end
