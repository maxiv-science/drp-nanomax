import json

from dranspose.event import EventData

import numpy as np

class FluorescenceWorker:

    def __init__(self):
        self.number = 0

    def process_event(self, event: EventData, parameters = None):
        #print(event)

        ps = event.streams["position"]
        assert ps.typ == "motors"
        positions = json.loads(ps.frames[0].bytes)
        #print(positions)

        es = event.streams["energy"]
        assert es.typ == "xspress3"
        header = json.loads(es.frames[0].bytes)
        spectra = np.frombuffer(es.frames[1].bytes, dtype=header["dtype"]).reshape(header["shape"])

        #print(spectra[3])

        return {"position": positions,
                "concentrations": {"Fe": spectra[3][100:200].sum(), "As": spectra[3][200:300].sum()}}
