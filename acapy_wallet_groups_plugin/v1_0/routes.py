"""
Multitenant admin routes.

This file has been copied from: https://github.com/openwallet-foundation/acapy/blob/1.3.0/acapy_agent/multitenant/admin/routes.py

We do this because we want to override 4 endpoints - create, update, list, get
"""

from acapy_agent.admin.request_context import AdminRequestContext
from acapy_agent.core.error import BaseError
from acapy_agent.messaging.models.base import BaseModelError
from acapy_agent.messaging.models.openapi import OpenAPISchema
from acapy_agent.messaging.models.paginated_query import get_paginated_query_params
from acapy_agent.multitenant.admin.routes import (
    CreateWalletRequestSchema,
    CreateWalletResponseSchema,
    UpdateWalletRequestSchema,
    WalletIdMatchInfoSchema,
    WalletListQueryStringSchema,
    WalletSettingsError,
    get_extra_settings_dict_per_tenant,
    wallet_create_token,
    wallet_remove,
)
from acapy_agent.multitenant.base import BaseMultitenantManager
from acapy_agent.storage.error import StorageError, StorageNotFoundError
from acapy_agent.utils.endorsement_setup import attempt_auto_author_with_endorser_setup
from acapy_agent.wallet.models.wallet_record import WalletRecord, WalletRecordSchema
from aiohttp import web
from aiohttp_apispec import (
    docs,
    match_info_schema,
    querystring_schema,
    request_schema,
    response_schema,
)
from marshmallow import fields


# Deduplicate GroupId field definition, to append to following OpenApiSchema classes
class GroupId:
    group_id = fields.Str(
        metadata={"description": "Wallet group identifier.", "example": "some_group_id"}
    )


class CreateWalletRequestWithGroupIdSchema(CreateWalletRequestSchema):
    """Request schema for adding a new wallet which will be registered by the agent."""

    group_id = fields.Str(
        metadata={
            "description": "An optional group identifier. Useful with `get_tenants` to fetch wallets by group id.",
            "example": "some_group_id",
        }
    )


class CreateWalletResponseWithGroupIdSchema(CreateWalletResponseSchema, GroupId):
    """Response schema for creating a wallet."""


class WalletListQueryStringWithGroupIdSchema(WalletListQueryStringSchema, GroupId):
    """Parameters and validators for wallet list request query string."""


class UpdateWalletRequestWithGroupIdSchema(UpdateWalletRequestSchema, GroupId):
    """Request schema for updating a existing wallet."""


class WalletRecordWithGroupIdSchema(WalletRecordSchema, GroupId):
    """Schema to allow serialization/deserialization of record."""


class WalletListWithGroupIdSchema(OpenAPISchema):
    """Result schema for wallet list."""

    results = fields.List(
        fields.Nested(WalletRecordWithGroupIdSchema()),
        metadata={"description": "List of wallet records"},
    )


def format_wallet_record(wallet_record: WalletRecord):
    """Serialize a WalletRecord object."""

    wallet_info = wallet_record.serialize()

    # Hide wallet wallet key
    if "wallet.key" in wallet_info["settings"]:
        del wallet_info["settings"]["wallet.key"]

    if wallet_record.group_id:
        wallet_info["group_id"] = wallet_record.group_id

    return wallet_info


