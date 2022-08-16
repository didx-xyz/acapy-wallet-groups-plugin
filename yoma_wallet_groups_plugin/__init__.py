"""Handles the initialization of the plugin."""

from aries_cloudagent.admin.request_context import InjectionContext

__version__ = "0.1.0"


async def setup(_: InjectionContext):
    """Plugin initialization call.

    This function is automatically called by ACA-Py during start up.

    Args:
        context (InjectionContext): Context injected by ACA-Py.
    """
