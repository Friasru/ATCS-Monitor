"""Deterministic counting scenarios (synthetic tracks, no model involved)."""

import pytest

from app.detection.types import Detection
from app.tracking.counter import CountingEngine, CountingLine

W, H = 1000, 1000


def box(cls, tid, cx, cy, size=40, conf=0.9):
    return Detection(cls, conf, cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2, tid)


def horizontal(direction="both", y=0.5):
    # P1 left, P2 right: side A (right-hand side walking P1->P2) is BELOW the line.
    return CountingLine("line-1", (0.1, y), (0.9, y), direction, True)


def run(engine, frames):
    events = []
    for i, dets in enumerate(frames):
        upd = engine.update(dets, (W, H), float(i))
        events.extend(upd.crossing_events)
    return events


def path(cls, tid, x, y0, y1, steps):
    return [[box(cls, tid, x, y0 + (y1 - y0) * k / (steps - 1))] for k in range(steps)]


def test_one_car_crossing_once_downwards_is_b_to_a():
    eng = CountingEngine([horizontal()])
    ev = run(eng, path("car", 1, 500, 300, 700, 12))
    assert [(e.cls, e.direction, e.track_id) for e in ev] == [("car", "b_to_a", 1)]
    assert eng.crossings["car"] == 1
    assert eng.unique["car"] == 1


def test_person_crossing_opposite_direction():
    eng = CountingEngine([horizontal()])
    ev = run(eng, path("person", 7, 400, 700, 300, 12))
    assert [(e.cls, e.direction) for e in ev] == [("person", "a_to_b")]


def test_stationary_car_never_counted():
    eng = CountingEngine([horizontal()])
    ev = run(eng, [[box("car", 1, 500, 520)] for _ in range(100)])
    assert ev == []
    assert eng.crossings["car"] == 0
    assert eng.unique["car"] == 1
    assert eng.visible["car"] == 1


def test_visible_counts_do_not_accumulate():
    eng = CountingEngine([horizontal()])
    for i in range(10):
        eng.update([box("car", 1, 100, 100), box("car", 2, 300, 100), box("person", 3, 500, 100)], (W, H), i)
    assert eng.visible == {"person": 1, "car": 2, "motorcycle": 0, "bicycle": 0, "bus": 0, "truck": 0}
    eng.update([box("car", 1, 100, 100)], (W, H), 11)
    assert eng.visible["car"] == 1 and eng.visible["person"] == 0


def test_untracked_detections_count_as_visible_only():
    eng = CountingEngine([horizontal()])
    for i in range(5):
        eng.update([Detection("car", 0.8, 0, 0, 10, 10, None)], (W, H), i)
    assert eng.visible["car"] == 1
    assert eng.unique["car"] == 0


def test_two_objects_crossing_simultaneously():
    eng = CountingEngine([horizontal()])
    frames = [
        [box("car", 1, 300, 300 + 40 * k), box("motorcycle", 2, 700, 300 + 40 * k)] for k in range(11)
    ]
    ev = run(eng, frames)
    assert sorted((e.cls, e.track_id) for e in ev) == [("car", 1), ("motorcycle", 2)]
    assert eng.crossings["car"] == 1 and eng.crossings["motorcycle"] == 1


@pytest.mark.parametrize("cls", ["bicycle", "motorcycle", "bus", "truck"])
def test_each_vehicle_class_counted_in_its_own_bucket(cls):
    eng = CountingEngine([horizontal()])
    run(eng, path(cls, 1, 500, 300, 700, 12))
    assert eng.crossings[cls] == 1
    assert sum(eng.crossings.values()) == 1  # e.g. a motorcycle is never a car


def test_track_disappearing_and_returning_with_same_id_not_double_counted():
    eng = CountingEngine([horizontal()])
    frames = path("car", 5, 500, 300, 700, 12)
    frames[5:8] = [[], [], []]  # occlusion around the line
    frames += [[] for _ in range(10)] + path("car", 5, 500, 700, 720, 5)
    ev = run(eng, frames)
    assert len(ev) == 1
    assert eng.unique["car"] == 1


