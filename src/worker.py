import json
import logging
import tempfile

from PyMca5.PyMcaIO import ConfigDict
from PyMca5.PyMcaPhysics.xrf.FastXRFLinearFit import FastXRFLinearFit
from dranspose.event import EventData
from dranspose.data.xspress3 import XspressStart, XspressImage
from dranspose.data.contrast import ContrastRunning
from dranspose.data.stream1 import Stream1Data
from dranspose.data.positioncap import PositionCapValues
from dranspose.middlewares.contrast import parse as contrast_parse
from dranspose.middlewares.xspress import parse as xspress_parse
from dranspose.middlewares.stream1 import parse as stins_parse
from dranspose.middlewares.positioncap import PositioncapParser
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
            BinaryParameter(name="poni"),
            StrParameter(name="pcap_channel_x", default="INENC2.VAL.Mean"),
            StrParameter(name="pcap_channel_y", default="INENC3.VAL.Mean"),
        ]
        return params

    def __init__(self, parameters=None, *args, **kwargs):
        self.number = 0
        self.ai = None
        self.pcap = PositioncapParser()
        if "poni_file" in parameters:
            print("par", parameters["poni_file"])
            with tempfile.NamedTemporaryFile() as fp:
                fp.write(parameters["poni_file"].data)
                fp.flush()
                self.ai = azint.AzimuthalIntegrator(fp.name, 4, 100)

    def _azint(self, event):
        if "pilatus" in event.streams:
            logger.debug("use pilatus data for azint")
            if self.ai is not None:
                data = stins_parse(event.streams["pilatus"])
                if isinstance(data, Stream1Data):
                    if "bslz4" in data.compression:
                        bufframe = event.streams["pilatus"].frames[1]
                        if isinstance(bufframe, zmq.Frame):
                            bufframe = bufframe.bytes
                        img = decompress_lz4(bufframe, data.shape, dtype=data.type)
                        # print("decomp", img, img.shape)
                        I, _ = self.ai.integrate(img)
                        logger.info("got I %s", I.shape)
                        return {"azint": I}
        return {}

    def _eigers(self, event):
        ret = {}
        for stream in ["eiger-4m", "eiger-1m"]:
            if stream in event.streams:
                data = stins_parse(event.streams[stream])
                if isinstance(data, Stream1Data):
                    if "bslz4" in data.compression:
                        bufframe = event.streams[stream].frames[1]
                        if isinstance(bufframe, zmq.Frame):
                            bufframe = bufframe.bytes
                        data.data = decompress_lz4(
                            bufframe, data.shape, dtype=data.type
                        )
                logger.info("got %s %s", stream, data)
        return ret

    def process_event(self, event: EventData, parameters=None, *args, **kwargs):
        logger.debug("using parameters %s", parameters)
        ret = {}

        panda0 = None
        if "panda0" in event.streams:
            panda0 = self.pcap.parse(event.streams["panda0"])

        ret.update(self._azint(event))
        ret.update(self._eigers(event))

        contrast = None
        if "contrast" in event.streams:
            contrast = contrast_parse(event.streams["contrast"])
            if not isinstance(contrast, ContrastRunning):
                logger.warning("contrast is %s", contrast)
                ret["contrast"] = contrast

        spectrum = None
        spec = "absent"
        if "xspress3" in event.streams:
            spec = xspress_parse(event.streams["xspress3"])
            if isinstance(spec, XspressImage):
                spectrum = spec.data[3]

        if "x3mini" in event.streams:
            spec = xspress_parse(event.streams["x3mini"])
            if isinstance(spec, XspressImage):
                spectrum = spec.data[1]

        logger.debug("contrast: %s", contrast)
        logger.debug("spectrum: %s", spectrum)

        if panda0 is not None and spectrum is not None:
            if isinstance(panda0, PositionCapValues):
                px = panda0.fields[parameters["pcap_channel_x"].value].value
                py = panda0.fields[parameters["pcap_channel_y"].value].value

                ret["position"] = {"x": px, "y": py}
                ret["spectrum"] = spectrum

        #        sx, sy = con.pseudo["x"][0], con.pseudo["y"][0]
        #        logger.debug("process position %s %s", sx, sy)
        if len(ret) > 0:
            return ret
        # logger.warning("empty worker message %s: %s, %s", event.event_number, panda0, spectrum)

    def finish(self, parameters=None):
        print("finished")
