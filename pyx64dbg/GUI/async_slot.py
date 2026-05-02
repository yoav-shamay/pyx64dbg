import asyncio
from functools import wraps

def async_slot(func):
    """
    Decorator to connect async methods to standard Qt signals.
    Automatically schedules the coroutine on the active asyncio event loop.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Catch any arguments the signal emits and pass them to the async function
        return asyncio.create_task(func(*args, **kwargs))
    
    return wrapper