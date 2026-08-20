from app.security import PrincipalKind, SecurityPrincipal


def test_account_continuity_namespace_ignores_untrusted_body_user() -> None:
    principal = SecurityPrincipal(kind=PrincipalKind.ACCOUNT, account_id="trusted-id")

    assert principal.continuity_namespace("account:spoofed") == "account:trusted-id"


def test_api_key_continuity_namespace_never_addresses_account_subject() -> None:
    principal = SecurityPrincipal(kind=PrincipalKind.LEGACY_API_KEY)

    assert principal.continuity_namespace("account:spoofed") == "legacy:account:spoofed"
    assert principal.continuity_namespace(None) == "legacy:qingxiaoda-gateway"
