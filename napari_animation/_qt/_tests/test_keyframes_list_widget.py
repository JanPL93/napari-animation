from qtpy.QtCore import QEvent, QPointF, QRect, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QAbstractItemView, QStyleOptionViewItem

from napari_animation._qt.keyframeslist_widget import KeyFrameItemDelegate


class _FakeIndex:
    def __init__(self, row):
        self._row = row

    def row(self):
        return self._row


def _release_event(pos):
    return QMouseEvent(
        QEvent.MouseButtonRelease,
        QPointF(pos),
        Qt.LeftButton,
        Qt.LeftButton,
        Qt.NoModifier,
    )


def test_delegate_button_click_triggers_overwrite(qtbot):
    delegate = KeyFrameItemDelegate()
    called = []
    delegate.overwrite_callback = called.append

    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 240, 34)
    button_center = delegate._button_rect(option).center()

    handled = delegate.editorEvent(
        _release_event(button_center), None, option, _FakeIndex(2)
    )
    assert handled is True
    assert called == [2]


def test_drag_to_reorder_is_enabled(make_napari_viewer, qtbot):
    from napari_animation._qt import AnimationWidget

    viewer = make_napari_viewer()
    aw = AnimationWidget(viewer)
    qtbot.addWidget(aw)

    lst = aw.keyframesListWidget
    assert lst.dragDropMode() == QAbstractItemView.InternalMove
    assert lst.dragEnabled()
    # the per-row Overwrite button is wired to the widget callback
    assert (
        lst.keyframe_delegate.overwrite_callback
        == aw._overwrite_keyframe_callback
    )