@docs(tags=["multitenancy"], summary="Query subwallets")
@querystring_schema(WalletListQueryStringWithGroupIdSchema())
@response_schema(WalletListWithGroupIdSchema(), 200, description="")
async def wallets_list(request: web.BaseRequest):
    """Request handler for listing all internal subwallets.

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
        query["group_id"] = group_id

    limit, offset, order_by, descending = get_paginated_query_params(request)

    try:
        async with profile.session() as session:
            records = await WalletRecord.query(
                session,
                tag_filter=query,
                limit=limit,
                offset=offset,
                order_by=order_by,
                descending=descending,
            )
        results = [format_wallet_record(record) for record in records]
    except (StorageError, BaseModelError) as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    return web.json_response({"results": results})


@docs(tags=["multitenancy"], summary="Get a single subwallet")
@match_info_schema(WalletIdMatchInfoSchema())
@response_schema(WalletRecordWithGroupIdSchema(), 200, description="")
async def wallet_get(request: web.BaseRequest):
    """Request handler for getting a single subwallet.

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
@request_schema(CreateWalletRequestWithGroupIdSchema)
@response_schema(CreateWalletResponseWithGroupIdSchema(), 200, description="")
async def wallet_create(request: web.BaseRequest):
    """Request handler for adding a new subwallet for handling by the agent.

    Args:
        request: aiohttp request object
    """

    context: AdminRequestContext = request["context"]
    body = await request.json()

    base_wallet_type = context.profile.settings.get("wallet.type")
    sub_wallet_type = body.get("wallet_type", base_wallet_type)

    key_management_mode = body.get("key_management_mode") or WalletRecord.MODE_MANAGED
    wallet_key = body.get("wallet_key")
    group_id = body.get("group_id")
    wallet_webhook_urls = body.get("wallet_webhook_urls") or []
    wallet_dispatch_type = body.get("wallet_dispatch_type") or "default"
    extra_settings = body.get("extra_settings") or {}
    # If no webhooks specified, then dispatch only to base webhook targets
    if wallet_webhook_urls == []:
        wallet_dispatch_type = "base"

    settings = {
        "wallet.type": sub_wallet_type,
        "wallet.name": body.get("wallet_name"),
        "wallet.key": wallet_key,
        "wallet.webhook_urls": wallet_webhook_urls,
        "wallet.dispatch_type": wallet_dispatch_type,
    }
    extra_subwallet_setting = get_extra_settings_dict_per_tenant(extra_settings)
    settings.update(extra_subwallet_setting)

    label = body.get("label")
    image_url = body.get("image_url")
    key_derivation = body.get("wallet_key_derivation")
    if label:
        settings["default_label"] = label
    if image_url:
        settings["image_url"] = image_url
    if key_derivation:  # allow lower levels to handle default
        settings["wallet.key_derivation_method"] = key_derivation

    if group_id is not None:
        settings["wallet.group_id"] = group_id  # add group_id to wallet settings

    try:
        multitenant_mgr = context.profile.inject(BaseMultitenantManager)

        wallet_record = await multitenant_mgr.create_wallet(
            settings, key_management_mode
        )

        # Set the custom group_id
        if group_id:
            wallet_record.group_id = group_id

            # Save the record with the custom group_id
            async with context.profile.session() as session:
                await wallet_record.save(session)

        token = await multitenant_mgr.create_auth_token(wallet_record, wallet_key)

        wallet_profile = await multitenant_mgr.get_wallet_profile(
            context, wallet_record, extra_settings=settings
        )
        await attempt_auto_author_with_endorser_setup(wallet_profile)
    except BaseError as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

    result = {
        **format_wallet_record(wallet_record),
        "token": token,
    }
    return web.json_response(result)


@docs(tags=["multitenancy"], summary="Update a subwallet")
@match_info_schema(WalletIdMatchInfoSchema())
@request_schema(UpdateWalletRequestWithGroupIdSchema)
@response_schema(WalletRecordWithGroupIdSchema(), 200, description="")
async def wallet_update(request: web.BaseRequest):
    """Request handler for updating a existing subwallet for handling by the agent.

    Args:
        request: aiohttp request object
    """

    context: AdminRequestContext = request["context"]
    wallet_id = request.match_info["wallet_id"]

    body = await request.json()
    wallet_webhook_urls = body.get("wallet_webhook_urls")
    wallet_dispatch_type = body.get("wallet_dispatch_type")
    label = body.get("label")
    image_url = body.get("image_url")
    group_id = body.get("group_id")
    extra_settings = body.get("extra_settings")

    if all(
        v is None
        for v in (
            wallet_webhook_urls,
            wallet_dispatch_type,
            label,
            image_url,
            extra_settings,
            group_id,
        )
    ):
        raise web.HTTPBadRequest(reason="At least one parameter is required.")

    # adjust wallet_dispatch_type according to wallet_webhook_urls
    if wallet_webhook_urls and wallet_dispatch_type is None:
        wallet_dispatch_type = "default"
    if wallet_webhook_urls == []:
        wallet_dispatch_type = "base"

    # only parameters that are not none are updated
    settings = {}
    if wallet_webhook_urls is not None:
        settings["wallet.webhook_urls"] = wallet_webhook_urls
    if wallet_dispatch_type is not None:
        settings["wallet.dispatch_type"] = wallet_dispatch_type
    if label is not None:
        settings["default_label"] = label
    if image_url is not None:
        settings["image_url"] = image_url

    if group_id is not None:
        settings["wallet.group_id"] = group_id  # add group_id to wallet settings

    extra_subwallet_setting = get_extra_settings_dict_per_tenant(extra_settings or {})
    settings.update(extra_subwallet_setting)

    try:
        multitenant_mgr = context.profile.inject(BaseMultitenantManager)
        wallet_record = await multitenant_mgr.update_wallet(wallet_id, settings)

        if group_id is not None:
            wallet_record.group_id = group_id

            # Save the record with the new custom group_id
            async with context.profile.session() as session:
                await wallet_record.save(session)

        result = format_wallet_record(wallet_record)
    except StorageNotFoundError as err:
        raise web.HTTPNotFound(reason=err.roll_up) from err
    except WalletSettingsError as err:
        raise web.HTTPBadRequest(reason=err.roll_up) from err

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
        {"name": "multitenancy", "description": "Multitenant wallet management"}
    )
