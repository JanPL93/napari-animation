import numpy as np
import pytest
from napari.components import ViewerModel

from napari_animation.ortho_slicer import (
    OrthoSlicer,
    axis_to_view,
    view_to_axis,
)


def test_view_to_axis_3d():
    # napari convention: last axis = X, second-last = Y, third-last = Z
    assert view_to_axis("XY", 3) == 0  # slice Z
    assert view_to_axis("XZ", 3) == 1  # slice Y
    assert view_to_axis("YZ", 3) == 2  # slice X
    # extra leading (e.g. time) axes leave the spatial mapping intact
    assert view_to_axis("XY", 4) == 1
    assert view_to_axis("YZ", 4) == 3
    # case-insensitive
    assert view_to_axis("xy", 3) == 0


def test_axis_to_view_round_trip():
    for ndim in (3, 4, 5):
        for view in ("XY", "XZ", "YZ"):
            assert axis_to_view(view_to_axis(view, ndim), ndim) == view


@pytest.fixture
def model_viewer():
    # ViewerModel has real dims/layers but no Qt canvas, so no GL is needed.
    viewer = ViewerModel()
    viewer.add_image(
        np.random.random((10, 20, 20)), name="img", scale=(3, 1, 1)
    )
    return viewer


def test_to_from_dict_round_trip():
    slicer = OrthoSlicer(
        enabled=True, thickness=5, mode="clip", projection_mode="min", axis=0
    )
    assert OrthoSlicer.from_dict(slicer.to_dict()) == slicer
    # None / empty -> a disabled default slicer
    assert OrthoSlicer.from_dict(None) == OrthoSlicer()
    # unknown keys are ignored
    assert OrthoSlicer.from_dict({"enabled": True, "bogus": 1}).enabled


def test_projection_sets_margins_and_mode(model_viewer):
    OrthoSlicer(enabled=True, thickness=3, projection_mode="max").apply(
        model_viewer
    )
    # axis 0 has a step (scale) of 3; thickness 3 -> 1 plane either side -> 3 world units
    assert model_viewer.dims.margin_left[0] == pytest.approx(3.0)
    assert model_viewer.dims.margin_right[0] == pytest.approx(3.0)
    # other axes are untouched
    assert model_viewer.dims.margin_left[1] == 0
    assert str(model_viewer.layers["img"].projection_mode) == "max"


def test_single_plane_thickness_has_zero_margin(model_viewer):
    OrthoSlicer(enabled=True, thickness=1).apply(model_viewer)
    assert model_viewer.dims.margin_left[0] == pytest.approx(0.0)
    assert model_viewer.dims.margin_right[0] == pytest.approx(0.0)


def test_disabled_resets_view(model_viewer):
    OrthoSlicer(enabled=True, thickness=5).apply(model_viewer)
    assert model_viewer.dims.margin_left[0] != 0
    # applying a disabled slicer restores the full view
    OrthoSlicer(enabled=False).apply(model_viewer)
    assert model_viewer.dims.margin_left[0] == 0
    assert model_viewer.dims.margin_right[0] == 0
    assert str(model_viewer.layers["img"].projection_mode) == "none"


def test_clip_mode_sets_two_clipping_planes(model_viewer):
    # put the current plane in the middle so the slab is interior
    model_viewer.dims.current_step = (5, 9, 9)
    OrthoSlicer(enabled=True, thickness=4, mode="clip", axis=0).apply(
        model_viewer
    )
    planes = model_viewer.layers["img"].experimental_clipping_planes
    assert len(planes) == 2
    # the two planes bound the slab and face opposite directions along axis 0
    low_pos = planes[0].position[0]
    high_pos = planes[1].position[0]
    assert low_pos < high_pos
    assert planes[0].normal[0] == pytest.approx(1.0)
    assert planes[1].normal[0] == pytest.approx(-1.0)
    # projection margins must be cleared when in clip mode
    assert model_viewer.dims.margin_left[0] == 0


def test_ortho_params_interpolate_and_apply(model_viewer):
    # an optical section that grows from 1 to 11 planes across the animation
    from napari_animation import KeyFrame, ViewerState
    from napari_animation.frame_sequence import FrameSequence
    from napari_animation.key_frame import KeyFrameList

    def ortho(thickness):
        return {
            "enabled": True,
            "thickness": thickness,
            "mode": "projection",
            "projection_mode": "max",
            "axis": 0,
        }

    thumb = np.zeros((30, 30, 4), dtype=np.uint8)
    kfs = KeyFrameList()
    kfs.append(
        KeyFrame(
            viewer_state=ViewerState.from_viewer(model_viewer, ortho=ortho(1)),
            thumbnail=thumb,
            steps=1,
        )
    )
    kfs.append(
        KeyFrame(
            viewer_state=ViewerState.from_viewer(
                model_viewer, ortho=ortho(11)
            ),
            thumbnail=thumb,
            steps=10,
        )
    )
    frames = FrameSequence(kfs)

    thicknesses = [frames[i].ortho["thickness"] for i in range(len(frames))]
    # monotonically increasing optical section, interpolated between keyframes
    assert thicknesses[0] == 1
    assert thicknesses[-1] == 11
    assert thicknesses == sorted(thicknesses)
    assert 1 < thicknesses[len(thicknesses) // 2] < 11

    # a mid-animation interpolated state still applies to a viewer
    frames[len(frames) // 2].apply(model_viewer)
    assert model_viewer.dims.margin_left[0] > 0


def test_clip_axis_follows_selected_view(model_viewer):
    # YZ view -> slab along X (axis 2 for 3D data)
    axis = view_to_axis("YZ", model_viewer.dims.ndim)
    OrthoSlicer(enabled=True, thickness=4, mode="clip", axis=axis).apply(
        model_viewer
    )
    planes = model_viewer.layers["img"].experimental_clipping_planes
    assert len(planes) == 2
    # the clipping planes are oriented along the X axis, not Z
    assert planes[0].normal[2] == pytest.approx(1.0)
    assert planes[0].normal[0] == pytest.approx(0.0)


def test_clip_then_disable_clears_planes(model_viewer):
    OrthoSlicer(enabled=True, thickness=4, mode="clip").apply(model_viewer)
    assert len(model_viewer.layers["img"].experimental_clipping_planes) == 2
    OrthoSlicer(enabled=False).apply(model_viewer)
    assert len(model_viewer.layers["img"].experimental_clipping_planes) == 0
