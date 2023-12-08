from dranspose.event import ResultData


class FluorescenceReducer:
    def __init__(self, parameters=None):
        self.publish = {"map": {}, "control":{}}

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            if "control" in result.payload:
                self.publish["control"][result.event_number] = result.payload["control"]
                print("saved control message to", self.publish["control"])
            else:
                self.publish["map"][result.payload["position"]] = result.payload[
                    "fit"
                ]
            #print(result.payload["fit"].__dict__)

    def finish(self, parameters=None):
        print("finished reducer")
        print(self.publish)
