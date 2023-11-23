

class FluorescenceReducer:
    def __init__(self):
        self.result = {"map":[]}

    def process_data(self, data):
        self.result["map"].append(data)

    def __del__(self):
        print(self.result["map"])