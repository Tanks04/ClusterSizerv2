from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from src.models.cluster_project import ClusterProject
from src.models.network_connection import (
    NetworkConnection,
    SPEED_OPTIONS,
    MEDIA_OPTIONS,
    PURPOSE_OPTIONS,
    KIND_SERVER_SWITCH,
    KIND_STORAGE_SWITCH,
    KIND_SERVER_STORAGE,
    KIND_SWITCH_SWITCH,
)
from src.calculations.networking import server_nic_usage, switch_port_usage, storage_port_usage, format_usage

# For each connection kind: (label_a, entities_a_attr, uid_field_a),
# (label_b, entities_b_attr, uid_field_b), usage_fn_a, usage_fn_b.
# entities_*_attr is the ClusterProject list attribute name to populate
# that side's dropdown from; uid_field_* is the NetworkConnection field
# that side writes to.
_KIND_SPECS = {
    KIND_SERVER_SWITCH: {
        "a": ("Server", "servers", "server_uid", server_nic_usage),
        "b": ("Switch", "switches", "switch_uid", switch_port_usage),
    },
    KIND_STORAGE_SWITCH: {
        "a": ("Storage", "storages", "storage_uid", storage_port_usage),
        "b": ("Switch", "switches", "switch_uid", switch_port_usage),
    },
    KIND_SERVER_STORAGE: {
        "a": ("Server", "servers", "server_uid", server_nic_usage),
        "b": ("Storage", "storages", "storage_uid", storage_port_usage),
    },
    KIND_SWITCH_SWITCH: {
        "a": ("Switch", "switches", "switch_uid", switch_port_usage),
        "b": ("Switch (2nd)", "switches", "switch_b_uid", switch_port_usage),
    },
}

_ALL_UID_FIELDS = ["server_uid", "switch_uid", "storage_uid", "switch_b_uid"]


