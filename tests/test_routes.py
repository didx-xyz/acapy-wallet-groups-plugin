import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aries_cloudagent.admin.request_context import AdminRequestContext
from aries_cloudagent.askar.profile import AskarProfile
from aries_cloudagent.core.in_memory.profile import InMemoryProfile
from aries_cloudagent.messaging.models.base import BaseModelError
from aries_cloudagent.multitenant.base import (
    BaseMultitenantManager,
    MultitenantManagerError,
)
from aries_cloudagent.multitenant.error import WalletKeyMissingError
from aries_cloudagent.storage.error import StorageError, StorageNotFoundError
from aries_cloudagent.wallet.models.wallet_record import WalletRecord
from marshmallow.exceptions import ValidationError

import acapy_wallet_groups_plugin.v1_0.routes as test_module

test_created_at = 1234567890
test_group_id = "test-group-id"
test_image_url = "test-image-url"
test_key = "dummy_key"
test_label = "test-label"
test_token = "test_token"
test_wallet_id = "test-wallet-id"
test_wallet_name = "wallet_name"

dict_wallet_key = {"wallet_key": test_key}

setting_wallet_name = "wallet.name"
setting_wallet_key = "wallet.key"
dict_setting_wallet_name = {setting_wallet_name: test_wallet_name}
dict_wallet_id_w_settings = {
    "wallet_id": test_wallet_id,
    "settings": dict_setting_wallet_name,
}
dict_wallet_id_no_settings = {
    "wallet_id": test_wallet_id,
    "settings": {},
}


