"""
    Multitenant admin routes.

    This file has been copied from: https://github.com/hyperledger/aries-cloudagent-python/blob/d407c48cc9f041c5b27ee8f589fc0e2eaef2220d/aries_cloudagent/multitenant/admin/routes.py

    We do this because we want to override two endpoints
"""

from aiohttp import web
from aiohttp_apispec import (
    docs,
    match_info_schema,
    querystring_schema,
    request_schema,
    response_schema,
)
from marshmallow import ValidationError, fields, validate, validates_schema

from aries_cloudagent.multitenant.admin.routes import (
    wallet_update,
    wallet_create_token,
    wallet_remove,
    WalletListSchema,
    CreateWalletResponseSchema,
)
from aries_cloudagent.admin.request_context import AdminRequestContext
from aries_cloudagent.core.error import BaseError
from aries_cloudagent.core.profile import ProfileManagerProvider
from aries_cloudagent.messaging.models.base import BaseModelError
from aries_cloudagent.messaging.models.openapi import OpenAPISchema
from aries_cloudagent.messaging.valid import UUIDFour
from aries_cloudagent.multitenant.base import BaseMultitenantManager, BaseStorage
from aries_cloudagent.storage.error import StorageError, StorageNotFoundError
from aries_cloudagent.wallet.models.wallet_record import (
    WalletRecord,
    WalletRecordSchema,
)


def format_wallet_record(wallet_record: WalletRecord):
    """Serialize a WalletRecord object."""

    wallet_info = wallet_record.serialize()

    # Hide wallet wallet key
    if "wallet.key" in wallet_info["settings"]:
        del wallet_info["settings"]["wallet.key"]

    group_id = wallet_record.tags.get("group_id")
    if group_id:
        wallet_info["group_id"] = group_id

    return wallet_info


class YomaMultitenantModuleResponseSchema(OpenAPISchema):
    """Response schema for multitenant module."""


class YomaWalletIdMatchInfoSchema(OpenAPISchema):
    """Path parameters and validators for request taking wallet id."""

    wallet_id = fields.Str(
        description="Subwallet identifier", required=True, example=UUIDFour.EXAMPLE
    )


class YomaCreateWalletRequestSchema(OpenAPISchema):
    """Request schema for adding a new wallet which will be registered by the agent."""

    wallet_name = fields.Str(description="Wallet name", example="MyNewWallet")

    wallet_key = fields.Str(
        description="Master key used for key derivation.", example="MySecretKey123"
    )

    # TODO: determine the example for the group identifier
    group_id = fields.Str(description="Wallet group identifier.", example="NL")

    wallet_key_derivation = fields.Str(
        description="Key derivation",
        required=False,
        example="RAW",
        validate=validate.OneOf(["ARGON2I_MOD", "ARGON2I_INT", "RAW"]),
    )

    wallet_type = fields.Str(
        description="Type of the wallet to create",
        example="indy",
        default="in_memory",
        validate=validate.OneOf(
            [wallet_type for wallet_type in ProfileManagerProvider.MANAGER_TYPES]
        ),
    )

    wallet_dispatch_type = fields.Str(
        description="Webhook target dispatch type for this wallet. \
            default - Dispatch only to webhooks associated with this wallet. \
            base - Dispatch only to webhooks associated with the base wallet. \
            both - Dispatch to both webhook targets.",
        example="default",
        default="default",
        validate=validate.OneOf(["default", "both", "base"]),
    )

    wallet_webhook_urls = fields.List(
        fields.Str(
            description="Optional webhook URL to receive webhook messages",
            example="http://localhost:8022/webhooks",
        ),
        required=False,
        description="List of Webhook URLs associated with this subwallet",
    )

    label = fields.Str(
        description="Label for this wallet. This label is publicized\
            (self-attested) to other agents as part of forming a connection.",
        example="Alice",
    )

    image_url = fields.Str(
        description="Image url for this wallet. This image url is publicized\
            (self-attested) to other agents as part of forming a connection.",
        example="https://aries.ca/images/sample.png",
    )

    key_management_mode = fields.Str(
        description="Key management method to use for this wallet.",
        example=WalletRecord.MODE_MANAGED,
        default=WalletRecord.MODE_MANAGED,
        # MTODO: add unmanaged mode once implemented
        validate=validate.OneOf((WalletRecord.MODE_MANAGED,)),
    )

    @validates_schema
    def validate_fields(self, data, **kwargs):
        """
        Validate schema fields.

        Args:
            data: The data to validate

        Raises:
            ValidationError: If any of the fields do not validate

        """

        if data.get("wallet_type") == "indy":
            for field in ("wallet_key", "wallet_name"):
                if field not in data:
                    raise ValidationError("Missing required field", field)


class YomaWalletListQueryStringSchema(OpenAPISchema):
    """Parameters and validators for wallet list request query string."""

    wallet_name = fields.Str(description="Wallet name", example="MyNewWallet")

    # TODO: determine the example for the group identifier
    group_id = fields.Str(description="Wallet group identifier", example="NL")