class ConnectionDialog(QDialog):
    """A physical link between two of {Server, Switch, Storage}. The
    Connection Type selector determines which two entity dropdowns are
    shown - Server<->Switch (the original case), Storage<->Switch (a
    storage array plugged into a SAN switch), or Server<->Storage direct
    (an HBA wired straight to an array, no switch in between - common
    with FC or SAS). Dropdowns are populated from the current project;
    below each one, free/used for the selected speed is shown, purely
    informational (doesn't block saving if oversubscribed - see the note
    in calculations/networking.py)."""

    def __init__(
        self,
        project: ClusterProject,
        connection: NetworkConnection | None = None,
        exclude_uid: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.project = project
        self._exclude_uid = exclude_uid

        self.setWindowTitle("Network Connection")
        self.resize(440, 340)

        layout = QFormLayout(self)

        self.type_combo = QComboBox()
        for kind in _KIND_SPECS:
            self.type_combo.addItem(kind, kind)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addRow("Connection Type", self.type_combo)

        self.label_a = QLabel("")
        self.combo_a = QComboBox()
        self.combo_a.currentIndexChanged.connect(self._update_usage_hint)
        layout.addRow(self.label_a, self.combo_a)

        self.label_b = QLabel("")
        self.combo_b = QComboBox()
        self.combo_b.currentIndexChanged.connect(self._update_usage_hint)
        layout.addRow(self.label_b, self.combo_b)

        self.speed_combo = QComboBox()
        self.speed_combo.addItems(SPEED_OPTIONS)
        self.speed_combo.currentIndexChanged.connect(self._update_usage_hint)
        layout.addRow("Speed", self.speed_combo)

        self.media_combo = QComboBox()
        self.media_combo.addItems(MEDIA_OPTIONS)
        layout.addRow("Media", self.media_combo)

        self.dedicated_link_check = QCheckBox("Dedicated/Proprietary link (e.g. a stacking cable, HA-sync port)")
        self.dedicated_link_check.setToolTip(
            "Check this for a proprietary or dedicated cable (Cisco StackWise, a "
            "firewall HA-sync port, a cluster heartbeat link) that does NOT "
            "consume one of the device's declared 1G/10G/etc ports - excluded "
            "from the port-usage/over-commit counting below, even though "
            "Speed/Media above can still be filled in for reference."
        )
        layout.addRow("", self.dedicated_link_check)

        self.port_label_edit = QLineEdit()
        self.port_label_edit.setPlaceholderText("e.g. Gi1/0/3, Uplink #1 (optional)")
        layout.addRow("Port Label", self.port_label_edit)

        self.purpose_combo = QComboBox()
        self.purpose_combo.addItems(PURPOSE_OPTIONS)
        layout.addRow("Purpose", self.purpose_combo)

        self.notes_edit = QLineEdit()
        layout.addRow("Notes", self.notes_edit)

        self.usage_label = QLabel("-")
        self.usage_label.setWordWrap(True)
        layout.addRow("Current port status", self.usage_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._uid = None

        if connection is not None:
            self.load(connection)
        else:
            self._on_type_changed()

    # ------------------------------------------------------------------
    # Connection type switching
    # ------------------------------------------------------------------

    def _current_kind(self) -> str:
        return self.type_combo.currentData() or KIND_SERVER_SWITCH

    def _on_type_changed(self) -> None:
        spec = _KIND_SPECS[self._current_kind()]

        label_a, attr_a, _, _ = spec["a"]
        label_b, attr_b, _, _ = spec["b"]

        self.label_a.setText(label_a)
        self.label_b.setText(label_b)

        self._populate_combo(self.combo_a, getattr(self.project, attr_a))
        self._populate_combo(self.combo_b, getattr(self.project, attr_b))

        self._update_usage_hint()

    @staticmethod
    def _populate_combo(combo: QComboBox, entities: list) -> None:
        combo.blockSignals(True)
        combo.clear()
        for entity in entities:
            combo.addItem(entity.name or "(unnamed)", entity.uid)
        combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Usage hint
    # ------------------------------------------------------------------

    def _update_usage_hint(self) -> None:
        spec = _KIND_SPECS[self._current_kind()]
        _, attr_a, _, usage_fn_a = spec["a"]
        _, attr_b, _, usage_fn_b = spec["b"]

        entities_a = getattr(self.project, attr_a)
        entities_b = getattr(self.project, attr_b)

        if not entities_a or not entities_b:
            self.usage_label.setText(
                f"Add at least one {spec['a'][0].lower()} and one {spec['b'][0].lower()}."
            )
            return

        speed = self.speed_combo.currentText()
        connections = [c for c in self.project.connections if c.uid != self._exclude_uid]

        entity_a = next((e for e in entities_a if e.uid == self.combo_a.currentData()), None)
        entity_b = next((e for e in entities_b if e.uid == self.combo_b.currentData()), None)

        parts = []
        for label, entity, usage_fn in (
            (spec["a"][0], entity_a, usage_fn_a),
            (spec["b"][0], entity_b, usage_fn_b),
        ):
            if not entity:
                continue
            usage = [u for u in usage_fn(entity, connections) if u.speed == speed]
            if usage:
                u = usage[0]
                parts.append(f"{label} {speed}: {u.used}/{u.total} used")
            else:
                parts.append(f"{label} has no declared {speed} ports")

        self.usage_label.setText("  |  ".join(parts) if parts else "-")

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def load(self, connection: NetworkConnection) -> None:
        self._uid = connection.uid

        idx = self.type_combo.findData(connection.connection_kind)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self._on_type_changed()

        idx = self.combo_a.findData(getattr(connection, _KIND_SPECS[connection.connection_kind]["a"][2]))
        if idx >= 0:
            self.combo_a.setCurrentIndex(idx)

        idx = self.combo_b.findData(getattr(connection, _KIND_SPECS[connection.connection_kind]["b"][2]))
        if idx >= 0:
            self.combo_b.setCurrentIndex(idx)

        self.speed_combo.setCurrentText(connection.speed)
        self.media_combo.setCurrentText(connection.media)
        self.dedicated_link_check.setChecked(connection.dedicated_link)
        self.port_label_edit.setText(connection.switch_port_label)
        self.purpose_combo.setCurrentText(connection.purpose)
        self.notes_edit.setText(connection.notes)

        self._update_usage_hint()

    def get_connection(self) -> NetworkConnection:
        connection = NetworkConnection.create_default()

        if self._uid:
            connection.uid = self._uid

        spec = _KIND_SPECS[self._current_kind()]
        _, _, uid_field_a, _ = spec["a"]
        _, _, uid_field_b, _ = spec["b"]

        # Clear all three, then set only the two relevant for this kind -
        # important when editing an existing connection whose type changed.
        for field in _ALL_UID_FIELDS:
            setattr(connection, field, "")

        setattr(connection, uid_field_a, self.combo_a.currentData() or "")
        setattr(connection, uid_field_b, self.combo_b.currentData() or "")

        connection.speed = self.speed_combo.currentText()
        connection.media = self.media_combo.currentText()
        connection.dedicated_link = self.dedicated_link_check.isChecked()
        connection.switch_port_label = self.port_label_edit.text()
        connection.purpose = self.purpose_combo.currentText()
        connection.notes = self.notes_edit.text()

        return connection
