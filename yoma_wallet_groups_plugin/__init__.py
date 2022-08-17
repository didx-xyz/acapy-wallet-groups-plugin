"""Handles the initialization of the plugin."""

from aries_cloudagent.admin.request_context import InjectionContext
from aries_cloudagent.wallet.models.wallet_record import (
    WalletRecord
)

__version__ = "0.1.0"

original_wallet_init = WalletRecord.__init__

def custom_wallet_init(
        self,
        *,
        group_id: str = None,
        **kwargs
):
    original_wallet_init(self, **kwargs)
    self.group_id = group_id

# Extend wallet record to include the group id as tag name
WalletRecord.TAG_NAMES = {"wallet_name", "group_id"}
WalletRecord.group_id = None
WalletRecord.__init__ = custom_wallet_init

async def setup(_: InjectionContext):
    """Plugin initialization call.

    This function is automatically called by ACA-Py during start up.

    Args:
        context (InjectionContext): Context injected by ACA-Py.
    """
