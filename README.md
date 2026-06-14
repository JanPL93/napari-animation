# napari-animation (WIP under active development)

[![License](https://img.shields.io/pypi/l/napari-animation.svg?color=green)](https://github.com/napari/napari-animation/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/napari-animation.svg?color=green)](https://pypi.org/project/napari-animation)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-animation.svg?color=green)](https://python.org)
[![tests](https://github.com/napari/napari-animation/actions/workflows/test_and_deploy.yml/badge.svg)](https://github.com/napari/napari-animation/actions)
[![codecov](https://codecov.io/gh/napari/napari-animation/branch/main/graph/badge.svg)](https://codecov.io/gh/napari/napari-animation)

**napari-animation** is a plugin for making animations in [napari].

----------------------------------

This [napari] plugin was generated with [Cookiecutter] using with [@napari]'s [cookiecutter-napari-plugin] template.

It is built off of great work from @guiwitz in [naparimovie](https://github.com/guiwitz/naparimovie) which was initially submitted to napari in [PR#851](https://github.com/napari/napari/pull/780).

----------------------------------
## Overview

**napari-animation** provides a framework for the creation of animations in napari and features:
- an easy to use GUI for interactive creation of animations
- Python tools for programmatic creation of animations

This plugin is currently pre-release and under active development. APIs are likely to change before it's first 0.0.1 release,
but feedback and contributions are welcome.

## Installation

You can clone this repository with install locally with

    pip install -e .

## Examples
Examples can be found in our [examples](examples) folder. Simple examples for both interactive and headless 
use of the plugin follow.

### Interactive
**napari-animation** can be used interactively by creating an `AnimationWidget` from a napari `Viewer` and adding it to
the viewer as a dock widget.

```python
from napari_animation import AnimationWidget

animation_widget = AnimationWidget(viewer)
viewer.window.add_dock_widget(animation_widget, area='right')
```

![AnimationWidget image](resources/screenshot-animation-widget.png)

### Headless
**napari-animation** can also be run headless, allowing for reproducible, scripted creation of animations.

```python
from napari_animation import Animation

animation = Animation(viewer)

viewer.dims.ndisplay = 3
viewer.camera.angles = (0.0, 0.0, 90.0)
animation.capture_keyframe()
viewer.camera.zoom = 2.4
animation.capture_keyframe()
viewer.camera.angles = (-7.0, 15.7, 62.4)
animation.capture_keyframe(steps=60)
viewer.camera.angles = (2.0, -24.4, -36.7)
animation.capture_keyframe(steps=60)
viewer.reset_view()
viewer.camera.angles = (0.0, 0.0, 90.0)
animation.capture_keyframe()
animation.animate('demo.mov', canvas_only=False)
```

### Editing keyframes

Keyframes can be **dragged to reorder** them in the list. Each keyframe row has
an **Overwrite** button that replaces that keyframe's captured view with the
current viewer state (keeping its name, steps and easing), so you can fix up a
single keyframe without deleting and re-adding it.

### Rendering performance

Frames are rendered on the main thread (napari needs its single OpenGL context
there), while encoding and writing to disk happen on a background thread so the
two overlap. By default `animate()` also logs a per-phase performance summary
so you can see what is rate-limiting:

```
napari-animation performance summary:
  interpolate  total=  0.10s  mean=    1.2ms  n=80     2.1%
  apply        total=  0.40s  mean=    5.0ms  n=80     8.3%
  screenshot   total=  4.10s  mean=   51.3ms  n=80    85.4%
  encode/write total=  0.20s  mean=    2.5ms  n=80     4.2%
  finalize     total=  0.05s
  wall-clock   total=  4.30s
```

A large `screenshot`/`apply` share usually means the viewer is waiting on lazy
data (e.g. dask-backed reads); a large `encode/write` share means disk/codec is
the bottleneck. Pass `perf_log=False` to silence it. If a video writer can't be
created, the fallback to a folder of PNGs is now reported rather than silent.

### Saving and resuming keyframes

Keyframes can be saved to a file so an animation can be resumed in a later
napari session. In the GUI, use the **Save Keyframes** / **Load Keyframes**
buttons; from Python use:

```python
animation.save_keyframes('my_animation.json')
# ... later, in a new session with the same data loaded ...
animation.load_keyframes('my_animation.json')
```

The file stores each keyframe's viewer state (camera, dims, layer display
settings, optical section), interpolation settings and a thumbnail. Pixel data
is **not** stored; instead the source file path of each layer is recorded and
those layers are re-opened on load (matched to keyframe state by layer name).
Pass `reload_layers=False` to skip re-opening and match against layers already
present in the viewer.

### Ortho slicer (optical sections)

An Imaris-style ortho slicer restricts the display to an optical section of a
chosen thickness (a number of planes) centered on the currently selected plane.
Enable it from the **Ortho slicer** panel in the GUI, or from Python:

```python
from napari_animation.ortho_slicer import view_to_axis

animation.ortho_slicer.enabled = True
animation.ortho_slicer.thickness = 7          # planes
animation.ortho_slicer.mode = 'projection'    # or 'clip'
animation.ortho_slicer.projection_mode = 'max'  # max/mean/min/sum
# orientation: defaults to XY; toggle to XZ / YZ via the GUI or set the axis
animation.ortho_slicer.axis = view_to_axis('YZ', viewer.dims.ndim)
animation.ortho_slicer.apply(viewer)
```

In `projection` mode the slab is projected into the 2D slice (a thick optical
section); in `clip` mode a 3D rendering is kept but only the slab is rendered.
The optical section defaults to the **XY** view (slab along Z) and can be
toggled to the **XZ** or **YZ** orthogonal views (slab along Y or X), which
changes the axis the slab runs along. The widget also shows the physical
section thickness derived from the layer scale/units (e.g. `0.5 µm/plane → 3.5
µm` for a 7-plane section), so you know how thick the optical section is. The optical-section parameters are
captured into keyframes, so the thickness, orientation or slab position can be
animated (e.g. a slab that sweeps through z or grows over the movie).

## Is everything animate-able?

Unfortunately, not yet! Currently differences in the following objects are tracked by the `Animation` class

- `Viewer.camera`
- `Viewer.dims`
- `Layer.scale`
- `Layer.translate`
- `Layer.rotate`
- `Layer.shear`
- `layer.opacity`
- `Layer.blending`
- `Layer.visible`

Support for more layer attributes will be added in future releases.

## Contributing

Contributions are very welcome and a detailed contributing guide is coming soon. 

Tests are run with `pytest`.

We use [`pre-commit`](https://pre-commit.com) to sort imports with
[`isort`](https://github.com/timothycrosley/isort), format code with
[`black`](https://github.com/psf/black), and lint with
[`flake8`](https://github.com/PyCQA/flake8) automatically prior to each commit.
To minmize test errors when submitting pull requests, please install `pre-commit`
in your environment as follows:

```sh
pre-commit install
```



## License

Distributed under the terms of the [BSD-3] license,
"napari-animation" is free and open source software

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[napari]: https://github.com/napari/napari
[Cookiecutter]: https://github.com/audreyr/cookiecutter
[@napari]: https://github.com/napari
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[cookiecutter-napari-plugin]: https://github.com/napari/cookiecutter-napari-plugin
[file an issue]: https://github.com/sofroniewn/napari-animation/issues
[napari]: https://github.com/napari/napari
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/
[PyPI]: https://pypi.org/