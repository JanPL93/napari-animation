from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QComboBox, QFormLayout, QGroupBox, QSpinBox

from ..ortho_slicer import ORTHO_VIEWS, PROJECTION_MODES, view_to_axis

if TYPE_CHECKING:
    from ..animation import Animation


class OrthoSlicerWidget(QGroupBox):
    """Controls for the Imaris-style optical-section (ortho) slicer.

    Lets the user enable an optical section of a chosen thickness (number of
    planes) centered on the currently selected plane, displayed either as a 2D
    projection or a 3D clipped sub-volume. The settings are pushed live to the
    viewer and are captured into keyframes so the optical section is animated.
    """

    def __init__(self, parent=None):
        super().__init__("Ortho slicer", parent=parent)
        self.animation: Animation = self.parentWidget().animation
        self.setCheckable(True)
        self.setChecked(self.animation.ortho_slicer.enabled)
        self.setToolTip(
            "Show only an optical section of N planes around the selected plane"
        )

        # thickness in planes
        self.thicknessSpinBox = QSpinBox()
        self.thicknessSpinBox.setRange(1, 100000)
        self.thicknessSpinBox.setValue(self.animation.ortho_slicer.thickness)
        self.thicknessSpinBox.setToolTip(
            "Optical section thickness, in planes"
        )

        # orthogonal view: which plane the optical section faces. Defaults to
        # XY (slab along Z); XZ/YZ slice along Y/X respectively.
        self.viewComboBox = QComboBox()
        self.viewComboBox.addItems(list(ORTHO_VIEWS))
        self.viewComboBox.setToolTip(
            "Orthogonal view the optical section faces "
            "(XY slices Z, XZ slices Y, YZ slices X)"
        )

        # display mode
        self.modeComboBox = QComboBox()
        self.modeComboBox.addItems(["projection", "clip"])
        self.modeComboBox.setCurrentText(self.animation.ortho_slicer.mode)

        # projection type (only used in projection mode)
        self.projectionComboBox = QComboBox()
        self.projectionComboBox.addItems(list(PROJECTION_MODES))
        self.projectionComboBox.setCurrentText(
            self.animation.ortho_slicer.projection_mode
        )

        layout = QFormLayout()
        layout.addRow("View", self.viewComboBox)
        layout.addRow("Thickness (planes)", self.thicknessSpinBox)
        layout.addRow("Mode", self.modeComboBox)
        layout.addRow("Projection", self.projectionComboBox)
        self.setLayout(layout)

        # callbacks
        self.toggled.connect(self._update_slicer)
        self.viewComboBox.currentIndexChanged.connect(self._update_slicer)
        self.thicknessSpinBox.valueChanged.connect(self._update_slicer)
        self.modeComboBox.currentIndexChanged.connect(self._update_slicer)
        self.projectionComboBox.currentIndexChanged.connect(
            self._update_slicer
        )
        # keep the optical section locked to the current plane as the user
        # scrolls through z.
        self.animation.viewer.dims.events.current_step.connect(
            self._on_dims_changed
        )

        self._update_enabled_state()

    def _update_enabled_state(self):
        """Projection type only applies in projection mode."""
        is_projection = self.modeComboBox.currentText() == "projection"
        self.projectionComboBox.setEnabled(is_projection)

    def _sync_slicer_from_widgets(self):
        slicer = self.animation.ortho_slicer
        slicer.enabled = self.isChecked()
        slicer.thickness = self.thicknessSpinBox.value()
        slicer.mode = self.modeComboBox.currentText()
        slicer.projection_mode = self.projectionComboBox.currentText()
        # translate the named orthogonal view into a concrete slab axis for the
        # current data dimensionality.
        ndim = self.animation.viewer.dims.ndim
        slicer.axis = view_to_axis(self.viewComboBox.currentText(), ndim)

    def _update_slicer(self, *args):
        """Push widget state to the slicer and apply it live to the viewer."""
        self._sync_slicer_from_widgets()
        self._update_enabled_state()
        self.animation.ortho_slicer.apply(self.animation.viewer)

    def _on_dims_changed(self, event=None):
        """Re-center the optical section when the selected plane changes."""
        if self.animation.ortho_slicer.enabled:
            self.animation.ortho_slicer.apply(self.animation.viewer)
