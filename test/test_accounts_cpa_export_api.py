from __future__ import annotations

import json
import unittest
import zipfile
from io import BytesIO
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.accounts as accounts_module


AUTH_HEADERS = {"Authorization": "Bearer test-admin"}


class FakeAccountService:
    def list_accounts(self):
        return [
            {"access_token": "token-one", "email": "one@example.com", "status": "正常"},
            {"access_token": "token-two", "email": "two@example.com", "status": "异常"},
        ]


class AccountsCPAExportApiTests(unittest.TestCase):
    def setUp(self):
        self.service_patcher = mock.patch.object(accounts_module, "account_service", FakeAccountService())
        self.auth_patcher = mock.patch.object(accounts_module, "require_admin", lambda _authorization: {"role": "admin"})
        self.service_patcher.start()
        self.auth_patcher.start()
        self.addCleanup(self.service_patcher.stop)
        self.addCleanup(self.auth_patcher.stop)

        app = FastAPI()
        app.include_router(accounts_module.create_router())
        self.client = TestClient(app)

    def test_export_selected_accounts_as_cpa_zip(self):
        response = self.client.post(
            "/api/accounts/export/cpa",
            headers=AUTH_HEADERS,
            json={"access_tokens": ["token-two"]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/zip")
        self.assertIn("attachment; filename=", response.headers["content-disposition"])

        with zipfile.ZipFile(BytesIO(response.content), "r") as archive:
            self.assertEqual(archive.namelist(), ["two@example.com.json"])
            payload = json.loads(archive.read("two@example.com.json").decode("utf-8"))

        self.assertEqual(payload["access_token"], "token-two")
        self.assertEqual(payload["type"], "codex")
        self.assertTrue(payload["disabled"])

    def test_export_rejects_empty_selection(self):
        response = self.client.post(
            "/api/accounts/export/cpa",
            headers=AUTH_HEADERS,
            json={"access_tokens": ["missing-token"]},
        )

        self.assertEqual(response.status_code, 400, response.text)


if __name__ == "__main__":
    unittest.main()
