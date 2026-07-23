from __future__ import annotations

import unittest
from pathlib import Path

from app.version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


class CatalogPerformanceAssetTests(unittest.TestCase):
    def test_performance_script_is_loaded_before_media_wrapper(self) -> None:
        template = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
        performance = f'/static/catalog-performance.js?v={APP_VERSION}'
        media = f'/static/media-ui.js?v={APP_VERSION}'
        self.assertIn(performance, template)
        self.assertIn(media, template)
        self.assertLess(template.index(performance), template.index(media))

    def test_catalog_is_batched_and_images_are_viewport_deferred(self) -> None:
        source = (ROOT / "app/static/catalog-performance.js").read_text(encoding="utf-8")
        self.assertIn("const PAGE_SIZE = 72", source)
        self.assertIn("IntersectionObserver", source)
        self.assertIn("image.dataset.src = url.href", source)
        self.assertIn("loadContent = async function loadContentBatched", source)
        self.assertIn("Mehr anzeigen", source)
        self.assertIn("window.cancelDeferredCardImages", source)

    def test_catalog_renderer_uses_proxy_and_avoids_html_injection(self) -> None:
        source = (ROOT / "app/static/catalog-performance.js").read_text(encoding="utf-8")
        self.assertIn("item.image_proxy || item.image || imageOf(item)", source)
        self.assertIn("title.textContent = titleOf(item)", source)
        self.assertNotIn("card.innerHTML", source)


if __name__ == "__main__":
    unittest.main()
