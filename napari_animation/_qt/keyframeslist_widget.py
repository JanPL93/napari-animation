from napari._qt.containers import QtListModel, QtListView
from qtpy.QtCore import QEvent, QModelIndex, QRect, QSize, Qt
from qtpy.QtGui import QImage
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
)


class KeyFrameModel(QtListModel):
    """Model for QtListView of KeyFrames"""

    def data(self, index: QModelIndex, role: Qt.ItemDataRole):
        """Return data at `index` for the requested `role`.

        see https://doc.qt.io/qt-5/model-view-programming.html#item-roles
        """
        if role == Qt.EditRole:
            return index.data(Qt.UserRole).name
        if role == Qt.DecorationRole:  # thumbnail
            key_frame = index.data(Qt.UserRole)
            return QImage(
                key_frame.thumbnail,
                key_frame.thumbnail.shape[1],
                key_frame.thumbnail.shape[0],
                QImage.Format_RGBA8888,
            )
        if role == Qt.SizeHintRole:  # determines size of item
            return QSize(240, 34)
        return super().data(index, role)

    def setData(self, index, value, role) -> bool:
        """Set data at `index` for `role` to `value`."""
        if value and role == Qt.EditRole:
            # user has double-clicked on the keyframe name
            key_frame = index.data(Qt.UserRole)
            key_frame.name = value
        return super().setData(index, value, role=role)


class KeyFrameItemDelegate(QStyledItemDelegate):
    """Draws an "Overwrite" button on each keyframe row.

    Clicking the button calls ``overwrite_callback(row)`` so the keyframe at
    that row can be replaced with the current viewer state.
    """

    BUTTON_WIDTH = 78
    BUTTON_MARGIN = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.overwrite_callback = None
        self._pressed_row = None

    def _button_rect(self, option) -> QRect:
        rect = option.rect
        return QRect(
            rect.right() - self.BUTTON_WIDTH - self.BUTTON_MARGIN,
            rect.top() + self.BUTTON_MARGIN,
            self.BUTTON_WIDTH,
            rect.height() - 2 * self.BUTTON_MARGIN,
        )

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        min_width = self.BUTTON_WIDTH + 2 * self.BUTTON_MARGIN + 140
        return QSize(max(size.width(), min_width), max(size.height(), 34))

    def paint(self, painter, option, index):
        # reserve space on the right for the button so it doesn't overlap
        # the thumbnail/name drawn by the default delegate.
        item_option = QStyleOptionViewItem(option)
        item_rect = QRect(option.rect)
        item_rect.setRight(
            item_rect.right() - self.BUTTON_WIDTH - 2 * self.BUTTON_MARGIN
        )
        item_option.rect = item_rect
        super().paint(painter, item_option, index)

        button = QStyleOptionButton()
        button.rect = self._button_rect(option)
        button.text = "Overwrite"
        state = QStyle.State_Enabled
        if self._pressed_row == index.row():
            state |= QStyle.State_Sunken
        else:
            state |= QStyle.State_Raised
        button.state = state
        QApplication.style().drawControl(QStyle.CE_PushButton, button, painter)

    def editorEvent(self, event, model, option, index):
        if event.type() in (
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
        ):
            if self._button_rect(option).contains(event.pos()):
                if event.type() == QEvent.MouseButtonPress:
                    self._pressed_row = index.row()
                else:  # release inside the button -> trigger overwrite
                    self._pressed_row = None
                    if self.overwrite_callback is not None:
                        self.overwrite_callback(index.row())
                # consume the event so it doesn't start a drag or selection
                return True
            self._pressed_row = None
        return super().editorEvent(event, model, option, index)


class KeyFramesListWidget(QtListView):
    """QtListView comes from napari and works with SelectableEventedList."""

    def __init__(self, root, parent=None):
        super().__init__(root, parent=parent)
        self.setModel(KeyFrameModel(root))
        self.setStyleSheet("KeyFramesListWidget::item { padding: 0px; }")

        # allow reordering keyframes by dragging them around
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

        # per-row "Overwrite" button
        self.keyframe_delegate = KeyFrameItemDelegate(self)
        self.setItemDelegate(self.keyframe_delegate)

    def set_overwrite_callback(self, callback):
        """Set ``callback(row)`` invoked when a row's Overwrite button is hit."""
        self.keyframe_delegate.overwrite_callback = callback
