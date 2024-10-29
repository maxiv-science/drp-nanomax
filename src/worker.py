import json
import logging
import tempfile

from PyMca5.PyMcaIO import ConfigDict
from PyMca5.PyMcaPhysics.xrf.FastXRFLinearFit import FastXRFLinearFit
from dranspose.event import EventData
from dranspose.data.xspress3 import XspressStart
from dranspose.data.contrast import ContrastRunning
from dranspose.data.stream1 import Stream1Data
from dranspose.middlewares import contrast
from dranspose.middlewares import xspress
from dranspose.middlewares import stream1
from dranspose.parameters import StrParameter, BinaryParameter
import numpy as np
import azint
import zmq

from bitshuffle import decompress_lz4

logger = logging.getLogger(__name__)


class FluorescenceWorker:
    @staticmethod
    def describe_parameters():
        params = [
            BinaryParameter(name="mca_config"),
            BinaryParameter(name="poni"),
        ]
        return params

    def __init__(self, parameters=None, *args, **kwargs):
        self.number = 0
        self.fastFit = FastXRFLinearFit()
        if "mca_config_file" in parameters:
            with tempfile.NamedTemporaryFile() as fp:
                fp.write(parameters["mca_config_file"].data)
                self.fastFit.setFitConfigurationFile(fp.name)
        self.ai = None
        if "poni_file" in parameters:
            print("par", parameters["poni_file"])
            with tempfile.NamedTemporaryFile() as fp:
                fp.write(parameters["poni_file"].data)
                fp.flush()
                self.ai = azint.AzimuthalIntegrator(fp.name, 4, 100)

    def process_event(self, event: EventData, parameters=None, **kwargs):
        logger.debug("using parameters %s", parameters)
        ret = {}
        if "pilatus" in event.streams:
            logger.debug("use eiger data for azint")
            if self.ai is not None:
                data = stream1.parse(event.streams["pilatus"])
                if isinstance(data, Stream1Data):
                    if "bslz4" in data.compression:
                        bufframe = event.streams["pilatus"].frames[1]
                        if isinstance(bufframe, zmq.Frame):
                            bufframe = bufframe.bytes
                        img = decompress_lz4(bufframe, data.shape, dtype=data.type)
                        # print("decomp", img, img.shape)
                        I, _ = self.ai.integrate(img)
                        logger.info("got I %s", I.shape)
                        ret["azint"] = I

            # self.ai.integrate()
        if len(ret) > 0:
            return ret

        if {"contrast"} - set(event.streams.keys()) != set():
            logger.error(
                "missing streams for this worker, only present %s", event.streams.keys()
            )
            return
        try:
            con = contrast.parse(event.streams["contrast"])
            if not isinstance(con, ContrastRunning):
                return {"control": con}
        except Exception as e:
            logger.error("failed to parse contrast %s", e.__repr__())
            return

        channel = None
        spec = None
        try:
            if "xspress3" in event.streams:
                spec = xspress.parse(event.streams["xspress3"])
                if isinstance(spec, XspressStart):
                    logger.info("ignore start message")
                    return
                channel = spec.data[3]
        except Exception as e:
            logger.error("failed to parse xspress3 %s", e.__repr__())
            return

        try:
            if "x3mini" in event.streams:
                spec = xspress.parse(event.streams["x3mini"])
                if isinstance(spec, XspressStart):
                    logger.info("ignore start message")
                    return
                channel = spec.data[1]
        except Exception as e:
            logger.error("failed to parse x3mini %s", e.__repr__())
            return

        if channel is None or spec is None:
            logger.error("failed to parse xspress3 or x3mini spectrum")
            return
        logger.debug("contrast: %s", con)
        logger.debug("spectrum: %s", spec)

        if con.status == "running":
            # new data
            sx, sy = con.pseudo["x"][0], con.pseudo["y"][0]
            logger.debug("process position %s %s", sx, sy)

            # print(spec.data[3])
            res = self.fastFit.fitMultipleSpectra(
                y=channel, weight=0, refit=1, concentrations=1
            )

            result = res.__dict__
            del result["_labelFormats"]
            return {"position": (sx, sy), "fit": result}

    def finish(self, parameters=None):
        print("finished")
