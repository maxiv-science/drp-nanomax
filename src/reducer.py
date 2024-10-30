from dranspose.event import ResultData


class FluorescenceReducer:
    def __init__(self, parameters=None, *args, **kwargs):
        self.publish = {
            "map": {"x": [], "y": [], "values": []},
            "map_attrs": {"NX_class": "NXdata", "signal": "values", "axes": ["x", "y"]},
            "control": {},
            "azint": {"data": []},
        }

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            if "control" in result.payload:
                # self.publish["control"][result.event_number] = result.payload["control"]
                print("saved control message to", self.publish["control"])
            elif "azint" in result.payload:
                self.publish["azint"]["data"].append(result.payload["azint"])
            elif "fit" in result.payload:
                self.publish["map"]["x"].append(result.payload["position"][0])
                self.publish["map"]["y"].append(result.payload["position"][1])
                self.publish["map"]["values"].append(
                    result.payload["fit"]["parameters"][5][0]
                )

    def finish(self, parameters=None):
        print("finished reducer")
        print(self.publish)
