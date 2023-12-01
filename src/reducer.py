from dranspose.event import ResultData


class FluorescenceReducer:
    def __init__(self, parameters=None):
        self.publish = {"map": {}}

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            self.publish["map"][result.payload["position"]] = result.payload[
                "fit"
            ]
            #print(result.payload["fit"].__dict__)

    def finish(self, parameters=None):
        print("finished reducer")
        print(self.publish)