class TestMultitenantRoutes(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_multitenant_mgr = MagicMock(__aexit__=AsyncMock(), autospec=True)
        self.mock_multitenant_mgr.__aenter__ = AsyncMock(
            return_value=self.mock_multitenant_mgr
        )
        self.profile = InMemoryProfile.test_profile(
            settings={"wallet.type": "askar"},
            profile_class=AskarProfile,
        )
        self.context = AdminRequestContext.test_context({}, self.profile)
        self.request_dict = {
            "context": self.context,
        }

        self.context.profile.context.injector.bind_instance(
            BaseMultitenantManager, self.mock_multitenant_mgr
        )

        self.request_dict = {
            "context": self.context,
            "outbound_message_router": AsyncMock(),
        }
        self.request = MagicMock(
            app={},
            match_info={},
            query={},
            __getitem__=lambda _, k: self.request_dict[k],
        )

    async def test_format_wallet_record_removes_wallet_key(self):
        wallet_record = WalletRecord(
            wallet_id=test_wallet_id,
            key_management_mode=WalletRecord.MODE_MANAGED,
            settings={
                setting_wallet_name: test_wallet_name,
                setting_wallet_key: test_key,
            },
        )

        formatted = test_module.format_wallet_record(wallet_record)

        assert setting_wallet_key not in formatted["settings"]

    async def test_wallets_list(self):
        with patch.object(
            test_module, "WalletRecord", autospec=True
        ) as mock_wallet_record, patch.object(
            test_module.web, "json_response"
        ) as mock_response:
            wallets = [
                MagicMock(
                    serialize=MagicMock(
                        return_value={
                            "wallet_id": test_wallet_id,
                            "settings": dict_setting_wallet_name,
                            "created_at": str(test_created_at),
                        }
                    )
                ),
                MagicMock(
                    serialize=MagicMock(
                        return_value={
                            "wallet_id": test_wallet_id,
                            "settings": dict_setting_wallet_name,
                            "created_at": str(test_created_at + 1),
                        }
                    )
                ),
                MagicMock(
                    serialize=MagicMock(
                        return_value={
                            "wallet_id": test_wallet_id,
                            "settings": dict_setting_wallet_name,
                            "created_at": str(test_created_at + 2),
                        }
                    )
                ),
            ]
            mock_wallet_record.query = AsyncMock()
            mock_wallet_record.query.return_value = [wallets[2], wallets[0], wallets[1]]

            await test_module.wallets_list(self.request)
            mock_response.assert_called_once_with(
                {"results": [test_module.format_wallet_record(w) for w in wallets]}
            )

    async def test_wallets_list_x(self):
        with patch.object(
            test_module, "WalletRecord", autospec=True
        ) as mock_wallet_record:
            mock_wallet_record.query = AsyncMock()

            mock_wallet_record.query.side_effect = StorageError()
            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.wallets_list(self.request)

            mock_wallet_record.query.side_effect = BaseModelError()
            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.wallets_list(self.request)

    async def test_wallets_list_query(self):
        self.request.query = {"wallet_name": test_wallet_name}

        with patch.object(
            test_module, "WalletRecord", autospec=True
        ) as mock_wallet_record, patch.object(
            test_module.web, "json_response"
        ) as mock_response:
            wallets = [
                MagicMock(
                    group_id=test_group_id,
                    serialize=MagicMock(
                        return_value={
                            "wallet_id": test_wallet_id,
                            "settings": dict_setting_wallet_name,
                            "created_at": str(test_created_at),
                        }
                    ),
                ),
            ]
            mock_wallet_record.query = AsyncMock()
            mock_wallet_record.query.return_value = wallets

            await test_module.wallets_list(self.request)
            mock_response.assert_called_once_with(
                {
                    "results": [
                        {
                            "group_id": test_group_id,
                            "wallet_id": test_wallet_id,
                            "created_at": str(test_created_at),
                            "settings": dict_setting_wallet_name,
                        }
                    ]
                }
            )

    async def test_wallet_create_tenant_settings(self):
        body = {
            "wallet_name": "test",
            "default_label": "test_label",
            "wallet_type": "askar",
            "wallet_key": "test",
            "key_management_mode": "managed",
            "wallet_webhook_urls": [],
            "wallet_dispatch_type": "base",
            "extra_settings": {
                "ACAPY_LOG_LEVEL": "INFO",
                "ACAPY_INVITE_PUBLIC": True,
                "ACAPY_PUBLIC_INVITES": True,
            },
        }
        self.request.json = AsyncMock(return_value=body)

        test_module.attempt_auto_author_with_endorser_setup = AsyncMock()

        with patch.object(test_module.web, "json_response") as mock_response:
            wallet_mock = MagicMock(
                serialize=MagicMock(
                    return_value={
                        "wallet_id": "test",
                        "settings": {},
                        "key_management_mode": body["key_management_mode"],
                    }
                )
            )  # wallet_record
            self.mock_multitenant_mgr.create_wallet = AsyncMock(
                return_value=wallet_mock
            )

            self.mock_multitenant_mgr.create_auth_token = AsyncMock(
                return_value="test_token"
            )
            self.mock_multitenant_mgr.get_wallet_profile = AsyncMock(
                return_value=MagicMock()
            )

            await test_module.wallet_create(self.request)

            self.mock_multitenant_mgr.create_wallet.assert_called_once_with(
                {
                    "wallet.name": body["wallet_name"],
                    "wallet.type": body["wallet_type"],
                    "wallet.key": body["wallet_key"],
                    "wallet.webhook_urls": body["wallet_webhook_urls"],
                    "wallet.dispatch_type": body["wallet_dispatch_type"],
                    "log.level": "INFO",
                    "debug.invite_public": True,
                    "public_invites": True,
                },
                body["key_management_mode"],
            )
            self.mock_multitenant_mgr.create_auth_token.assert_called_once_with(
                wallet_mock, body["wallet_key"]
            )
            mock_response.assert_called_once_with(
                {**test_module.format_wallet_record(wallet_mock), "token": "test_token"}
            )
            assert self.mock_multitenant_mgr.get_wallet_profile.called
            assert test_module.attempt_auto_author_with_endorser_setup.called

    async def test_wallet_create_wallet_type_different_from_base_wallet_raises_403(
        self,
    ):
        body = {
            "wallet_name": "test",
            "default_label": "test_label",
            "wallet_type": "askar",
            "wallet_key": "test",
            "key_management_mode": "managed",
            "wallet_webhook_urls": [],
            "wallet_dispatch_type": "base",
        }
        wallet_mock = MagicMock(
            group_id=test_group_id,
            serialize=MagicMock(
                return_value={
                    "wallet_id": "test",
                    "settings": {},
                    "key_management_mode": body["key_management_mode"],
                }
            ),
        )
        # wallet_record
        self.mock_multitenant_mgr.create_wallet = AsyncMock(return_value=wallet_mock)

        self.mock_multitenant_mgr.create_auth_token = AsyncMock(
            return_value="test_token"
        )
        self.mock_multitenant_mgr.get_wallet_profile = AsyncMock(
            return_value=MagicMock()
        )
        self.request.json = AsyncMock(return_value=body)

        await test_module.wallet_create(self.request)

        body["wallet_type"] = "askar-anoncreds"
        with self.assertRaises(test_module.web.HTTPForbidden):
            await test_module.wallet_create(self.request)

        body["wallet_type"] = "indy"
        with self.assertRaises(test_module.web.HTTPForbidden):
            await test_module.wallet_create(self.request)

        body["wallet_type"] = "in_memory"
        with self.assertRaises(test_module.web.HTTPForbidden):
            await test_module.wallet_create(self.request)

    async def test_wallet_create(self):
        body = {
            "wallet_name": test_wallet_name,
            "default_label": test_label,
            "wallet_type": "askar",
            "wallet_key": test_key,
            "key_management_mode": "managed",
            "wallet_webhook_urls": [],
            "wallet_dispatch_type": "base",
        }
        self.request.json = AsyncMock(return_value=body)
        test_module.attempt_auto_author_with_endorser_setup = AsyncMock()

        with patch.object(test_module.web, "json_response") as mock_response:
            wallet_mock = MagicMock(
                serialize=MagicMock(
                    return_value={
                        "wallet_id": test_wallet_id,
                        "settings": {},
                        "key_management_mode": body["key_management_mode"],
                    }
                )
            )  # wallet_record
            self.mock_multitenant_mgr.create_wallet = AsyncMock(
                return_value=wallet_mock
            )

            self.mock_multitenant_mgr.create_auth_token = AsyncMock(
                return_value="test_token"
            )
            self.mock_multitenant_mgr.get_wallet_profile = AsyncMock(
                return_value=MagicMock()
            )

            await test_module.wallet_create(self.request)

            self.mock_multitenant_mgr.create_wallet.assert_called_once_with(
                {
                    setting_wallet_name: body["wallet_name"],
                    "wallet.type": body["wallet_type"],
                    setting_wallet_key: body["wallet_key"],
                    "wallet.webhook_urls": body["wallet_webhook_urls"],
                    "wallet.dispatch_type": body["wallet_dispatch_type"],
                },
                body["key_management_mode"],
            )
            self.mock_multitenant_mgr.create_auth_token.assert_called_once_with(
                wallet_mock, body["wallet_key"]
            )
            mock_response.assert_called_once_with(
                {**test_module.format_wallet_record(wallet_mock), "token": test_token}
            )
            assert self.mock_multitenant_mgr.get_wallet_profile.called
            assert test_module.attempt_auto_author_with_endorser_setup.called

    async def test_wallet_create_x(self):
        body = {}
        self.request.json = AsyncMock(return_value=body)

        self.mock_multitenant_mgr.create_wallet.side_effect = MultitenantManagerError()
        with self.assertRaises(test_module.web.HTTPBadRequest):
            await test_module.wallet_create(self.request)

    async def test_wallet_create_schema_validation_fails_indy_no_name_key(self):
        incorrect_body = {"wallet_type": "indy"}

        with self.assertRaises(ValidationError):
            schema = test_module.CreateWalletRequestSchema()
            schema.validate_fields(incorrect_body)

    async def test_wallet_create_optional_default_fields(self):
        body = {
            "wallet_name": test_wallet_name,
            "wallet_key": test_key,
            "wallet_key_derivation": "ARGON2I_MOD",
            "wallet_webhook_urls": [],
            "wallet_dispatch_type": "base",
            "label": test_label,
            "image_url": test_image_url,
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response"):
            self.mock_multitenant_mgr.create_wallet = AsyncMock(
                return_value=MagicMock()
            )
            self.mock_multitenant_mgr.create_auth_token = AsyncMock()
            self.mock_multitenant_mgr.get_wallet_profile = AsyncMock(
                return_value=MagicMock()
            )

            await test_module.wallet_create(self.request)
            self.mock_multitenant_mgr.create_wallet.assert_called_once_with(
                {
                    setting_wallet_name: body["wallet_name"],
                    "wallet.type": "askar",
                    setting_wallet_key: body["wallet_key"],
                    "default_label": body["label"],
                    "image_url": body["image_url"],
                    "wallet.webhook_urls": body["wallet_webhook_urls"],
                    "wallet.dispatch_type": body["wallet_dispatch_type"],
                    "wallet.key_derivation_method": body["wallet_key_derivation"],
                },
                WalletRecord.MODE_MANAGED,
            )
            assert self.mock_multitenant_mgr.get_wallet_profile.called

    async def test_wallet_create_raw_key_derivation(self):
        body = {
            "wallet_name": test_wallet_name,
            "wallet_key": test_key,
            "wallet_key_derivation": "RAW",
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response"):
            self.mock_multitenant_mgr.create_wallet = AsyncMock(
                return_value=MagicMock()
            )
            self.mock_multitenant_mgr.create_auth_token = AsyncMock()
            self.mock_multitenant_mgr.get_wallet_profile = AsyncMock(
                return_value=MagicMock()
            )

            await test_module.wallet_create(self.request)
            self.mock_multitenant_mgr.create_wallet.assert_called_once_with(
                {
                    "wallet.type": "askar",
                    setting_wallet_name: body["wallet_name"],
                    setting_wallet_key: body["wallet_key"],
                    "wallet.key_derivation_method": body["wallet_key_derivation"],
                    "wallet.webhook_urls": [],
                    "wallet.dispatch_type": "base",
                },
                WalletRecord.MODE_MANAGED,
            )
            assert self.mock_multitenant_mgr.get_wallet_profile.called

    async def test_wallet_update_tenant_settings(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {
            "wallet_webhook_urls": ["test-webhook-url"],
            "wallet_dispatch_type": "default",
            "label": test_label,
            "image_url": test_image_url,
            "extra_settings": {
                "ACAPY_LOG_LEVEL": "INFO",
                "ACAPY_INVITE_PUBLIC": True,
                "ACAPY_PUBLIC_INVITES": True,
            },
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response") as mock_response:
            settings = {
                "wallet.webhook_urls": body["wallet_webhook_urls"],
                "wallet.dispatch_type": body["wallet_dispatch_type"],
                "default_label": body["label"],
                "image_url": body["image_url"],
                "log.level": "INFO",
                "debug.invite_public": True,
                "public_invites": True,
            }
            wallet_mock = MagicMock(
                group_id=test_group_id,
                serialize=MagicMock(
                    return_value={
                        "wallet_id": test_wallet_id,
                        "settings": settings,
                    }
                ),
            )
            self.mock_multitenant_mgr.update_wallet = AsyncMock(
                return_value=wallet_mock
            )

            await test_module.wallet_update(self.request)

            self.mock_multitenant_mgr.update_wallet.assert_called_once_with(
                test_wallet_id,
                settings,
            )
            mock_response.assert_called_once_with(
                {
                    "wallet_id": test_wallet_id,
                    "settings": settings,
                    "group_id": test_group_id,
                }
            )

    async def test_wallet_update(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {
            "wallet_webhook_urls": ["test-webhook-url"],
            "wallet_dispatch_type": "default",
            "label": test_label,
            "image_url": test_image_url,
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response") as mock_response:
            settings = {
                "wallet.webhook_urls": body["wallet_webhook_urls"],
                "wallet.dispatch_type": body["wallet_dispatch_type"],
                "default_label": body["label"],
                "image_url": body["image_url"],
            }
            wallet_mock = MagicMock(
                group_id=test_group_id,
                save=AsyncMock(),
                serialize=MagicMock(
                    return_value={
                        "wallet_id": test_wallet_id,
                        "settings": settings,
                    }
                ),
            )
            self.mock_multitenant_mgr.update_wallet = AsyncMock(
                return_value=wallet_mock
            )

            await test_module.wallet_update(self.request)

            self.mock_multitenant_mgr.update_wallet.assert_called_once_with(
                test_wallet_id,
                settings,
            )
            mock_response.assert_called_once_with(
                {
                    "wallet_id": test_wallet_id,
                    "settings": settings,
                    "group_id": test_group_id,
                }
            )

    async def test_wallet_update_no_wallet_webhook_urls(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {
            "label": test_label,
            "image_url": test_image_url,
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response") as mock_response:
            settings = {
                "default_label": body["label"],
                "image_url": body["image_url"],
            }
            wallet_mock = MagicMock(
                group_id=test_group_id,
                save=AsyncMock(),
                serialize=MagicMock(
                    return_value={
                        "wallet_id": test_wallet_id,
                        "settings": settings,
                    }
                ),
            )
            self.mock_multitenant_mgr.update_wallet = AsyncMock(
                return_value=wallet_mock
            )

            await test_module.wallet_update(self.request)

            self.mock_multitenant_mgr.update_wallet.assert_called_once_with(
                test_wallet_id,
                settings,
            )
            mock_response.assert_called_once_with(
                {
                    "wallet_id": test_wallet_id,
                    "settings": settings,
                    "group_id": test_group_id,
                }
            )

    async def test_wallet_update_empty_wallet_webhook_urls(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {
            "wallet_webhook_urls": [],
            "label": test_label,
            "image_url": test_image_url,
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response") as mock_response:
            settings = {
                "wallet.webhook_urls": [],
                "wallet.dispatch_type": "base",
                "default_label": body["label"],
                "image_url": body["image_url"],
            }
            wallet_mock = MagicMock(
                group_id=test_group_id,
                save=AsyncMock(),
                serialize=MagicMock(
                    return_value={
                        "wallet_id": test_wallet_id,
                        "settings": settings,
                    }
                ),
            )
            self.mock_multitenant_mgr.update_wallet = AsyncMock(
                return_value=wallet_mock
            )

            await test_module.wallet_update(self.request)

            self.mock_multitenant_mgr.update_wallet.assert_called_once_with(
                test_wallet_id,
                settings,
            )
            mock_response.assert_called_once_with(
                {
                    "wallet_id": test_wallet_id,
                    "settings": settings,
                    "group_id": test_group_id,
                }
            )

    async def test_wallet_update_wallet_settings_x(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {
            "wallet_webhook_urls": ["test-webhook-url"],
            "label": test_label,
            "image_url": test_image_url,
        }
        self.request.json = AsyncMock(return_value=body)

        with patch.object(test_module.web, "json_response"):
            self.mock_multitenant_mgr.update_wallet = AsyncMock(
                side_effect=test_module.WalletSettingsError("bad settings")
            )

            with self.assertRaises(test_module.web.HTTPBadRequest) as context:
                await test_module.wallet_update(self.request)
            assert "bad settings" in str(context.exception)

    async def test_wallet_update_no_params(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {}
        self.request.json = AsyncMock(return_value=body)

        with self.assertRaises(test_module.web.HTTPBadRequest):
            await test_module.wallet_update(self.request)

    async def test_wallet_update_not_found(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        body = {"label": test_label}
        self.request.json = AsyncMock(return_value=body)
        self.mock_multitenant_mgr.update_wallet = AsyncMock(
            side_effect=StorageNotFoundError()
        )

        with self.assertRaises(test_module.web.HTTPNotFound):
            await test_module.wallet_update(self.request)

    async def test_wallet_get(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        mock_wallet_record = MagicMock(group_id=test_group_id)
        mock_wallet_record.serialize.return_value = dict_wallet_id_no_settings

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id, patch.object(
            test_module.web, "json_response"
        ) as mock_response:
            mock_wallet_record_retrieve_by_id.return_value = mock_wallet_record

            await test_module.wallet_get(self.request)
            mock_response.assert_called_once_with(
                {"settings": {}, "wallet_id": test_wallet_id, "group_id": test_group_id}
            )

    async def test_wallet_get_not_found(self):
        self.request.match_info = {"wallet_id": test_wallet_id}

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id:
            mock_wallet_record_retrieve_by_id.side_effect = StorageNotFoundError()

            with self.assertRaises(test_module.web.HTTPNotFound):
                await test_module.wallet_get(self.request)

    async def test_wallet_get_x(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        mock_wallet_record = MagicMock()
        mock_wallet_record.serialize.side_effect = test_module.BaseModelError()

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id:
            mock_wallet_record_retrieve_by_id.return_value = mock_wallet_record

            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.wallet_get(self.request)

    async def test_wallet_create_token_managed(self):
        self.request.has_body = False
        self.request.match_info = {"wallet_id": test_wallet_id}
        mock_wallet_record = MagicMock()
        mock_wallet_record.serialize.return_value = dict_wallet_id_no_settings

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id, patch.object(
            test_module.web, "json_response"
        ) as mock_response:
            mock_wallet_record_retrieve_by_id.return_value = mock_wallet_record

            self.mock_multitenant_mgr.create_auth_token = AsyncMock(
                return_value=test_token
            )

            await test_module.wallet_create_token(self.request)

            self.mock_multitenant_mgr.create_auth_token.assert_called_once_with(
                mock_wallet_record, None
            )
            mock_response.assert_called_once_with({"token": test_token})

    async def test_wallet_create_token_unmanaged(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        self.request.json = AsyncMock(return_value=dict_wallet_key)
        mock_wallet_record = MagicMock()
        mock_wallet_record.serialize.return_value = dict_wallet_id_no_settings

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id, patch.object(
            test_module.web, "json_response"
        ) as mock_response:
            mock_wallet_record_retrieve_by_id.return_value = mock_wallet_record

            self.mock_multitenant_mgr.create_auth_token = AsyncMock(
                return_value=test_token
            )

            await test_module.wallet_create_token(self.request)

            self.mock_multitenant_mgr.create_auth_token.assert_called_once_with(
                mock_wallet_record, test_key
            )
            mock_response.assert_called_once_with({"token": test_token})

    async def test_wallet_create_token_managed_wallet_key_provided_throws(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        self.request.json = AsyncMock(return_value=dict_wallet_key)
        mock_wallet_record = MagicMock()
        mock_wallet_record.serialize.return_value = dict_wallet_id_no_settings
        mock_wallet_record.requires_external_key = False

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id:
            mock_wallet_record_retrieve_by_id.return_value = mock_wallet_record

            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.wallet_create_token(self.request)

    async def test_wallet_create_token_x(self):
        self.request.has_body = False
        self.request.match_info = {"wallet_id": test_wallet_id}

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id:
            mock_wallet_record_retrieve_by_id.return_value = MagicMock()

            with self.assertRaises(test_module.web.HTTPUnauthorized):
                mock_wallet_record_retrieve_by_id.side_effect = WalletKeyMissingError()
                await test_module.wallet_create_token(self.request)

            with self.assertRaises(test_module.web.HTTPNotFound):
                mock_wallet_record_retrieve_by_id.side_effect = (
                    test_module.StorageNotFoundError()
                )
                await test_module.wallet_create_token(self.request)

    async def test_wallet_remove_managed(self):
        self.request.has_body = False
        self.request.match_info = {"wallet_id": test_wallet_id}

        with patch.object(
            test_module.web, "json_response"
        ) as mock_response, patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ):
            self.mock_multitenant_mgr.remove_wallet = AsyncMock()

            result = await test_module.wallet_remove(self.request)

            self.mock_multitenant_mgr.remove_wallet.assert_called_once_with(
                test_wallet_id, None
            )
            mock_response.assert_called_once_with({})
            assert result == mock_response.return_value

    async def test_wallet_remove_unmanaged(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        self.request.json = AsyncMock(return_value=dict_wallet_key)

        with patch.object(
            test_module.web, "json_response"
        ) as mock_response, patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ):
            self.mock_multitenant_mgr.remove_wallet = AsyncMock()

            result = await test_module.wallet_remove(self.request)

            self.mock_multitenant_mgr.remove_wallet.assert_called_once_with(
                test_wallet_id, test_key
            )
            mock_response.assert_called_once_with({})
            assert result == mock_response.return_value

    async def test_wallet_remove_managed_wallet_key_provided_throws(self):
        self.request.match_info = {"wallet_id": test_wallet_id}
        self.request.json = AsyncMock(return_value=dict_wallet_key)

        mock_wallet_record = MagicMock()
        mock_wallet_record.requires_external_key = False

        with patch.object(
            test_module.WalletRecord, "retrieve_by_id", AsyncMock()
        ) as mock_wallet_record_retrieve_by_id:
            mock_wallet_record_retrieve_by_id.return_value = mock_wallet_record

            with self.assertRaises(test_module.web.HTTPBadRequest):
                await test_module.wallet_remove(self.request)

    async def test_wallet_remove_x(self):
        self.request.has_body = False
        self.request.match_info = {"wallet_id": test_wallet_id}

        self.mock_multitenant_mgr.remove_wallet = AsyncMock()

        with patch.object(test_module.WalletRecord, "retrieve_by_id", AsyncMock()):
            with self.assertRaises(test_module.web.HTTPUnauthorized):
                self.mock_multitenant_mgr.remove_wallet.side_effect = (
                    WalletKeyMissingError()
                )
                await test_module.wallet_remove(self.request)

            with self.assertRaises(test_module.web.HTTPNotFound):
                self.mock_multitenant_mgr.remove_wallet.side_effect = (
                    test_module.StorageNotFoundError()
                )
                await test_module.wallet_remove(self.request)

    async def test_register(self):
        mock_app = MagicMock()
        mock_app.add_routes = MagicMock()

        await test_module.register(mock_app)
        mock_app.add_routes.assert_called_once()

    async def test_post_process_routes(self):
        mock_app = MagicMock(_state={"swagger_dict": {}})
        test_module.post_process_routes(mock_app)
        assert "tags" in mock_app._state["swagger_dict"]
