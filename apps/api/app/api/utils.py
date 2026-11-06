"""Shared utilities for API route handlers."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status

from app.services.store import Project, Template, User


def iso_format(dt: datetime) -> str:
    """Format a datetime as an ISO 8601 string with 'Z' suffix for UTC.
    
    Converts Python's +00:00 timezone suffix to the more standard 'Z' notation.
    """
    return dt.isoformat().replace("+00:00", "Z")


def require_ownership(
    resource: Project | Template | None,
    user: User,
    resource_type: str = "resource",
) -> Project | Template:
    """Verify that a resource exists and is owned by the given user.
    
    Args:
        resource: The resource to check (Project or Template)
        user: The authenticated user
        resource_type: Name of the resource type for error messages
    
    Returns:
        The resource if ownership is verified
    
    Raises:
        HTTPException: 404 if resource is missing or not owned by user
    """
    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type} not found",
        )
    if resource.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_type} not found",
        )
    return resource
