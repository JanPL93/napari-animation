"""Background prefetching of upcoming frames' data slices.

The dominant cost when rendering an animation over lazily-loaded data (e.g. an
Imaris/HDF5 file surfaced as dask arrays) is reading each displayed slice from
disk -- this shows up as the ``apply`` phase in the performance log. The
:class:`SlicePrefetcher` reads the slices that *upcoming* frames will display on
background threads, so that by the time the main thread applies a frame the read
hits the OS/dask cache instead of disk, and several reads overlap.

Prefetching only *warms caches*; it never affects what is rendered, so any error
encountered while prefetching is swallowed. Reads go through ``np.asarray`` on
the layer data, which for dask-backed sources uses dask's scheduler (handling
locking for thread-safe backends such as h5py). If a data source is not safe for
concurrent reads, prefetching can be disabled with ``prefetch=0``.
"""

from __future__ import annotations

import contextlib
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np

logger = logging.getLogger("napari_animation")

#: Cap for the "auto" dask cache size.
_AUTO_CACHE_CAP = 2 * 1024**3  # 2 GiB
#: Fraction of available RAM to use for the "auto" dask cache.
_AUTO_CACHE_FRACTION = 0.25


def resolve_cache_bytes(spec) -> int:
    """Resolve a dask-cache size spec to a byte count (0 disables it).

    ``spec`` may be ``None``/``False`` (disabled), ``"auto"`` (a fraction of
    available RAM, capped), or an integer number of bytes.
    """
    if not spec:
        return 0
    if spec == "auto":
        try:
            import psutil

            available = psutil.virtual_memory().available
        except Exception:  # noqa: BLE001 - psutil optional/!available
            available = 4 * 1024**3
        return int(min(_AUTO_CACHE_CAP, _AUTO_CACHE_FRACTION * available))
    return int(spec)


@contextlib.contextmanager
def dask_cache_context(spec):
    """Register a dask opportunistic cache for the duration of the block.

    The cache lets prefetched (decompressed) chunks be reused by the main
    thread's slice instead of being recomputed, and makes frames that share a
    chunk free. Yields the cache size in bytes (0 if disabled/unavailable).
    """
    nbytes = resolve_cache_bytes(spec)
    if nbytes <= 0:
        yield 0
        return
    try:
        from dask.cache import Cache
    except Exception as err:  # noqa: BLE001 - cachey may be missing
        logger.warning(
            "dask cache unavailable (%s); continuing without it", err
        )
        yield 0
        return
    with Cache(nbytes):
        yield nbytes


def _layer_level_array(layer):
    """Return the array a layer would read from (handles multiscale)."""
    data = getattr(layer, "data", None)
    if data is None:
        return None
    if getattr(layer, "multiscale", False) and isinstance(data, (list, tuple)):
        if not data:
            return None
        level = getattr(layer, "data_level", 0)
        level = min(max(0, int(level)), len(data) - 1)
        return data[level]
    return data


def _axis_index(point, ranges, axis, size):
    """Map a world position along ``axis`` to an index into an array of size."""
    axis_range = ranges[axis]
    start, stop = float(axis_range[0]), float(axis_range[1])
    pt = float(point[axis])
    frac = 0.0 if stop == start else (pt - start) / (stop - start)
    idx = int(round(frac * (size - 1)))
    return max(0, min(size - 1, idx))


def read_keys(viewer, dims):
    """Yield ``(array, index)`` pairs to materialize each layer's slice.

    ``index`` is a tuple with ``slice(None)`` for displayed axes and an integer
    for sliced axes, computed from the (interpolated) ``dims`` of a frame.
    """
    ndim = dims["ndim"]
    ndisplay = dims["ndisplay"]
    order = list(dims["order"])
    point = dims["point"]
    ranges = dims["range"]
    displayed = set(order[-ndisplay:])

    keys = []
    for layer in viewer.layers:
        try:
            arr = _layer_level_array(layer)
            if arr is None:
                continue
            layer_ndim = getattr(layer, "ndim", arr.ndim)
            offset = ndim - layer_ndim
            index = []
            for ax in range(layer_ndim):
                global_ax = ax + offset
                if global_ax in displayed:
                    index.append(slice(None))
                else:
                    index.append(
                        _axis_index(point, ranges, global_ax, arr.shape[ax])
                    )
            keys.append((arr, tuple(index)))
        except Exception:  # noqa: BLE001 - best effort per layer
            continue
    return keys


class SlicePrefetcher:
    """Warm the data cache for frames ``current+1 .. current+depth`` ahead."""

    def __init__(self, viewer, frames, depth=2, workers=2):
        self.viewer = viewer
        self.frames = frames
        self.depth = max(0, int(depth))
        self.enabled = self.depth > 0
        self._submitted = set()
        self._pool = (
            ThreadPoolExecutor(
                max_workers=max(1, int(workers)),
                thread_name_prefix="napari-anim-prefetch",
            )
            if self.enabled
            else None
        )

    def advance(self, current_index):
        """Submit prefetch reads for the look-ahead window past ``current``."""
        if not self.enabled:
            return
        for i in range(current_index + 1, current_index + self.depth + 1):
            self._submit(i)

    def _submit(self, index):
        if index in self._submitted or index < 0 or index >= len(self.frames):
            return
        self._submitted.add(index)
        try:
            state = self.frames[index]
        except Exception:  # noqa: BLE001
            return
        self._pool.submit(self._warm, state.dims)

    def _warm(self, dims):
        try:
            for arr, index in read_keys(self.viewer, dims):
                np.asarray(arr[index])
        except Exception as err:  # noqa: BLE001 - cache warming is best effort
            logger.debug("prefetch read failed: %s", err)

    def shutdown(self):
        if self._pool is not None:
            self._pool.shutdown(wait=False)
            self._pool = None
