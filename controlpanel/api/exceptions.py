class AddCustomerError(Exception):
    pass


class DeleteCustomerError(Exception):
    pass


class QuicksightAccessError(Exception):
    """Raised when granting or revoking QuickSight access fails."""

    pass
