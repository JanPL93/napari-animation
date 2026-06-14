import time

from napari_animation.perf import PerfLogger


def test_perf_logger_records_phases():
    perf = PerfLogger()
    perf.start()
    with perf.timer("a"):
        time.sleep(0.005)
    with perf.timer("a"):
        time.sleep(0.005)
    with perf.timer("b"):
        time.sleep(0.001)
    report = perf.report()
    assert "a" in report and "b" in report
    # phase "a" ran twice
    assert perf._counts["a"] == 2
    assert perf._totals["a"] >= perf._totals["b"]
    assert "wall-clock" in report


def test_perf_logger_disabled_is_noop():
    perf = PerfLogger(enabled=False)
    with perf.timer("a"):
        pass
    # nothing recorded when disabled
    assert perf._totals == {}
    assert perf.log_report() == perf.report()