@docs(tags=["multitenancy"], summary="Query subwallets")
@querystring_schema(YomaWalletListQueryStringSchema())
@response_schema(WalletListSchema(), 200, description="")
async def wallets_list(request: web.BaseRequest):
    """
    Request handler for listing all internal subwallets.

    Args:
        request: aiohttp request object
    """

    context: AdminRequestContext = request["context"]
    profile = context.profile

    query = {}
    wallet_name = request.query.get("wallet_name")
    group_id = request.query.get("group_id")
    if wallet_name:
        query["wallet_name"] = wallet_name
    if group_id:
        query["roup_id"] = group_id

    try:
        async with profile.session() as session:
            records = await WalletRecord.query(session, tag_filter=query)
        results = [format_wallet_record(record) for record in records]
        results.sort(key=lambda w: w["created_at"])
    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


@docs(tags=["multitenancy"], summary="Get a single subwallet")
@match_info_schema(YomaWalletIdMatchInfoSchema())
@response_schema(WalletRecordSchema(), 200, description="")
async def wallet_get(request: web.BaseRequest):
    """
    Request handler for getting a single subwallet.

    Args:
        request: aiohttp request object

    Raises:
        HTTPNotFound: if wallet_id does not match any known wallets

    """

    context: AdminRequestContext = request["context"]
    profile = context.profile
    wallet_id = request.match_info["wallet_id"]

    try:
        async with profile.session() as session:
            wallet_record = await WalletRecord.retrieve_by_id(session, wallet_id)
        result = format_wallet_record(wallet_record)
    except StorageNotFoundError as err:
        raise web.HTTPNotFound(reason=err.roll_up) from err
    except BaseModelError as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response(result)


@docs(tags=["multitenancy"], summary="Create a subwallet")
@request_schema(YomaCreateWalletRequestSchema)
@response_schema(CreateWalletResponseSchema(), 200, description="")
async def wallet_create(request: web.BaseRequest):
    """
    Request handler for adding a new subwallet for handling by the agent.

    Args:
        request: aiohttp request object
    """

    context: AdminRequestContext = request["context"]
    body = await request.json()

    key_management_mode = body.get("key_management_mode") or WalletRecord.MODE_MANAGED
    wallet_key = body.get("wallet_key")
    group_id = body.get("group_id")
    wallet_webhook_urls = body.get("wallet_webhook_urls") or []
    wallet_dispatch_type = body.get("wallet_dispatch_type") or "default"
    # If no webhooks specified, then dispatch only to base webhook targets
    if wallet_webhook_urls == []:
        wallet_dispatch_type = "base"

    settings = {
        "wallet.type": body.get("wallet_type") or "in_memory",
        "wallet.name": body.get("wallet_name"),
        "wallet.key": wallet_key,
        "wallet.webhook_urls": wallet_webhook_urls,
        "wallet.dispatch_type": wallet_dispatch_type,
    }

    label = body.get("label")
    image_url = body.get("image_url")
    key_derivation = body.get("wallet_key_derivation")
    if label:
        settings["default_label"] = label
    if image_url:
        settings["image_url"] = image_url
    if key_derivation:  # allow lower levels to handle default
        settings["wallet.key_derivation_method"] = key_derivation

    try:
        multitenant_mgr = context.profile.inject(BaseMultitenantManager)

        wallet_record = await multitenant_mgr.create_wallet(
            settings, key_management_mode
        )

        if group_id:
            print(f"--------- GROUP_ID {group_id} ---------------")
            # This can update the settings but we cannot query this...
            wallet_record.update_settings({"wallet.group_id": group_id})

            # This errors because we do not supply `group_id` in the constructor
            wallet_record.TAG_NAMES.update({"group_id"})

            # Does not add anything as I believe it is a "readonly" property
            wallet_record.tags.update({"~group_id": group_id})

            # Empty dict. should contain: `{"group_id": "NL"}`
            print(wallet_record.tags)

        token = await multitenant_mgr.create_auth_token(wallet_record, wallet_key)
    except BaseError as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    result = {
        **format_wallet_record(wallet_record),
        "token": token,
    }
    return web.json_response(result)


async def register(app: web.Application):
    """Register routes."""

    app.add_routes(
        [
            web.get("/multitenancy/wallets", wallets_list, allow_head=False),
            web.post("/multitenancy/wallet", wallet_create),
            web.get("/multitenancy/wallet/{wallet_id}", wallet_get, allow_head=False),
            web.put("/multitenancy/wallet/{wallet_id}", wallet_update),
            web.post("/multitenancy/wallet/{wallet_id}/token", wallet_create_token),
            web.post("/multitenancy/wallet/{wallet_id}/remove", wallet_remove),
        ]
    )


def post_process_routes(app: web.Application):
    """Amend swagger API."""

    # Add top-level tags description
    if "tags" not in app._state["swagger_dict"]:
        app._state["swagger_dict"]["tags"] = []

    app._state["swagger_dict"]["tags"].append(
        {
            "name": "yoma-multitenancy",
            "description": "Yoma specific Multitenant wallet management",
        }
    )
