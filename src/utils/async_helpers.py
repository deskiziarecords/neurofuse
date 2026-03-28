# file: src/utils/async_helpers.py
import asyncio
import threading

_loop = None
_loop_lock = threading.Lock()

def get_global_loop():
    global _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            t = threading.Thread(target=_loop.run_forever, daemon=True)
            t.start()
        return _loop

async def create_plugin_task(coro):
    """Wraps a plugin coroutine so we can catch exceptions."""
    try:
        await coro
    except Exception as exc:
        # In a real system, you might log this or update a status object
        raise exc
