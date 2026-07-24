"""LDAP authentication module."""

import logging

import ldap
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import User

logger = logging.getLogger(__name__)


class LDAPConfig(BaseSettings):
    """LDAP configuration settings."""

    ldap_server: str = ""
    ldap_base_dn: str = ""
    ldap_user_dn: str = ""
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    ldap_use_ssl: bool = False
    ldap_use_active_directory: bool = False
    ldap_ad_domain: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


class LDAPAuthenticator:
    """LDAP authenticator class."""

    def __init__(self, config: LDAPConfig):
        """Initialize LDAP authenticator.

        Args:
            config: LDAP configuration
        """
        self.config = config

    def authenticate(self, username: str, password: str) -> User | None:  # NOSONAR python:S3776
        """Authenticate user against LDAP server.

        Args:
            username: Username to authenticate
            password: Password for authentication

        Returns:
            User object if authentication successful, None otherwise

        Raises:
            Exception: If LDAP connection or authentication fails
        """
        ldap_client = None
        try:
            ldap_client = ldap.initialize(self.config.ldap_server)
            ldap_client.set_option(ldap.OPT_REFERRALS, 0)
            ldap_client.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

            if self.config.ldap_use_ssl:
                ldap_client.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
                ldap_client.start_tls_s()

            if self.config.ldap_use_active_directory:
                if self.config.ldap_ad_domain:
                    user_dn = f"{username}@{self.config.ldap_ad_domain}"
                else:
                    user_dn = f"{username}"
                search_filter = f"(sAMAccountName={username})"
                attributes = ["cn", "mail", "sAMAccountName", "userPrincipalName"]
            else:
                user_dn = f"uid={username},{self.config.ldap_user_dn}"
                search_filter = f"(uid={username})"
                attributes = ["cn", "mail", "uid"]

            ldap_client.simple_bind_s(user_dn, password)

            result = ldap_client.search_s(self.config.ldap_user_dn, ldap.SCOPE_SUBTREE, search_filter, attributes)

            if result:
                _dn, attrs = result[0]
                email = attrs.get("mail", [b""])[0].decode("utf-8") if "mail" in attrs else ""
                full_name = attrs.get("cn", [b""])[0].decode("utf-8") if "cn" in attrs else ""

                logger.info(f"Successfully authenticated user: {username}")
                return User(username=username, email=email, full_name=full_name)

            logger.warning(f"User not found in LDAP: {username}")
            return None

        except ldap.INVALID_CREDENTIALS:
            logger.warning(f"Invalid credentials for user: {username}")
            return None
        except ldap.SERVER_DOWN:
            logger.error(f"LDAP server is down: {self.config.ldap_server}")
            raise Exception("LDAP server is unavailable") from None
        except Exception as e:
            logger.error(f"LDAP authentication error for user {username}: {e!s}")
            raise Exception(f"LDAP authentication error: {e!s}") from e
        finally:
            if ldap_client:
                try:
                    ldap_client.unbind_s()
                except Exception as e:
                    logger.error(f"Error unbinding LDAP connection: {e!s}")

    def verify_connection(self) -> bool:
        """Verify LDAP server connection.

        Returns:
            True if connection successful, False otherwise
        """
        ldap_client = None
        try:
            ldap_client = ldap.initialize(self.config.ldap_server)
            ldap_client.set_option(ldap.OPT_REFERRALS, 0)
            ldap_client.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

            if self.config.ldap_use_ssl:
                ldap_client.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
                ldap_client.start_tls_s()

            ldap_client.simple_bind_s(self.config.ldap_bind_dn, self.config.ldap_bind_password)
            logger.info("LDAP connection verified successfully")
            return True

        except Exception as e:
            logger.error(f"LDAP connection verification failed: {e!s}")
            return False
        finally:
            if ldap_client:
                try:
                    ldap_client.unbind_s()
                except Exception as e:
                    logger.error(f"Error unbinding LDAP connection: {e!s}")
