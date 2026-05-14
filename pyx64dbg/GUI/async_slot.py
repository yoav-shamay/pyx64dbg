from __future__ import annotations
import asyncio
from functools import wraps
from typing import Any, Callable, ParamSpec, Awaitable

P = ParamSpec("P") # parameter specifications of the callables

# save a reference to all background tasks created so they aren't discarded by the garbage collecotr.
background_tasks: set[asyncio.Task[Any]] = set()

def async_slot(func: Callable[P, Awaitable[Any]]) -> Callable[P, None]:
    """
    Decorator to connect async methods to standard Qt signals.
    Automatically schedules the coroutine on the active asyncio event loop.
    """
    # define the wrapper function
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs):
        # Catch any arguments the signal emits and pass them to the async function
        task = asyncio.create_task(func(*args, **kwargs))
        # save a reference to the task to prevent it from getting garbage collected, and remove it once the task is done
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
    
    return wrapper