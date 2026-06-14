"""Tests for the save-dialog extension handling (no GUI interaction)."""

from napari_animation._qt.savedialog_widget import SaveDialogWidget

FILTERS = "MP4 (*.mp4);;GIF (*.gif);;Folder of PNGs (*)"


def test_ensure_extension_appends_from_filter(qtbot):
    dialog = SaveDialogWidget()
    qtbot.addWidget(dialog)
    dialog.setNameFilter(FILTERS)

    dialog.selectNameFilter("MP4 (*.mp4)")
    assert dialog._ensure_extension("C:/tmp/test") == "C:/tmp/test.mp4"
    # an explicit extension is left untouched
    assert dialog._ensure_extension("C:/tmp/test.mov") == "C:/tmp/test.mov"

    dialog.selectNameFilter("GIF (*.gif)")
    assert dialog._ensure_extension("movie") == "movie.gif"


def test_ensure_extension_png_folder_filter_keeps_bare_name(qtbot):
    dialog = SaveDialogWidget()
    qtbot.addWidget(dialog)
    dialog.setNameFilter(FILTERS)
    # "Folder of PNGs (*)" has no concrete extension -> keep the bare name so
    # animate() writes a folder of PNGs.
    dialog.selectNameFilter("Folder of PNGs (*)")
    assert dialog._ensure_extension("C:/tmp/frames") == "C:/tmp/frames"
