from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.config import Settings
from app.image_proxy import (
    _detected_media_type,
    _validate_target,
    attach_image_proxies,
    create_image_ticket,
    read_image_ticket,
)

ROOT = Path(__file__).resolve().parents[1]


def settings(portal_url: str = "http://192.168.178.4/stalker_portal") -> Settings:
    return Settings(
        portal_url=portal_url,
        portal_mac="00:1A:79:00:00:01",
        app_secret="test-secret-that-is-long-enough",
    )


def ticket_from_proxy_url(value: str) -> str:
    prefix = "/api/image?ticket="
    if not value.startswith(prefix):
        raise AssertionError(f"Kein Bild-Proxy: {value}")
    return value.removeprefix(prefix)


class ImageProxyTicketTests(unittest.TestCase):
    def test_listing_keeps_original_and_adds_same_origin_proxy(self) -> None:
        configured = settings()
        result = attach_image_proxies(
            [{"name": "Sender", "logo": "http://cdn.example/logo.png"}],
            configured,
        )
        item = result[0]
        self.assertEqual(item["logo"], "http://cdn.example/logo.png")
        ticket = ticket_from_proxy_url(item["image_proxy"])
        self.assertEqual(read_image_ticket(ticket, configured, now=1), "http://cdn.example/logo.png")

    def test_relative_portal_image_is_made_absolute(self) -> None:
        configured = settings()
        result = attach_image_proxies({"logo": "/logos/channel.png"}, configured)
        ticket = ticket_from_proxy_url(result["image_proxy"])
        self.assertEqual(
            read_image_ticket(ticket, configured, now=1),
            "http://192.168.178.4/logos/channel.png",
        )

    def test_ticket_is_bound_to_selected_portal(self) -> None:
        first = settings("http://192.168.178.4/portal")
        second = settings("http://192.168.178.5/portal")
        ticket = create_image_ticket("https://cdn.example/logo.png", first, now=1)
        with self.assertRaises(HTTPException) as raised:
            read_image_ticket(ticket, second, now=1)
        self.assertEqual(raised.exception.status_code, 403)

    def test_modified_ticket_is_rejected(self) -> None:
        configured = settings()
        ticket = create_image_ticket("https://cdn.example/logo.png", configured, now=1)
        payload, signature = ticket.split(".", 1)
        with self.assertRaises(HTTPException):
            read_image_ticket(f"{payload}x.{signature}", configured, now=1)


class ImageProxyNetworkTests(unittest.TestCase):
    def test_configured_private_portal_host_is_allowed(self) -> None:
        asyncio.run(_validate_target("http://192.168.178.4/logo.png", settings()))

    def test_other_private_targets_are_blocked(self) -> None:
        for target in ("http://127.0.0.1/logo.png", "http://10.0.0.2/logo.png"):
            with self.subTest(target=target):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(_validate_target(target, settings()))
                self.assertEqual(raised.exception.status_code, 403)

    def test_public_literal_ip_is_allowed(self) -> None:
        asyncio.run(_validate_target("https://1.1.1.1/logo.png", settings()))

    def test_html_and_svg_are_not_accepted_as_images(self) -> None:
        self.assertIsNone(_detected_media_type("text/html", b"<html></html>"))
        self.assertIsNone(_detected_media_type("image/svg+xml", b"<svg></svg>"))


class ImageProxyFrontendTests(unittest.TestCase):
    def test_secure_card_prefers_proxy_and_supports_stored_images(self) -> None:
        source = (ROOT / "app/static/card-security.js").read_text(encoding="utf-8")
        self.assertIn("item.image_proxy || item.image || imageOf(item)", source)
        self.assertNotIn("innerHTML", source)

    def test_server_requires_portal_for_image_proxy(self) -> None:
        source = (ROOT / "app/server.py").read_text(encoding="utf-8")
        self.assertIn('"/api/image"', source)
        self.assertIn("install_image_proxy(app)", source)

    def test_ticket_is_not_placed_in_logged_request_path(self) -> None:
        source = (ROOT / "app/image_proxy.py").read_text(encoding="utf-8")
        self.assertIn('app.add_api_route("/api/image", image_response', source)
        self.assertIn('f"/api/image?ticket=', source)
        self.assertNotIn('app.add_api_route("/api/image/{ticket}"', source)


if __name__ == "__main__":
    unittest.main()
