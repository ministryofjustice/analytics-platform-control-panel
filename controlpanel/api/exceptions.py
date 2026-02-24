class AddCustomerError(Exception):
    """Raised when adding a customer to an App fails."""

    pass


class DeleteCustomerError(Exception):
    """Raised when deleting a customer from an App fails."""

    pass


class AddViewerError(Exception):
    """Raised when adding a viewer to a Dashboard fails."""

    pass


class DeleteViewerError(Exception):
    """Raised when deleting a viewer from a Dashboard fails."""

    pass


class QuicksightAccessError(Exception):
    """Raised when granting or revoking QuickSight access fails."""

    pass
