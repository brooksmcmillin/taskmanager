"""Lakera Guard security integration for MCP tools.

Provides decorator-based protection against prompt injection attacks,
data leakage, and other AI security threats.

See: https://docs.lakera.ai/docs/api/guard
"""

import functools
import json
import logging
import os
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar, cast

import httpx

logger = logging.getLogger(__name__)

# Lakera Guard API configuration
LAKERA_API_URL = os.environ.get("LAKERA_GUARD_API_URL", "https://api.lakera.ai/v2/guard")
LAKERA_API_KEY = os.environ.get("LAKERA_GUARD_API_KEY", "")
LAKERA_GUARD_ENABLED = os.environ.get("LAKERA_GUARD_ENABLED", "false").lower() == "true"

# Type variables for generic decorator
P = ParamSpec("P")
R = TypeVar("R")


class LakeraGuardError(Exception):
    """Raised when Lakera Guard blocks content due to detected threats."""

    def __init__(self, message: str, categories: dict[str, bool] | None = None):
        super().__init__(message)
        self.categories = categories or {}


async def screen_content(text: str, role: str = "user") -> dict[str, Any]:
    """Screen content for security threats using Lakera Guard API.

    Args:
        text: The content to screen
        role: The role of the message sender (user, assistant, system, tool)

    Returns:
        Lakera Guard API response containing threat detection results

    Raises:
        httpx.HTTPError: If the API call fails
    """
    if not LAKERA_API_KEY:
        logger.warning("LAKERA_GUARD_API_KEY not set, skipping content screening")
        return {"results": [{"flagged": False, "categories": {}}]}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            LAKERA_API_URL,
            json={
                "messages": [{"role": role, "content": text}],
                "breakdown": True,
            },
            headers={
                "Authorization": f"Bearer {LAKERA_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


def is_content_flagged(guard_response: dict[str, Any]) -> tuple[bool, dict[str, bool]]:
    """Check if content was flagged by Lakera Guard.

    Args:
        guard_response: Response from Lakera Guard API

    Returns:
        Tuple of (is_flagged, categories dict)
    """
    results = guard_response.get("results", [])
    if not results:
        return False, {}

    result = results[0]
    flagged = result.get("flagged", False)
    categories = result.get("categories", {})

    return flagged, categories


def get_flagged_categories(categories: dict[str, bool]) -> list[str]:
    """Extract list of flagged category names.

    Args:
        categories: Categories dict from Lakera Guard response

    Returns:
        List of category names that were flagged
    """
    return [cat for cat, flagged in categories.items() if flagged]


def guard_content(
    input_params: list[str] | None = None,
    screen_output: bool = True,
    block_on_detection: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to protect MCP tools with Lakera Guard security screening.

    Screens specified input parameters and optionally the output for security
    threats including prompt injection, data leakage, and harmful content.

    Args:
        input_params: List of parameter names to screen (if None, screens all string params)
        screen_output: Whether to screen the tool's output
        block_on_detection: If True, raises LakeraGuardError on detection.
                           If False, logs warning but allows execution.

    Returns:
        Decorated function with security screening

    Example:
        @mcp.tool()
        @guard_content(input_params=["title", "description"])
        async def create_task(title: str, description: str) -> str:
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Skip screening if Lakera Guard is disabled
            if not LAKERA_GUARD_ENABLED:
                logger.debug(f"Lakera Guard disabled, executing {func.__name__} without screening")
                return await func(*args, **kwargs)  # type: ignore[misc]

            # Screen input parameters
            params_to_screen = input_params
            if params_to_screen is None:
                # Screen all string kwargs by default
                params_to_screen = [k for k, v in kwargs.items() if isinstance(v, str)]

            for param_name in params_to_screen:
                if param_name in kwargs and kwargs[param_name]:
                    value = kwargs[param_name]
                    if isinstance(value, str):
                        await _screen_and_handle(
                            content=value,
                            role="user",
                            context=f"input parameter '{param_name}' for {func.__name__}",
                            block_on_detection=block_on_detection,
                        )
                    elif isinstance(value, list):
                        # Handle list parameters (e.g., tags)
                        combined = " ".join(str(v) for v in value)
                        if combined.strip():
                            await _screen_and_handle(
                                content=combined,
                                role="user",
                                context=f"input parameter '{param_name}' for {func.__name__}",
                                block_on_detection=block_on_detection,
                            )

            # Execute the actual function
            result: R = await func(*args, **kwargs)  # type: ignore[misc]

            # Screen output if enabled
            if screen_output and result:
                output_text = result if isinstance(result, str) else json.dumps(result)
                await _screen_and_handle(
                    content=output_text,
                    role="assistant",
                    context=f"output from {func.__name__}",
                    block_on_detection=block_on_detection,
                )

            return cast(R, result)

        return wrapper  # type: ignore[return-value]

    return decorator


async def _screen_and_handle(
    content: str,
    role: str,
    context: str,
    block_on_detection: bool,
) -> None:
    """Screen content and handle detection results.

    Args:
        content: Text content to screen
        role: Message role (user/assistant)
        context: Description of what is being screened (for logging)
        block_on_detection: Whether to raise exception on detection
    """
    try:
        guard_response = await screen_content(content, role=role)
        flagged, categories = is_content_flagged(guard_response)

        if flagged:
            flagged_cats = get_flagged_categories(categories)
            message = f"Security threat detected in {context}: {', '.join(flagged_cats)}"

            logger.warning(f"Lakera Guard flagged content: {message}")
            logger.debug(f"Flagged content preview: {content[:200]}...")

            if block_on_detection:
                raise LakeraGuardError(message, categories)
        else:
            logger.debug(f"Lakera Guard: {context} passed security screening")

    except httpx.HTTPError as e:
        logger.error(f"Lakera Guard API error while screening {context}: {e}")
        # On API errors, we log but don't block (fail-open for availability)
        # Change this behavior based on your security requirements


def guard_tool(
    input_params: list[str] | None = None,
    screen_output: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Convenience decorator for MCP tools with default blocking behavior.

    This is the recommended decorator for protecting MCP tools.

    Args:
        input_params: List of parameter names to screen
        screen_output: Whether to screen tool output (default: True)

    Example:
        @mcp.tool()
        @guard_tool(input_params=["query"])
        async def search_tasks(query: str) -> str:
            ...
    """
    return guard_content(
        input_params=input_params,
        screen_output=screen_output,
        block_on_detection=True,
    )
