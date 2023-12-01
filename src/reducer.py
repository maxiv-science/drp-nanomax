from dranspose.event import ResultData


class FluorescenceReducer:
    def __init__(self):
        self.publish = {"map": {}}

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            self.publish["map"][result.payload["position"]] = result.payload[
                "concentations"
            ]

    def finish(self, parameters=None):
        print("finished reducer")
        print(self.publish)