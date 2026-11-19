"""Register identity provider adapters selected by configuration. No tenant values are defaulted here."""
from asaa_identity.memory import InMemoryIdentityProvider
from asaa_identity.provider import register_provider
from asaa_identity.keycloak import KeycloakClient, KeycloakIdentityProvider
from asaa_identity.scim import ScimClient, ScimIdentityProvider


def register_configured_providers(settings) -> None:
    if settings.identity_provider == "memory" and settings.environment != "production":
        register_provider("memory", InMemoryIdentityProvider)
    if settings.identity_provider == "scim":
        if not settings.scim_base_url or not settings.scim_bearer_token:
            raise ValueError("ASAA_AP_SCIM_BASE_URL and ASAA_AP_SCIM_BEARER_TOKEN are required for the scim provider")
        register_provider("scim", lambda: ScimIdentityProvider(
            ScimClient(settings.scim_base_url, settings.scim_bearer_token), group_prefix=settings.scim_group_prefix))
    if settings.identity_provider == "keycloak":
        if not settings.keycloak_url or settings.keycloak_client_secret is None:
            raise ValueError("ASAA_IDENTITY_KEYCLOAK_URL and ASAA_IDENTITY_KEYCLOAK_CLIENT_SECRET are required for the keycloak provider")
        register_provider("keycloak", lambda: KeycloakIdentityProvider(
            KeycloakClient(settings.keycloak_url, settings.keycloak_realm, settings.keycloak_client_id,
                           settings.keycloak_client_secret.get_secret_value()),
            group_prefix=settings.scim_group_prefix, base_group=settings.keycloak_base_group,
            create_groups=settings.keycloak_create_groups, base_group_roles=settings.keycloak_base_group_roles))
