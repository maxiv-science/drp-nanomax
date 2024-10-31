import logging
import tempfile
from threading import Lock

import numpy as np
from PyMca5.PyMcaPhysics.xrf.FastXRFLinearFit import FastXRFLinearFit
from dranspose.event import ResultData
from dranspose.parameters import BinaryParameter


class FluorescenceReducer:
    def __init__(self, parameters=None, *args, **kwargs):
        self.x = []
        self.y = []
        self.publish = {
            "map": {},
            "control": {},
            "azint": {"data": []},
        }
        self.buffer = {}
        self.buffer_lock = Lock()
        self.fastFit = FastXRFLinearFit()
        if "mca_config" in parameters:
            with tempfile.NamedTemporaryFile() as fp:
                fp.write(parameters["mca_config"].data)
                self.fastFit.setFitConfigurationFile(fp.name)

    @staticmethod
    def describe_parameters():
        params = [
            BinaryParameter(name="mca_config"),
        ]
        return params

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            if "control" in result.payload:
                # self.publish["control"][result.event_number] = result.payload["control"]
                print("saved control message to", self.publish["control"])
            elif "azint" in result.payload:
                self.publish["azint"]["data"].append(result.payload["azint"])
            elif "spectrum" in result.payload:
                with self.buffer_lock:
                    self.buffer[result.payload["position"]] = result.payload["spectrum"]

    def timer(self):
        spectra = None
        with self.buffer_lock:
            if len(self.buffer) > 0:
                spectra = np.array(list(self.buffer.values()))
                positions = list(self.buffer.keys())
                self.buffer = {}
        if spectra is not None:
            logging.warning("process spectra %s", spectra.shape)
            res = self.fastFit.fitMultipleSpectra(
                y=spectra, weight=0, refit=1, concentrations=1
            )

            result = res.__dict__

            for maptype in result["_buffers"]:
                if maptype not in self.publish["map"]:
                    self.publish["map"][maptype] = {}
                for label, val in zip(
                    result["_labels"][maptype], result["_buffers"][maptype]
                ):
                    if label not in self.publish["map"][maptype]:
                        self.publish["map"][maptype][label] = {
                            "x": self.x,
                            "y": self.y,
                            "values": [],
                        }
                        self.publish["map"][maptype][f"{label}_attrs"] = {
                            "NX_class": "NXdata",
                            "signal": "values",
                            "axes": ["x", "y"],
                        }
                    self.publish["map"][maptype][label]["values"] += val.tolist()
            self.x += [p[0] for p in positions]
            self.y += [p[1] for p in positions]

        return 0.5

    def finish(self, parameters=None):
        print("finished reducer")
        # print(self.publish)
