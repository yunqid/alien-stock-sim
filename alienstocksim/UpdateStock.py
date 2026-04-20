import redis
import asyncio
import threading
from alienstocksim.consumers import StockConsumer

r = redis.Redis()

# Returns true if lock is set
def acquire_lock():
    return r.set("stock_engine_lock", "locked", nx=True, ex=60)

def BeginStockUpdate():
    # Makes sure that only one instance of this is ran
    if not acquire_lock():
        return
    
    # Need to create a seperate loop than the asgi event loop
    loop = asyncio.new_event_loop()

    def worker():
        asyncio.set_event_loop(loop)
        consumer = StockConsumer()
        # The task to repeat is send_stock_data
        loop.create_task(consumer.send_stock_data())
        loop.run_forever()

    # Creating the background thread and running it
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
