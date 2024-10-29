from copy import copy

from dranspose.event import ResultData
import h5pyd


class FluorescenceReducer:
    def __init__(self, parameters=None, *args, **kwargs):
        self.publish = {"map": {}, "control": {}, "azint": {"data": []}}

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            if "control" in result.payload:
                self.publish["control"][result.event_number] = result.payload["control"]
                print("saved control message to", self.publish["control"])
            elif "azint" in result.payload:
                self.publish["azint"]["data"].append(result.payload["azint"])
            elif "fit" in result.payload:
                self.publish["map"][result.payload["position"]] = result.payload["fit"]
            # print(result.payload["fit"].__dict__)

    def finish(self, parameters=None):
        print("finished reducer")
        print(self.publish)
