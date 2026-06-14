from types import SimpleNamespace

import numpy as np

from napari_animation.prefetch import SlicePrefetcher, read_keys


class CountingArray:
    """Array-like that counts how many times it is sliced (a 'read')."""

    def __init__(self, arr):
        self._arr = arr
        self.reads = 0

    @property
    def shape(self):
        return self._arr.shape

    @property
    def ndim(self):
        return self._arr.ndim

    def __getitem__(self, idx):
        self.reads += 1
        return self._arr[idx]


def _dims(point, ranges, ndisplay=2, ndim=3):
    return {
        "ndim": ndim,
        "ndisplay": ndisplay,
        "order": list(range(ndim)),
        "point": point,
        "range": ranges,
    }


def test_read_keys_slices_displayed_axes_indexes_rest():
    arr = CountingArray(np.zeros((10, 20, 20)))
    layer = SimpleNamespace(data=arr, ndim=3, multiscale=False, data_level=0)
    viewer = SimpleNamespace(layers=[layer])
    dims = _dims([5, 10, 10], [(0, 9, 1), (0, 19, 1), (0, 19, 1)])

    keys = read_keys(viewer, dims)
    assert len(keys) == 1
    array, index = keys[0]
    assert array is arr
    # axis 0 (Z, not displayed) -> integer; axes 1,2 (displayed) -> full slice
    assert index[0] == 5
    assert index[1] == slice(None) and index[2] == slice(None)


def test_read_keys_multiscale_uses_current_level():
    a0 = CountingArray(np.zeros((10, 40, 40)))
    a1 = CountingArray(np.zeros((10, 20, 20)))
    layer = SimpleNamespace(
        data=[a0, a1], ndim=3, multiscale=True, data_level=1
    )
    viewer = SimpleNamespace(layers=[layer])
    dims = _dims([5, 10, 10], [(0, 9, 1), (0, 39, 1), (0, 39, 1)])

    array, _ = read_keys(viewer, dims)[0]
    assert array is a1


def test_warm_materializes_slice():
    arr = CountingArray(np.zeros((10, 20, 20)))
    layer = SimpleNamespace(data=arr, ndim=3, multiscale=False, data_level=0)
    viewer = SimpleNamespace(layers=[layer])
    pf = SlicePrefetcher(viewer, frames=[], depth=2)
    pf._warm(_dims([5, 10, 10], [(0, 9, 1), (0, 19, 1), (0, 19, 1)]))
    assert arr.reads == 1


def test_advance_submits_future_window_only():
    frames = [
        SimpleNamespace(
            dims=_dims([0, 0, 0], [(0, 1, 1), (0, 1, 1), (0, 1, 1)])
        )
        for _ in range(5)
    ]
    pf = SlicePrefetcher(
        SimpleNamespace(layers=[]), frames, depth=2, workers=1
    )
    pf.advance(0)
    # frame 0 (current) is read by the main thread, so only 1 and 2 prefetch
    assert pf._submitted == {1, 2}
    pf.advance(3)  # 4 is valid, 5 is out of range
    assert pf._submitted == {1, 2, 4}
    pf.shutdown()


def test_disabled_when_depth_zero():
    pf = SlicePrefetcher(SimpleNamespace(layers=[]), [], depth=0)
    assert not pf.enabled
    assert pf._pool is None
    pf.advance(0)  # no-op
    assert pf._submitted == set()