def test_oscillation_near_line_is_absorbed_by_hysteresis():
    eng = CountingEngine([horizontal()], hysteresis_frac=0.01)  # ~14 px band
    frames = path("person", 1, 500, 400, 490, 6)
    for k in range(40):  # jitter +-8 px around the line
        frames.append([box("person", 1, 500, 500 + (8 if k % 2 else -8))])
    ev = run(eng, frames)
    assert ev == []


def test_oscillation_without_hysteresis_counts_at_most_once_per_direction():
    eng = CountingEngine([horizontal()], hysteresis_frac=0.0)
    frames = path("person", 1, 500, 400, 490, 6)
    for k in range(40):
        frames.append([box("person", 1, 500, 500 + (8 if k % 2 else -8))])
    ev = run(eng, frames)
    # Default policy: once per direction per track -> never more than 2.
    assert len(ev) <= 2
    assert len({e.direction for e in ev}) == len(ev)


def test_back_and_forth_counts_each_direction_once_only():
    eng = CountingEngine([horizontal()])
    frames = []
    for _ in range(3):
        frames += path("car", 1, 500, 300, 700, 8) + path("car", 1, 500, 700, 300, 8)
    ev = run(eng, frames)
    assert sorted(e.direction for e in ev) == ["a_to_b", "b_to_a"]


def test_direction_filter_a_to_b_only():
    eng = CountingEngine([horizontal("a_to_b")])
    run(eng, path("car", 1, 300, 300, 700, 12))  # downwards = b_to_a
    run(eng, path("car", 2, 600, 700, 300, 12))  # upwards = a_to_b
    assert eng.crossings["car"] == 1
    assert eng.line_totals["line-1"]["a_to_b"]["car"] == 1
    assert eng.line_totals["line-1"]["b_to_a"]["car"] == 0


def test_passing_beyond_line_end_is_not_a_crossing():
    eng = CountingEngine([horizontal()])
    ev = run(eng, path("car", 1, 960, 300, 700, 12))  # x=960 is right of P2 (x=900)
    assert ev == []


def test_track_id_switch_overcounts_and_this_is_visible():
    """Known limitation: if the tracker swaps a car's ID while it is on the
    line, the second ID can be counted again. This test documents it."""
    eng = CountingEngine([horizontal()], min_hits=1)
    frames = path("car", 1, 500, 300, 520, 8)  # crosses with id 1
    frames += [[box("car", 2, 500, 470)]]  # same physical car, new id, back above
    frames += path("car", 2, 500, 480, 700, 6)[1:]  # ...and crosses again
    ev = run(eng, frames)
    assert len(ev) == 2  # one real crossing counted twice
    assert eng.unique["car"] == 2


def test_unconfirmed_short_track_is_not_counted():
    eng = CountingEngine([horizontal()], min_hits=3)
    frames = [[box("car", 9, 500, 480)], [box("car", 9, 500, 530)]]  # only 2 hits
    ev = run(eng, frames + [[] for _ in range(5)])
    assert ev == [] and eng.unique["car"] == 0


def test_crossing_before_confirmation_is_committed_once_confirmed():
    eng = CountingEngine([horizontal()], min_hits=3)
    frames = [[box("car", 9, 500, 450)], [box("car", 9, 500, 560)], [box("car", 9, 500, 600)]]
    ev = run(eng, frames)
    assert [(e.track_id, e.direction) for e in ev] == [(9, "b_to_a")]


def test_line_moved_mid_session_produces_no_phantom_crossing():
    eng = CountingEngine([horizontal(y=0.5)])
    run(eng, [[box("car", 1, 500, 400)] for _ in range(5)])  # parked above y=500
    eng.set_lines([horizontal(y=0.3)])  # line moved above the parked car
    ev = run(eng, [[box("car", 1, 500, 400)] for _ in range(5)])
    assert ev == []
    ev = run(eng, path("car", 1, 500, 400, 100, 8))  # now it really crosses the moved line
    assert [e.direction for e in ev] == ["a_to_b"]


