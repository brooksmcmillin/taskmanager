"""SSRF (Server-Side Request Forgery) protection utilities."""


def is_safe_url(url: str, allow_localhost: bool = True) -> bool:
    """Check if a URL is safe to request (SSRF protection).

    Args:
        url: The URL to validate
        allow_localhost: Whether to allow localhost/127.0.0.1 URLs

    Returns:
        True if the URL is considered safe, False otherwise

    Safe URLs must:
    - Use HTTPS for production endpoints
    - Use HTTP only for localhost (if allow_localhost is True)
    - Use HTTP for Docker internal hostnames (e.g., http://mcp-auth:)
    """
    # Allow HTTPS
    if url.startswith("https://"):
        return True

    # Allow localhost and Docker internal hostnames if enabled
    if allow_localhost:
        if url.startswith(("http://localhost", "http://127.0.0.1")):
            return True

    # Allow Docker internal hostnames (single-segment hostnames with no dots)
    # e.g., http://mcp-auth:, http://backend:
    if url.startswith("http://") and ":" in url:
        # Extract hostname (between http:// and the port :)
        host_part = url[len("http://") :].split(":")[0]
        # If no dots in hostname, it's likely a Docker service name
        if "." not in host_part:
            return True

    return False
