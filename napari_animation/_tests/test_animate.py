"""Tests for the (threaded) animate/render pipeline.

These avoid a real OpenGL context by stubbing ``viewer.screenshot`` and using a
``ViewerModel`` (which has real camera/dims/layers but no Qt canvas).
"""

import numpy as np
import pytest
from napari.components import ViewerModel

from napari_animation import Animation, KeyFrame, ViewerState


@pytest.fixture
def stub_animation(monkeypatch):
    viewer = ViewerModel()
    viewer.add_image(np.random.random((6, 20, 20)), name="img")

    # stub screenshot so no GL context is needed
    def fake_screenshot(self, *args, **kwargs):
        return np.zeros((64, 64, 4), dtype=np.uint8)

    monkeypatch.setattr(
        type(viewer), "screenshot", fake_screenshot, raising=False
    )

    animation = Animation(viewer)
    thumb = np.zeros((30, 30, 4), dtype=np.uint8)
    for i in range(2):
        animation.key_frames.append(
            KeyFrame(
                viewer_state=ViewerState.from_viewer(viewer),
                thumbnail=thumb,
                steps=3,
            )
        )
        viewer.camera.zoom *= 2
    return animation


def test_overwrite_keyframe_preserves_steps_and_name(stub_animation):
    animation = stub_animation
    animation.key_frames[0].name = "first"
    animation.key_frames[0].steps = 7
    old_state = animation.key_frames[0].viewer_state

    # change the view, then overwrite keyframe 0 with it
    animation.viewer.camera.zoom *= 5
    animation.overwrite_keyframe(0)

    kf = animation.key_frames[0]
    assert kf.name == "first"  # name preserved
    assert kf.steps == 7  # interpolation settings preserved
    assert kf.viewer_state != old_state  # captured state updated
    assert len(animation.key_frames) == 2  # overwrite, not insert


def test_animate_writes_mp4(tmp_path, stub_animation):
    out = tmp_path / "movie.mp4"
    stub_animation.animate(str(out), fps=10)
    assert out.exists()
    assert out.stat().st_size > 0


def test_animate_writes_png_folder(tmp_path, stub_animation, capsys):
    out = tmp_path / "frames"  # no extension -> folder of PNGs
    stub_animation.animate(str(out))
    pngs = list((tmp_path / "frames").glob("*.png"))
    # 2 keyframes, second has steps=3 -> 3 + 1 frames
    assert len(pngs) == 4
    # the user is told up-front that PNGs (not a video) are being written
    assert "No video file extension" in capsys.readouterr().out


def test_animate_writes_render_log(tmp_path, stub_animation):
    # video -> log sits next to the file
    out = tmp_path / "movie.mp4"
    stub_animation.animate(str(out))
    assert (tmp_path / "movie.render_log.txt").exists()
    log = (tmp_path / "movie.render_log.txt").read_text()
    assert "performance summary" in log and "frames:" in log

    # folder -> log sits inside the folder
    folder_out = tmp_path / "frames"
    stub_animation.animate(str(folder_out))
    assert (tmp_path / "frames" / "render_log.txt").exists()


def test_animate_loud_fallback_when_writer_fails(
    tmp_path, stub_animation, monkeypatch, capsys
):
    import imageio

    def boom(*args, **kwargs):
        raise ValueError("no ffmpeg here")

    monkeypatch.setattr(imageio, "get_writer", boom)
    out = tmp_path / "movie.mp4"
    stub_animation.animate(str(out))

    captured = capsys.readouterr().out
    assert "WARNING" in captured  # the fallback is no longer silent
    # PNGs were written to a sibling folder instead
    assert list((tmp_path / "movie").glob("*.png"))


def test_animate_perf_report_printed(tmp_path, stub_animation, capsys):
    out = tmp_path / "movie.mp4"
    stub_animation.animate(str(out), perf_log=True)
    report = capsys.readouterr().out
    assert "performance summary" in report
    assert "screenshot" in report and "encode/write" in report
