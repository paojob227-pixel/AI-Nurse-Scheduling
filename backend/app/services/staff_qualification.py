"""Qualification rules derived from ICU Rule Configuration v1.1."""

HEAD_NURSE_ALLOWED_SHIFT_CODES = frozenset({"AM", "D"})


class StaffQualificationError(ValueError):
    """Raised when a staff qualification conflicts with the ICU role rules."""


def is_head_nurse(position: str, account_role: str | None) -> bool:
    normalized_position = position.strip().upper().replace("_", " ")
    return account_role == "head_nurse" or normalized_position == "HEAD NURSE"


def resolve_senior_rn_status(position: str, account_role: str | None, requested_status: bool) -> bool:
    """Apply Senior RN eligibility rules without relying on a client-side check."""
    normalized_position = position.strip().upper().replace("_", " ")
    if is_head_nurse(position, account_role):
        return True
    if requested_status and normalized_position != "RN":
        raise StaffQualificationError("Only RN staff can be designated as Senior RN")
    return requested_status
