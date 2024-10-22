"""Handles the initialization of the plugin."""

import logging
from importlib import metadata

from acapy_agent.admin.request_context import InjectionContext
from acapy_agent.wallet.models.wallet_record import WalletRecord

LOGGER = logging.getLogger(__name__)

__version__ = metadata.version("acapy_wallet_groups_plugin")

# ------------------------------------------
# The code below done because ACA-Py, version 0.7.4 does not support custom
# user-defined tags. This custom_wallet_init allows us to set the
# `self.group_id` and afterwards we add it to the `TAG_NAMES` so that indy sees
# it as a wallet tag.
#
# We need support for custom tags so we can query, retrieving, a sub-set of
# wallets.

original_wallet_init = WalletRecord.__init__


def custom_wallet_init(self, *, group_id: str = None, **kwargs):
    original_wallet_init(self, **kwargs)
    self.group_id = group_id


# Extend wallet record to include the group id as tag name
WalletRecord.TAG_NAMES = {*WalletRecord.TAG_NAMES, "group_id"}
WalletRecord.group_id = None
WalletRecord.__init__ = custom_wallet_init
# ------------------------------------------


async def setup(_: InjectionContext):
    """Plugin initialization call.

    This function is automatically called by ACA-Py during start up.

    Args:
        context (InjectionContext): Context injected by ACA-Py.
    """
    LOGGER.info("ACA-Py Wallet Groups plugin set up.")
