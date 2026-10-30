"""Recoverable domain errors. Each one carries what the caller needs to try again."""


class CatalogError(Exception):
    code = "catalog_error"

    def __init__(
        self,
        message: str,
        hint: str,
        allowed_values: list[str] | None = None,
        did_you_mean: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.allowed_values = allowed_values or []
        self.did_you_mean = did_you_mean or []


class UnknownCategory(CatalogError):
    code = "unknown_category"


class UnknownSubcategory(CatalogError):
    code = "unknown_subcategory"


class ProductNotFound(CatalogError):
    code = "product_not_found"
