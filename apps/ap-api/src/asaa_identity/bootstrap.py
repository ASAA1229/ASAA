"""Register identity provider adapters selected by configuration. No tenant values are defaulted here."""
from asaa_identity.memory import InMemoryIdentityProvider
from asaa_identity.provider import register_provider
from asaa_identity.scim import ScimClient, ScimIdentityProvider


def register_configured_providers(settings) -> None:
    if settings.identity_provider == "memory" and settings.environment != "production":
        register_provider("memory", InMemoryIdentityProvider)
    if settings.identity_provider == "scim":
        if not settings.scim_base_url or not settings.scim_bearer_token:
            raise ValueError("ASAA_AP_SCIM_BASE_URL and ASAA_AP_SCIM_BEARER_TOKEN are required for the scim provider")
        register_provider("scim", lambda: ScimIdentityProvider(
            ScimClient(settings.scim_base_url, settings.scim_bearer_token), group_prefix=settings.scim_group_prefix))
