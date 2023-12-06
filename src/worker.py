import json
import logging
import tempfile

from PyMca5.PyMcaIO import ConfigDict
from PyMca5.PyMcaPhysics.xrf.FastXRFLinearFit import FastXRFLinearFit
from dranspose.event import EventData
from dranspose.middlewares import contrast
from dranspose.middlewares import xspress
from dranspose.parameters import StrParameter, FileParameter
import numpy as np

logger = logging.getLogger(__name__)


class FluorescenceWorker:

    @staticmethod
    def describe_parameters():
        params = [
            FileParameter(name="mca_config"),
        ]
        return params

    def __init__(self, parameters=None):
        self.number = 0
        self.fastFit = FastXRFLinearFit()
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(parameters["mca_config_file"].data)
            self.fastFit.setFitConfigurationFile(fp.name)

    def process_event(self, event: EventData, parameters=None):
        logger.debug("using parameters %s", parameters)
        if {"contrast", "xspress3"} - set(event.streams.keys()) != set():
            logger.error(
                "missing streams for this worker, only present %s", event.streams.keys()
            )
            return
        try:
            con = contrast.parse(event.streams["contrast"])
        except Exception as e:
            logger.error("failed to parse contrast %s", e.__repr__())
            return

        try:
            spec = xspress.parse(event.streams["xspress3"])
        except Exception as e:
            logger.error("failed to parse xspress3 %s", e.__repr__())
            return
        logger.debug("contrast: %s", con)
        logger.debug("spectrum: %s", spec)

        if con.status == "running":
            # new data
            sx, sy = con.pseudo["x"][0], con.pseudo["y"][0]
            logger.debug("process position %s %s", sx, sy)

            #print(spec.data[3])
            res = self.fastFit.fitMultipleSpectra(y=spec.data[3],
                                       weight=0,
                                       refit=1,
                                       concentrations=1)

            result = res.__dict__
            del result["_labelFormats"]
            return {"position": (sx, sy), "fit": result}

    def finish(self, parameters=None):
        print("finished")
