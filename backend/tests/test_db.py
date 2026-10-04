import ssl

import pytest

from app.core.db import _tidb_url_and_tls_context, make_engine


def test_tidb_console_tls_options_become_one_verified_context() -> None:
    url, context = _tidb_url_and_tls_context(
        "mysql+pymysql://prefix.root:password@gateway.example.com:4000/etika"
        "?charset=utf8mb4&ssl_ca=/etc/ssl/cert.pem"
        "&ssl_verify_cert=true&ssl_verify_identity=true"
    )

    assert url.query == {"charset": "utf8mb4"}
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_tidb_rejects_disabled_tls_verification() -> None:
    with pytest.raises(ValueError, match="certificate and hostname verification"):
        _tidb_url_and_tls_context(
            "mysql+pymysql://prefix.root:password@gateway.example.com:4000/etika"
            "?ssl_verify_cert=false&ssl_verify_identity=true"
        )


def test_mysql_engine_uses_pool_health_settings() -> None:
    engine = make_engine("mysql+pymysql://prefix.root:password@gateway.example.com:4000/etika")

    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 300
