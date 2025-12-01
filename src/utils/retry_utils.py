# ==============================================================================
# File Location: dart-agent/src/utils/retry_utils.py
# File Name: retry_utils.py
# Description:
# - Exponential backoff decorator for async functions.
# - Logs retries with incident context for visibility.
# Inputs:
# - Wrapped async function arguments; retry/backoff configuration; exception types.
# Outputs:
# - Wrapped function result or propagated exception after retries; trace logs of retries.
# ==============================================================================

import time
import functools
import asyncio
from typing import Type, Tuple, Union
from src.utils.trace_viz import trace

def with_backoff(
    retries: int = 3, 
    base_delay: float = 1.0, 
    backoff_factor: float = 2.0, 
    exceptions: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception
):
    """
    Decorator that applies exponential backoff to any async function.
    
    Args:
        retries: Max attempts before giving up.
        base_delay: Initial sleep time (seconds).
        backoff_factor: Multiplier for delay (1s -> 2s -> 4s).
        exceptions: Which exceptions trigger a retry.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = base_delay
            last_exception = None
            
            # The Incident ID must be passed to the logger
            incident_id = kwargs.get('incident_id') or args[1] if len(args) > 1 and isinstance(args[1], str) else None
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < retries:
                        trace.log("System", f"⚠️ Operation failed ({e}). Retrying in {delay}s...", "warning", incident_id=incident_id)
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        trace.log("System", f"❌ Max retries exceeded for {func.__name__}.", "error", incident_id=incident_id)
            
            # Re-raise the last exception if we failed all attempts
            raise last_exception
        return wrapper
    return decorator
