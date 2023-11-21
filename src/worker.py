from dranspose.worker import Worker
from dranspose.data.event import EventData
class FluorescenceWorker(Worker):

    def process_event(self, event: EventData):
        print(event)

        

        return {"x": 3, "Fe": 0.3}
