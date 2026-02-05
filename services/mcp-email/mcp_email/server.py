"""MCP Email Server - FastMail email sending via JMAP.

This MCP server provides email sending capabilities using the FastMail JMAP API.
It integrates with the TaskManager OAuth infrastructure for authentication.
"""

import html
import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import click
import httpx
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.middleware import NormalizePathMiddleware
from mcp_resource_framework.security import guard_tool
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

DEFAULT_SCOPE = ["read"]

load_dotenv()

# OAuth client credentials (for MCP OAuth flow)
CLIENT_ID = os.environ.get("TASKMANAGER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("TASKMANAGER_CLIENT_SECRET", "")
MCP_AUTH_SERVER = os.environ.get("MCP_AUTH_SERVER", "http://localhost:9000")

# FastMail configuration
FASTMAIL_API_TOKEN = os.environ.get("FASTMAIL_API_TOKEN")
ALLOWED_EMAIL_RECIPIENTS = os.environ.get("ALLOWED_EMAIL_RECIPIENTS", "")
ADMIN_EMAIL_ADDRESS = os.environ.get("ADMIN_EMAIL_ADDRESS", "")

# JMAP Constants
JMAP_SESSION_URL = "https://api.fastmail.com/jmap/session"
JMAP_CAPABILITIES = {
    "core": "urn:ietf:params:jmap:core",
    "mail": "urn:ietf:params:jmap:mail",
    "submission": "urn:ietf:params:jmap:submission",
}

# RFC 5322 compliant email regex (simplified but covers most valid cases)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9]"
    r"(?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

# Dangerous HTML patterns that should never be in legitimate email HTML
DANGEROUS_HTML_PATTERNS = [
    r"<script",
    r"</script",
    r"javascript:",
    r"vbscript:",
    r"on\w+\s*=",  # Event handlers like onclick=, onerror=
    r"<iframe",
    r"<object",
    r"<embed",
    r"<form",
    r"<input",
    r"<meta\s+http-equiv",
    r"expression\s*\(",  # CSS expression
    r"url\s*\(\s*['\"]?\s*data:",  # Data URLs in CSS
]


class JMAPClient:
    """JMAP client for FastMail API interactions."""

    def __init__(self, api_token: str):
        """Initialize JMAP client.

        Args:
            api_token: FastMail API token
        """
        self.api_token = api_token
        self._session: dict[str, Any] | None = None
        self._account_id: str | None = None
        self._api_url: str | None = None

    async def _ensure_session(self) -> None:
        """Ensure we have a valid JMAP session."""
        if self._session is not None:
            return

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                JMAP_SESSION_URL,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            self._session = response.json()

        assert self._session is not None
        accounts = self._session.get("accounts", {})
        primary_accounts = self._session.get("primaryAccounts", {})

        # Get the primary mail account
        mail_account_id = primary_accounts.get(JMAP_CAPABILITIES["mail"])
        if mail_account_id:
            self._account_id = mail_account_id
        elif accounts:
            self._account_id = next(iter(accounts.keys()))

        self._api_url = self._session.get("apiUrl")

        if not self._account_id or not self._api_url:
            raise ValueError("Could not determine FastMail account or API URL from session")

        logger.info(f"JMAP session established for account: {self._account_id}")

    async def _call(self, method_calls: list[list[Any]]) -> dict[str, Any]:
        """Make a JMAP API call.

        Args:
            method_calls: List of JMAP method calls in format [[method, args, id], ...]

        Returns:
            JMAP response with methodResponses
        """
        await self._ensure_session()
        assert self._api_url is not None

        request_body = {
            "using": list(JMAP_CAPABILITIES.values()),
            "methodCalls": method_calls,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._api_url,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            response.raise_for_status()
            return response.json()

    @property
    def account_id(self) -> str:
        """Get the account ID (requires session to be established)."""
        if not self._account_id:
            raise ValueError("Session not established. Call a method first.")
        return self._account_id


def _validate_email(email: str) -> bool:
    """Validate an email address format."""
    if not email or not isinstance(email, str):
        return False
    if len(email) > 254:
        return False
    local_part = email.rsplit("@", 1)[0] if "@" in email else ""
    if len(local_part) > 64:
        return False
    return EMAIL_REGEX.match(email) is not None


def _validate_email_list(emails: list[str]) -> tuple[bool, list[str]]:
    """Validate a list of email addresses."""
    invalid = [e for e in emails if not _validate_email(e)]
    return len(invalid) == 0, invalid


def _is_recipient_allowed(email: str, allowed_patterns: list[str]) -> bool:
    """Check if an email recipient is in the allowed list."""
    email_lower = email.lower()
    for pattern in allowed_patterns:
        pattern_lower = pattern.lower().strip()
        if pattern_lower.startswith("*@"):
            domain = pattern_lower[2:]
            if email_lower.endswith(f"@{domain}"):
                return True
        elif email_lower == pattern_lower:
            return True
    return False


def _get_allowed_recipients() -> list[str]:
    """Get the list of allowed email recipients from environment."""
    allowed = []

    if ADMIN_EMAIL_ADDRESS:
        allowed.append(ADMIN_EMAIL_ADDRESS)

    if ALLOWED_EMAIL_RECIPIENTS:
        patterns = [p.strip() for p in ALLOWED_EMAIL_RECIPIENTS.split(",")]
        allowed.extend(p for p in patterns if p)

    return allowed


def _sanitize_html(html_content: str) -> str:
    """Sanitize HTML content to prevent XSS in email clients."""
    content_lower = html_content.lower()
    for pattern in DANGEROUS_HTML_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            logger.warning(f"Dangerous HTML pattern detected: {pattern}")
            return html.escape(html_content)
    return html_content


def _handle_jmap_error(error: Exception, operation: str) -> dict[str, Any]:
    """Handle JMAP API errors with consistent error responses."""
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        logger.error(f"HTTP error {operation}: {error}")

        if status_code == 401:
            return {
                "status": "error",
                "error_type": "AuthenticationError",
                "status_code": status_code,
                "message": "Authentication failed. Check your FastMail API token.",
            }
        if status_code == 403:
            return {
                "status": "error",
                "error_type": "ForbiddenError",
                "status_code": status_code,
                "message": f"Access forbidden (HTTP {status_code})",
            }
        return {
            "status": "error",
            "error_type": "HTTPError",
            "status_code": status_code,
            "message": f"HTTP error: {status_code}",
        }

    logger.error(f"Error {operation}: {error}")
    error_type = type(error).__name__

    safe_messages = {
        "ValueError": "Invalid value provided",
        "TypeError": "Invalid type provided",
        "KeyError": "Missing required field",
        "ConnectionError": "Connection failed",
        "TimeoutError": "Request timed out",
        "RequestError": "Network request failed",
    }

    return {
        "status": "error",
        "error_type": error_type,
        "message": safe_messages.get(error_type, f"Operation failed: {operation}"),
    }


def create_resource_server(
    port: int,
    server_url: str,
    auth_server_url: str,
    auth_server_public_url: str,
    oauth_strict: bool,
) -> FastMCP:
    """Create MCP Email Server with token introspection."""

    token_verifier = IntrospectionTokenVerifier(
        introspection_endpoint=f"{auth_server_url}/introspect",
        server_url=str(server_url),
        validate_resource=oauth_strict,
    )

    parsed_url = urlparse(server_url)
    allowed_host = parsed_url.netloc

    debug_mode = os.getenv("DEBUG", "false").lower() == "true"

    app = FastMCP(
        name="FastMail MCP Server",
        instructions="MCP Server for sending emails via FastMail",
        port=port,
        debug=debug_mode,
        token_verifier=token_verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(auth_server_public_url),
            required_scopes=DEFAULT_SCOPE,
            resource_server_url=AnyHttpUrl(server_url),
        ),
        transport_security=TransportSecuritySettings(
            allowed_hosts=[allowed_host],
        ),
    )

    # OAuth discovery endpoints
    @app.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource_main(request: Request) -> JSONResponse:
        """OAuth 2.0 Protected Resource Metadata (RFC 9908)"""
        resource_url = str(server_url).rstrip("/")
        auth_server_url_no_slash = str(auth_server_public_url).rstrip("/")

        return JSONResponse(
            {
                "resource": resource_url,
                "authorization_servers": [auth_server_url_no_slash],
                "scopes_supported": DEFAULT_SCOPE,
                "bearer_methods_supported": ["header"],
            }
        )

    @app.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
    async def openid_configuration(request: Request) -> JSONResponse:
        """OpenID Connect Discovery"""
        if request.method == "OPTIONS":
            return JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        auth_base = str(auth_server_public_url).rstrip("/")
        return JSONResponse(
            {
                "issuer": auth_base,
                "authorization_endpoint": f"{auth_base}/authorize",
                "token_endpoint": f"{auth_base}/token",
                "registration_endpoint": f"{auth_base}/register",
                "introspection_endpoint": f"{auth_base}/introspect",
                "scopes_supported": DEFAULT_SCOPE,
                "response_types_supported": ["code"],
                "grant_types_supported": [
                    "authorization_code",
                    "refresh_token",
                    "urn:ietf:params:oauth:grant-type:device_code",
                ],
                "code_challenge_methods_supported": ["S256"],
            }
        )

    @app.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    async def oauth_authorization_server(request: Request) -> JSONResponse:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414)"""
        if request.method == "OPTIONS":
            return JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        auth_base = str(auth_server_public_url).rstrip("/")
        return JSONResponse(
            {
                "issuer": auth_base,
                "authorization_endpoint": f"{auth_base}/authorize",
                "token_endpoint": f"{auth_base}/token",
                "registration_endpoint": f"{auth_base}/register",
                "introspection_endpoint": f"{auth_base}/introspect",
                "scopes_supported": DEFAULT_SCOPE,
                "response_types_supported": ["code"],
                "grant_types_supported": [
                    "authorization_code",
                    "refresh_token",
                    "urn:ietf:params:oauth:grant-type:device_code",
                ],
                "code_challenge_methods_supported": ["S256"],
            }
        )

    @app.custom_route("/mcp/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource_mcp(request: Request) -> JSONResponse:
        """OAuth 2.0 Protected Resource Metadata at MCP path"""
        return await oauth_protected_resource_main(request)

    # ========== EMAIL TOOL ==========

    @app.tool()
    @guard_tool(input_params=["to", "subject", "body"], screen_output=True)
    async def send_email(
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        reply_to_email_id: str | None = None,
        is_html: bool = False,
        identity_email: str | None = None,
    ) -> str:
        """
        Send an email via FastMail.

        Creates and sends an email using JMAP EmailSubmission. Supports plain text
        or HTML body, CC/BCC recipients, and replying to existing emails.

        SECURITY: Recipients are validated against ALLOWED_EMAIL_RECIPIENTS environment
        variable. If not configured, only ADMIN_EMAIL_ADDRESS can receive emails.

        Args:
            to: List of recipient email addresses
            subject: Email subject line
            body: Email body content (plain text or HTML)
            cc: Optional list of CC recipients
            bcc: Optional list of BCC recipients
            reply_to_email_id: Optional email ID to reply to (sets In-Reply-To header)
            is_html: If True, body is treated as HTML (default: False for plain text).
                HTML content is sanitized to prevent XSS.
            identity_email: Optional email address to send from. Must match a configured
                identity in FastMail. If not specified, uses the primary identity.

        Returns:
            JSON string with status, email_id (on success), and message
        """
        logger.info(f"=== send_email called: to={to}, subject={subject[:50]}... ===")

        # Validate FastMail token is configured
        if not FASTMAIL_API_TOKEN:
            return json.dumps(
                {
                    "status": "error",
                    "message": "FASTMAIL_API_TOKEN environment variable is not configured.",
                }
            )

        # Validate required fields
        if not to:
            return json.dumps(
                {
                    "status": "error",
                    "message": "At least one recipient (to) is required",
                }
            )

        if not subject:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Subject is required",
                }
            )

        # Collect all recipients
        all_recipients = list(to)
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        # Validate email address formats
        valid, invalid_emails = _validate_email_list(all_recipients)
        if not valid:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Invalid email address format: {', '.join(invalid_emails)}",
                }
            )

        # Validate recipients against security allowlist
        allowed_patterns = _get_allowed_recipients()
        if not allowed_patterns:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Email sending is disabled. Configure ALLOWED_EMAIL_RECIPIENTS or "
                    "ADMIN_EMAIL_ADDRESS environment variable to enable.",
                }
            )

        disallowed = [r for r in all_recipients if not _is_recipient_allowed(r, allowed_patterns)]
        if disallowed:
            logger.warning(f"Blocked email to unauthorized recipients: {disallowed}")
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Recipients not in allowed list: {', '.join(disallowed)}. "
                    "Configure ALLOWED_EMAIL_RECIPIENTS to allow additional recipients.",
                }
            )

        # Sanitize HTML content if needed
        sanitized_body = _sanitize_html(body) if is_html else body

        try:
            client = JMAPClient(FASTMAIL_API_TOKEN)
            await client._ensure_session()

            # Resolve sender identity
            identity_response = await client._call(
                [["Identity/get", {"accountId": client.account_id}, "identity-get"]]
            )

            identity_result = identity_response.get("methodResponses", [[]])[0]
            if identity_result[0] == "error":
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Failed to get identity: {identity_result[1].get('description')}",
                    }
                )

            identities = identity_result[1].get("list", [])
            if not identities:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "No email identity found. Cannot send email.",
                    }
                )

            identity = None
            use_custom_from = False

            if identity_email:
                # First try exact match
                for ident in identities:
                    if ident.get("email", "").lower() == identity_email.lower():
                        identity = ident
                        break

                # If no exact match, try catch-all pattern (*@domain)
                if not identity:
                    requested_domain = identity_email.lower().split("@")[-1]
                    for ident in identities:
                        ident_email = ident.get("email", "").lower()
                        if ident_email.startswith("*@"):
                            catch_all_domain = ident_email[2:]
                            if catch_all_domain == requested_domain:
                                identity = ident
                                use_custom_from = True
                                break

                if not identity:
                    available = [i.get("email") for i in identities]
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"Identity '{identity_email}' not found. "
                            f"Available identities: {available}",
                        }
                    )
            else:
                identity = identities[0]

            identity_id = identity.get("id")
            if not identity_id:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Identity has no ID configured.",
                    }
                )

            from_name: str = identity.get("name", "")
            if use_custom_from and identity_email:
                from_address = identity_email
            else:
                ident_email = identity.get("email")
                if not ident_email:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": "Identity has no email address configured.",
                        }
                    )
                from_address = ident_email

            # Build email object
            email_create: dict[str, Any] = {
                "from": [{"email": from_address, "name": from_name}]
                if from_name
                else [{"email": from_address}],
                "to": [{"email": addr} for addr in to],
                "subject": subject,
            }

            if cc:
                email_create["cc"] = [{"email": addr} for addr in cc]
            if bcc:
                email_create["bcc"] = [{"email": addr} for addr in bcc]

            if is_html:
                email_create["htmlBody"] = [{"partId": "body", "type": "text/html"}]
            else:
                email_create["textBody"] = [{"partId": "body", "type": "text/plain"}]
            email_create["bodyValues"] = {
                "body": {"value": sanitized_body, "isEncodingProblem": False}
            }

            # Add reply threading if replying
            if reply_to_email_id:
                orig_response = await client._call(
                    [
                        [
                            "Email/get",
                            {
                                "accountId": client.account_id,
                                "ids": [reply_to_email_id],
                                "properties": ["messageId", "references", "threadId"],
                            },
                            "orig-get",
                        ]
                    ]
                )

                orig_result = orig_response.get("methodResponses", [[]])[0]
                if orig_result[0] == "Email/get":
                    orig_emails = orig_result[1].get("list", [])
                    if orig_emails:
                        orig = orig_emails[0]
                        message_ids = orig.get("messageId", [])
                        if message_ids:
                            email_create["inReplyTo"] = message_ids[0]
                            refs = list(orig.get("references", []))
                            refs.extend(message_ids)
                            email_create["references"] = refs

            # Get mailbox IDs
            mailbox_response = await client._call(
                [
                    [
                        "Mailbox/query",
                        {"accountId": client.account_id, "filter": {"role": "drafts"}},
                        "drafts-query",
                    ],
                    [
                        "Mailbox/query",
                        {"accountId": client.account_id, "filter": {"role": "sent"}},
                        "sent-query",
                    ],
                ]
            )

            drafts_mailbox_id = None
            sent_mailbox_id = None

            for resp in mailbox_response.get("methodResponses", []):
                if resp[0] == "Mailbox/query":
                    ids = resp[1].get("ids") or []
                    if resp[2] == "drafts-query" and ids:
                        drafts_mailbox_id = ids[0]
                    elif resp[2] == "sent-query" and ids:
                        sent_mailbox_id = ids[0]

            if not drafts_mailbox_id:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Could not find drafts mailbox",
                    }
                )
            if not sent_mailbox_id:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Could not find sent mailbox",
                    }
                )

            # Set mailbox and draft keyword
            email_create["mailboxIds"] = {drafts_mailbox_id: True}
            email_create["keywords"] = {"$draft": True}

            # Create and submit email
            response = await client._call(
                [
                    [
                        "Email/set",
                        {"accountId": client.account_id, "create": {"draft": email_create}},
                        "email-create",
                    ],
                    [
                        "EmailSubmission/set",
                        {
                            "accountId": client.account_id,
                            "create": {"send": {"identityId": identity_id, "emailId": "#draft"}},
                            "onSuccessUpdateEmail": {
                                "#send": {
                                    f"mailboxIds/{drafts_mailbox_id}": None,
                                    f"mailboxIds/{sent_mailbox_id}": True,
                                    "keywords/$draft": None,
                                    "keywords/$sent": True,
                                }
                            },
                        },
                        "email-submit",
                    ],
                ]
            )

            # Process response
            for resp in response.get("methodResponses", []):
                if resp[0] == "error":
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"JMAP error: {resp[1].get('description', 'Unknown error')}",
                        }
                    )

                if resp[0] == "Email/set":
                    not_created = resp[1].get("notCreated") or {}
                    if "draft" in not_created:
                        error = not_created["draft"]
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Failed to create email: "
                                f"{error.get('description', error.get('type'))}",
                            }
                        )

                if resp[0] == "EmailSubmission/set":
                    submission_result = resp[1]
                    not_created = submission_result.get("notCreated") or {}
                    if "send" in not_created:
                        error = not_created["send"]
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"Failed to send email: "
                                f"{error.get('description', error.get('type'))}",
                            }
                        )
                    created_send = (submission_result.get("created") or {}).get("send")
                    if created_send:
                        email_id = created_send.get("emailId")
                        logger.info(f"Email sent successfully: {email_id}")
                        return json.dumps(
                            {
                                "status": "success",
                                "email_id": email_id,
                                "message": f"Email sent successfully to {', '.join(to)}",
                                "from_address": from_address,
                            }
                        )

            return json.dumps(
                {
                    "status": "error",
                    "message": "Unexpected response from server",
                }
            )

        except Exception as e:
            result = _handle_jmap_error(e, "sending email")
            return json.dumps(result)

    return app


@click.command()
@click.option("--port", default=8002, help="Port to listen on")
@click.option(
    "--auth-server",
    default=MCP_AUTH_SERVER,
    help="Authorization Server URL (internal, for introspection)",
)
@click.option(
    "--auth-server-public-url",
    help="Public Authorization Server URL (for OAuth metadata). Defaults to --auth-server value",
)
@click.option(
    "--server-url",
    help="External server URL (for OAuth). Defaults to https://localhost:PORT",
)
@click.option(
    "--oauth-strict",
    is_flag=True,
    help="Enable RFC 8707 resource validation",
)
def main(
    port: int,
    auth_server: str,
    auth_server_public_url: str | None = None,
    server_url: str | None = None,
    oauth_strict: bool = False,
) -> int:
    """
    Run the FastMail MCP server.

    Args:
        port: Port to bind the server to
        auth_server: URL of the OAuth authorization server
        server_url: Public URL of this server (for OAuth callbacks)
        oauth_strict: Enable RFC 8707 resource validation

    Returns:
        Exit code (0 for success, 1 for error)
    """

    # Configure logging
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format))
        uv_logger.addHandler(handler)

    try:
        if server_url is None:
            server_url = os.getenv("MCP_EMAIL_SERVER_URL", f"https://localhost:{port}")

        if auth_server_public_url is None:
            auth_server_public_url = os.getenv("MCP_AUTH_SERVER_PUBLIC_URL", auth_server)

        server_url = server_url.rstrip("/")
        auth_server_public_url = auth_server_public_url.rstrip("/")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Make sure to provide a valid Authorization Server URL")
        return 1

    try:
        mcp_server = create_resource_server(
            port, server_url, auth_server, auth_server_public_url, oauth_strict
        )

        logger.info("=" * 60)
        logger.info(f"MCP Email Server running on {server_url}")
        logger.info(f"Using Authorization Server (internal): {auth_server}")
        logger.info(f"Using Authorization Server (public): {auth_server_public_url}")
        logger.info(f"Resource Server URL (for OAuth): {server_url}")
        logger.info("=" * 60)

        import uvicorn

        starlette_app = mcp_server.streamable_http_app()
        app = NormalizePathMiddleware(starlette_app)

        uvicorn.run(
            app,
            host="0.0.0.0",  # noqa: S104
            port=port,
            log_level="debug",
            proxy_headers=False,
            access_log=True,
        )
        logger.info("Server stopped")
        return 0
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.exception("Exception details:")
        return 1


if __name__ == "__main__":
    main()
