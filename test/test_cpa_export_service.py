import base64
import json
import unittest
import zipfile
from io import BytesIO


def jwt_with_payload(payload: dict) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none'})}.{encode(payload)}.signature"


class CpaExportServiceTests(unittest.TestCase):
    def test_build_cpa_payload_matches_single_file_shape(self) -> None:
        from services.cpa_export_service import build_cpa_payload

        token = jwt_with_payload({"exp": 1779622898, "iat": 1778758898})
        payload = build_cpa_payload(
            {
                "access_token": token,
                "email": "deandrea.northey@outlook.com",
                "user_id": "user-example",
                "status": "禁用",
                "refresh_token": "rt-example",
                "id_token": "id-example",
            }
        )

        self.assertEqual(payload["access_token"], token)
        self.assertEqual(payload["refresh_token"], "rt-example")
        self.assertEqual(payload["id_token"], "id-example")
        self.assertEqual(payload["email"], "deandrea.northey@outlook.com")
        self.assertEqual(payload["account_id"], "user-example")
        self.assertTrue(payload["disabled"])
        self.assertEqual(payload["type"], "codex")
        self.assertTrue(payload["expired"].startswith("2026-05-24T"))
        self.assertTrue(payload["last_refresh"].startswith("2026-05-14T"))

    def test_build_cpa_zip_writes_email_named_json_files(self) -> None:
        from services.cpa_export_service import build_cpa_zip

        payload = build_cpa_zip(
            [
                {"access_token": "token-one", "email": "one@example.com", "status": "正常"},
                {"access_token": "token-two", "email": "two@example.com", "status": "异常"},
            ]
        )

        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            names = sorted(archive.namelist())
            self.assertEqual(names, ["one@example.com.json", "two@example.com.json"])
            first = json.loads(archive.read("one@example.com.json").decode("utf-8"))
            second = json.loads(archive.read("two@example.com.json").decode("utf-8"))

        self.assertEqual(first["access_token"], "token-one")
        self.assertFalse(first["disabled"])
        self.assertTrue(second["disabled"])


if __name__ == "__main__":
    unittest.main()
