from vantacut.core.timecode import Timebase


def test_timebase_round_trip() -> None:
    timebase = Timebase(fps=25)
    ticks = timebase.seconds_to_ticks(3.25)
    assert ticks == 3250
    assert timebase.ticks_to_seconds(ticks) == 3.25
    assert timebase.ticks_to_frames(ticks) == 81


def test_clock_format() -> None:
    timebase = Timebase()
    assert timebase.format_clock(12_345) == "00:00:12.345"

