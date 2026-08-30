from app.main import LIVE_ADVERTISING_ENABLED, META_READ_SYNC_ENABLED
from app.providers.meta_read import MetaReadClient


def test_live_advertising_defaults_off():
    assert LIVE_ADVERTISING_ENABLED is False


def test_meta_read_sync_defaults_off():
    assert META_READ_SYNC_ENABLED is False


def test_meta_adapter_exposes_no_write_methods():
    client = MetaReadClient()
    forbidden = {"create_campaign", "update_campaign", "activate_campaign", "delete_campaign", "post", "put", "patch", "delete"}
    assert forbidden.isdisjoint(set(dir(client)))
