"""Shared "existing data" prompt for imports - generalizes the Add/
Replace/Cancel pattern already established in Cluster Preparation's
per-site "Add Recommended Cluster" flow to every import in the app
(CSV, RVTools, Smart Import): if the destination already has some of
this kind of entity, ask whether to add the imported ones alongside,
replace the existing ones entirely, or cancel - rather than silently
appending on top of data that might already be there by mistake.
"""

from enum import Enum

from PySide6.QtWidgets import QMessageBox, QWidget


class ImportConflictChoice(Enum):
    ADD = "add"
    REPLACE = "replace"
    CANCEL = "cancel"


def confirm_import_conflict(
    parent: QWidget | None, kind: str, existing_count: int, new_count: int,
) -> ImportConflictChoice:
    """Returns ADD immediately, without prompting, if existing_count is
    0 - nothing to conflict with. kind should be a plural-ready noun
    ("server", "VM", "backup destination") for the message text."""
    if existing_count == 0:
        return ImportConflictChoice.ADD

    reply = QMessageBox.question(
        parent, "Existing Data",
        f"There are already {existing_count} {kind}(s) in this project. "
        f"Add the {new_count} imported {kind}(s) alongside the existing "
        f"ones, or replace the existing ones entirely?\n\n"
        "Yes = Add alongside\nNo = Replace existing\nCancel = Don't import",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
    )
    if reply == QMessageBox.StandardButton.Yes:
        return ImportConflictChoice.ADD
    if reply == QMessageBox.StandardButton.No:
        return ImportConflictChoice.REPLACE
    return ImportConflictChoice.CANCEL
