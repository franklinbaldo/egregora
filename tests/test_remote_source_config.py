import pytest

from egregora.config import PipelineConfig, RemoteSourceConfig


def test_remote_source_secret_handling():
    url = "https://drive.google.com/uc?id=secret"
    config = PipelineConfig.with_defaults(remote_source={"gdrive_url": url})

    secret = config.remote_source.gdrive_url
    assert secret is not None
    assert config.remote_source.get_gdrive_url() == url
    # Secret should be masked when converted to string or repr
    assert url not in str(secret)
    assert url not in repr(secret)

    safe = config.safe_dict()
    assert safe["remote_source"]["gdrive_url"] == str(secret)
    assert url not in safe["remote_source"]["gdrive_url"]

    # repr of config should not leak the URL
    assert url not in repr(config)


def test_remote_source_requires_https():
    with pytest.raises(ValueError):
        RemoteSourceConfig(gdrive_url="http://example.com/file.zip")

    # Empty strings should be treated as not configured
    config = RemoteSourceConfig(gdrive_url="   ")
    assert config.gdrive_url is None
