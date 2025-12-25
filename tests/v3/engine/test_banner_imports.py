"""Test imports for V3 Banner Engine."""

def test_banner_imports():
    """Verify that V3 Banner Engine modules import correctly."""
    from egregora_v3.engine.banner.generator import GeminiV3BannerGenerator
    from egregora_v3.engine.banner.feed_generator import FeedBannerGenerator

    assert GeminiV3BannerGenerator is not None
    assert FeedBannerGenerator is not None
