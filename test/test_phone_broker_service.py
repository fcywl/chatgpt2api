from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PhoneBrokerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        from services import phone_broker_service

        phone_broker_service._country_cursor = 0
        phone_broker_service._runtime_country_blacklist.clear()

    def test_reserve_ignores_stale_reuse_fields_and_buys_fresh_number(self) -> None:
        from services.hero_sms_service import HeroSmsActivation
        from services.phone_broker_service import reserve_phone

        fake_client = mock.Mock()
        fake_client.get_number.return_value = HeroSmsActivation("387677530", "84901234000", "ACCESS_NUMBER:387677530:84901234000", country=6)

        with mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client):
            activation = reserve_phone(
                {
                    "api_key": "hero-key",
                    "service": "dr",
                    "country": 10,
                    "operator": "any",
                    "reuse_activation_id": "387677529",
                    "reuse_phone": "84901234889",
                    "auto_buy": False,
                    "max_price_usd": 0.03,
                }
            )

        self.assertEqual(activation.activation_id, "387677530")
        fake_client.get_number.assert_called_once_with(service="dr", country=6, operator="any", max_price=0.03)

    def test_reserve_requires_api_key(self) -> None:
        from services.phone_broker_service import reserve_phone

        with self.assertRaisesRegex(RuntimeError, "api_key 为空"):
            reserve_phone(
                {
                    "api_key": "",
                    "service": "dr",
                    "country": 10,
                    "operator": "any",
                    "auto_buy": False,
                    "max_price_usd": 0.03,
                }
            )

    def test_reserve_auto_buy_passes_max_price_to_hero_sms(self) -> None:
        from services.hero_sms_service import HeroSmsActivation
        from services.phone_broker_service import reserve_phone

        fake_client = mock.Mock()
        fake_client.get_number.return_value = HeroSmsActivation("387677529", "84901234889", "ACCESS_NUMBER:387677529:84901234889")

        with mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client):
            activation = reserve_phone(
                {
                    "api_key": "hero-key",
                    "service": "dr",
                    "country": 10,
                    "operator": "any",
                    "auto_buy": True,
                    "max_price_usd": 0.03,
                    "poll_interval": 1,
                }
            )

        self.assertEqual(activation.activation_id, "387677529")
        fake_client.get_number.assert_called_once_with(service="dr", country=6, operator="any", max_price=0.03)
        fake_client.close.assert_called_once()

    def test_reserve_round_robins_default_country_start(self) -> None:
        from services.hero_sms_service import HeroSmsActivation
        from services.phone_broker_service import reserve_phone

        fake_client = mock.Mock()
        fake_client.get_number.side_effect = [
            HeroSmsActivation("1", "1001", "ACCESS_NUMBER:1:1001", country=6),
            HeroSmsActivation("2", "1002", "ACCESS_NUMBER:2:1002", country=117),
            HeroSmsActivation("3", "1003", "ACCESS_NUMBER:3:1003", country=31),
        ]

        with mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client):
            for _ in range(3):
                reserve_phone({"api_key": "hero-key", "service": "dr", "operator": "any"})

        countries = [call.kwargs["country"] for call in fake_client.get_number.call_args_list]
        self.assertEqual(countries, [6, 117, 31])

    def test_reserve_min_price_filters_cheap_stock_and_uses_priced_operator(self) -> None:
        from services.hero_sms_service import HeroSmsActivation
        from services.phone_broker_service import reserve_phone

        fake_client = mock.Mock()
        fake_client.get_prices.return_value = {
            "6": {"any": {"cost": 0.01, "count": 9}},
            "117": {"virtual4": {"cost": 0.08, "count": 2}},
            "31": {"any": {"cost": 0.12, "count": 0}},
        }
        fake_client.get_number.return_value = HeroSmsActivation("9", "1009", "ACCESS_NUMBER:9:1009", country=117, operator="any")
        events: list[str] = []

        with mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client):
            activation = reserve_phone(
                {
                    "api_key": "hero-key",
                    "service": "dr",
                    "operator": "any",
                    "country_pool": [6, 117, 31],
                    "min_price_usd": 0.04,
                    "max_price_usd": 0.1,
                },
                on_event=events.append,
            )

        self.assertEqual(activation.activation_id, "9")
        fake_client.get_prices.assert_called_once_with(service="dr")
        fake_client.get_number.assert_called_once_with(service="dr", country=117, operator="any", max_price=0.1)
        self.assertTrue(any("价格过滤命中" in event for event in events))

    def test_reserve_min_price_refuses_to_blind_buy_when_no_priced_candidate(self) -> None:
        from services.phone_broker_service import reserve_phone

        fake_client = mock.Mock()
        fake_client.get_prices.return_value = {"6": {"any": {"cost": 0.01, "count": 9}}}

        with mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client):
            with self.assertRaisesRegex(RuntimeError, "无符合价格区间"):
                reserve_phone(
                    {
                        "api_key": "hero-key",
                        "service": "dr",
                        "country_pool": [6],
                        "min_price_usd": 0.04,
                        "max_price_usd": 0.1,
                    }
                )

        fake_client.get_number.assert_not_called()

    def test_reserve_prefers_learned_successful_country_under_budget(self) -> None:
        from services import hero_sms_country_reputation, phone_broker_service
        from services.hero_sms_service import HeroSmsActivation
        from services.phone_broker_service import reserve_phone

        with tempfile.TemporaryDirectory() as temp_dir:
            store = hero_sms_country_reputation.CountryReputationStore(Path(temp_dir) / "hero_sms_country_reputation.json")
            store.record_event(33, "fraud_guard", price=0.05)
            store.record_event(31, "cpa_success", price=0.05)
            fake_client = mock.Mock()
            fake_client.get_activation_offers.return_value = {
                "dr": {
                    "33": {"prices": {"default": 0.05}, "counts": {"total": 9000, "physical": 1500}},
                    "31": {"prices": {"default": 0.05}, "counts": {"total": 3500, "physical": 3400}},
                    "48": {"prices": {"default": 0.075}, "counts": {"total": 2900, "physical": 1100}},
                }
            }
            fake_client.get_number.return_value = HeroSmsActivation("31-ok", "10031", "ACCESS_NUMBER:31-ok:10031", country=31)

            with (
                mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client),
                mock.patch.object(phone_broker_service.country_reputation, "store", store),
            ):
                activation = reserve_phone(
                    {
                        "api_key": "hero-key",
                        "service": "dr",
                        "operator": "any",
                        "country_pool": [33, 31, 48],
                        "min_price_usd": 0.045,
                        "max_price_usd": 0.1,
                    }
                )

        self.assertEqual(activation.country, 31)
        self.assertEqual(activation.price, 0.05)
        fake_client.get_number.assert_called_once_with(service="dr", country=31, operator="any", max_price=0.1)

    def test_reserve_avoids_zero_physical_stock_when_priced_candidates_exist(self) -> None:
        from services.hero_sms_service import HeroSmsActivation
        from services.phone_broker_service import reserve_phone

        fake_client = mock.Mock()
        fake_client.get_activation_offers.return_value = {
            "dr": {
                "54": {"prices": {"default": 0.1}, "counts": {"total": 800, "physical": 0}},
                "40": {"prices": {"default": 0.09}, "counts": {"total": 3200, "physical": 2900}},
            }
        }
        fake_client.get_number.return_value = HeroSmsActivation("40-ok", "10040", "ACCESS_NUMBER:40-ok:10040", country=40)

        with mock.patch("services.phone_broker_service.HeroSmsClient", return_value=fake_client):
            activation = reserve_phone(
                {
                    "api_key": "hero-key",
                    "service": "dr",
                    "operator": "any",
                    "country_pool": [54, 40],
                    "min_price_usd": 0.045,
                    "max_price_usd": 0.1,
                }
            )

        self.assertEqual(activation.country, 40)
        fake_client.get_number.assert_called_once_with(service="dr", country=40, operator="any", max_price=0.1)


if __name__ == "__main__":
    unittest.main()
