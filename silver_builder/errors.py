class NormalizationError(Exception):
    """A value failed normalization badly enough to be quarantine-worthy —
    distinct from a merely-missing value, which normalizes to NULL."""

    def __init__(self, reason_code: str, detail: str):
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(detail)