def test_counts_kept_when_line_moved():
    eng = CountingEngine([horizontal()])
    run(eng, path("car", 1, 500, 300, 700, 12))
    eng.set_lines([horizontal(y=0.2)])
    assert eng.crossings["car"] == 1


def test_stream_restart_resets_everything():
    eng = CountingEngine([horizontal()])
    run(eng, path("car", 1, 500, 300, 700, 12))
    eng.reset()
    assert sum(eng.crossings.values()) == 0 and sum(eng.unique.values()) == 0
    run(eng, path("car", 1, 500, 300, 700, 12))  # tracker restarted, IDs reused
    assert eng.crossings["car"] == 1


def test_disabled_class_is_ignored():
    eng = CountingEngine([horizontal()], enabled_classes=["car"])
    run(eng, path("person", 1, 500, 300, 700, 12))
    assert sum(eng.crossings.values()) == 0 and eng.visible["person"] == 0


def test_majority_vote_class_for_flickering_labels():
    eng = CountingEngine([horizontal()])
    frames = path("car", 1, 500, 300, 700, 12)
    frames[2] = [box("truck", 1, 500, 380)]  # one-frame misclassification
    run(eng, frames)
    assert eng.crossings == {"person": 0, "car": 1, "motorcycle": 0, "bicycle": 0, "bus": 0, "truck": 0}


def test_bottom_center_anchor():
    eng = CountingEngine([horizontal()], anchor="bottom_center")
    # Box centre stays above the line but its bottom edge crosses it.
    frames = [[Detection("person", 0.9, 480, 380 + 10 * k, 520, 470 + 10 * k, 1)] for k in range(8)]
    ev = run(eng, frames)
    assert len(ev) == 1


def test_stale_tracks_expire_and_emit_lost_event():
    eng = CountingEngine([horizontal()], max_age_frames=5)
    run(eng, [[box("car", 1, 100, 100)] for _ in range(4)])
    lost = []
    for i in range(7):
        lost += eng.update([], (W, H), 100 + i).track_events
    assert [e.event_type for e in lost] == ["track_lost"]
    assert eng.active_track_count == 0


def test_peak_and_average_visible():
    eng = CountingEngine([])
    eng.update([box("car", 1, 100, 100), box("car", 2, 300, 100)], (W, H), 0)
    eng.update([], (W, H), 1)
    assert eng.peak_visible_total == 2
    assert eng.average_visible_total == pytest.approx(1.0)


@pytest.mark.parametrize(
    "line",
    [
        CountingLine("x", (0.5, 0.5), (0.5, 0.5)),
        CountingLine("x", (-0.1, 0.5), (0.5, 0.5)),
        CountingLine("x", (0.1, 0.5), (1.5, 0.5)),
        CountingLine("x", (float("nan"), 0.5), (0.9, 0.5)),
        CountingLine("x", (0.1, 0.5), (0.9, 0.5), direction="sideways"),
        CountingLine("", (0.1, 0.5), (0.9, 0.5)),
    ],
)
def test_invalid_lines_rejected(line):
    with pytest.raises(ValueError):
        CountingEngine([line])


def test_duplicate_line_ids_rejected():
    with pytest.raises(ValueError):
        CountingEngine([horizontal(), horizontal(y=0.3)])


def test_two_lines_counted_independently():
    l1 = CountingLine("north", (0.1, 0.3), (0.9, 0.3))
    l2 = CountingLine("south", (0.1, 0.7), (0.9, 0.7))
    eng = CountingEngine([l1, l2])
    run(eng, path("car", 1, 500, 100, 900, 20))
    assert eng.line_totals["north"]["b_to_a"]["car"] == 1
    assert eng.line_totals["south"]["b_to_a"]["car"] == 1
    assert eng.crossings["car"] == 2  # crossings aggregate all lines


def test_line_roundtrip_dict():
    ln = CountingLine("l", (0.2, 0.3), (0.8, 0.6), "b_to_a", False)
    assert CountingLine.from_dict(ln.to_dict()) == ln
