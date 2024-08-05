from copy import copy

from dranspose.event import ResultData
import h5pyd

class FluorescenceReducer:
    def __init__(self, parameters=None, *args, **kwargs):
        self.publish = {"map": {}, "control":{}}
        self.hsds = h5pyd.File("http://nanomax-pipeline-hsds.daq.maxiv.lu.se/home/live", username="admin",
                               password="admin", mode="a")
        self.first = True
        self.buffer = {}

    def process_result(self, result: ResultData, parameters=None):
        if result.payload:
            if "control" in result.payload:
                self.publish["control"][result.event_number] = result.payload["control"]
                print("saved control message to", self.publish["control"])
            elif "azint" in result.payload:
                self.buffer[result.event_number] = result.payload["azint"]
            elif "fit" in result.payload:
                self.publish["map"][result.payload["position"]] = result.payload[
                    "fit"
                ]
            #print(result.payload["fit"].__dict__)

    def timer(self):
        print("timed")
        if len(self.buffer) > 0:
            if self.first:
                self.hsds.require_group("azint")
                try:
                    del self.hsds["azint"]["data"]
                except:
                    pass
                sample = list(self.buffer.values())[0]
                self.hsds["azint"].require_dataset("data", shape=(0,sample.shape[0]), maxshape=(None,sample.shape[0]),
                                                  dtype=sample.dtype)  # len(result.payload["pcap_start"]),

                self.first = False

            cpy = copy(self.buffer)
            self.buffer = {}
            print("upload buffer", cpy)
            oldsize = self.hsds["azint/data"].shape[0]
            print(oldsize)
            self.hsds["azint/data"].resize( max(oldsize, max(cpy.keys())), axis=0)
            sort_keys = list(sorted(cpy.keys()))
            start = sort_keys[0]
            chunk = [cpy[start]]
            for pevn, evn in zip(sort_keys, sort_keys[1:]):
                if evn == pevn +1:
                    # consecutive
                    chunk.append(cpy[evn])
                else:
                    self.hsds["azint/data"][start:start+len(chunk)] = chunk
                    start = evn
                    chunk = [cpy[start]]
            self.hsds["azint/data"][start:start + len(chunk)] = chunk
        return 1

    def finish(self, parameters=None):
        print("finished reducer")
        print(self.publish)
