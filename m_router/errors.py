class MRouterError(Exception):
    """Base exception for all M-Router SDK errors."""


class MRouterUnavailableError(MRouterError):
    """Raised when the hosted M-Router service is unavailable."""


class RouteDecisionError(MRouterError):
    """Raised when a route response is invalid or cannot be used."""


class ModelNotRegisteredError(MRouterError):
    """Raised when a selected model is not registered locally."""


class SchemaValidationError(MRouterError):
    """Raised when a response fails local schema validation."""


class GatewayExecutionError(MRouterError):
    """Raised when hosted gateway execution fails."""
