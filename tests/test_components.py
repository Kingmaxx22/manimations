"""Tests for the component library (construction only, no rendering)."""

from __future__ import annotations

import pytest
from manim import VGroup

from manimations.components import data, network, surfaces, typography
from manimations.helpers import layout


def test_typography_builders():
    assert typography.headline("Title").text == "Title"
    assert typography.body("Body").text == "Body"
    assert typography.mono("2001:db8::1").text == "2001:db8::1"
    assert isinstance(typography.scene_header("H", index="01"), VGroup)
    assert isinstance(typography.bullet_list(["a", "b"]), VGroup)


def test_highlight_phrase_recolors_substring():
    t = typography.highlight_phrase("the quick brown fox", "quick")
    # Manim's t2c rebuilds the text as sub-mobjects; the words are still present.
    assert "quick" in t.text
    assert "fox" in t.text


def test_surfaces_card_structure():
    card = surfaces.card("Title", "body text")
    assert isinstance(card, VGroup)
    assert len(card) == 2  # surface + content


def test_badge_and_callout():
    assert isinstance(surfaces.badge("IPv4"), VGroup)
    assert isinstance(surfaces.callout("note here"), VGroup)


def test_connector_between_mobjects():
    a = surfaces.badge("a")
    b = surfaces.badge("b")
    b.shift([3, 0, 0])
    conn = surfaces.connector(a, b)
    assert conn is not None


def test_elbow_connector_is_group():
    a = surfaces.badge("a")
    b = surfaces.badge("b").shift([2, -2, 0])
    assert isinstance(surfaces.elbow_connector(a, b), VGroup)


def test_address_block_cell_count_and_grouping():
    block = network.address_block(["2001", "db8", "1", "0"], dot=False, group_size=1)
    # 4 cells + 3 separators
    assert len(block) == 7
    # cells are at even indices
    assert block[0].width > 0
    assert block[0].height > 0


def test_address_block_wider_group_gap():
    block = network.address_block(
        ["a", "b", "c", "d", "e", "f", "g", "h"], dot=False,
        group_size=2, group_buff=1.0,
    )
    # gap after the 2nd and 4th cells should exceed the normal gap
    normal_gap = block[2].get_left()[0] - block[0].get_right()[0]
    group_gap = block[5].get_left()[0] - block[3].get_right()[0]
    assert group_gap > normal_gap


def test_bit_grid_dimensions():
    g = network.bit_grid(4, 8, cell=0.1)
    assert len(g) == 32


def test_network_nodes_and_icons():
    assert isinstance(network.node("Host"), VGroup)
    assert isinstance(network.router("R"), VGroup)
    assert isinstance(network.icon_cloud(), VGroup)
    assert isinstance(network.stack(["app", "transport", "network"]), VGroup)


def test_data_counter_has_tracker():
    c = data.counter(0, label="x")
    assert hasattr(c, "tracker")
    c.tracker.set_value(100)
    assert c.tracker.get_value() == 100


def test_data_meter_and_stat():
    assert isinstance(data.meter(0.5), VGroup)
    assert isinstance(data.stat_block("128-bit", "cap"), VGroup)


def test_data_comparison_columns():
    cmp = data.comparison("A", ["x", "y"], "B", ["p", "q"])
    assert isinstance(cmp, VGroup)
    assert len(cmp) == 2


def test_data_timeline_markers():
    tl = data.timeline([("1998", "standard"), ("2020", "now")])
    assert isinstance(tl, VGroup)


def test_layout_safe_area_and_helpers():
    area = layout.safe_area()
    assert area.width < 16  # frame width
    assert len(layout.columns(3, total_width=10, gap=0.5)) == 3
    assert len(layout.rows(3, total_height=6, gap=0.5)) == 3


def test_layout_fit_width_never_scales_up():
    from manim import Square

    sq = Square(side_length=1.0)
    layout.fit_width(sq, 5.0)
    assert sq.width == pytest.approx(1.0)


def test_safe_margins_scale_with_frame():
    """Margins are a fraction of the frame, so vertical is not starved."""
    from manim import config
    from manimations.theme import LANDSCAPE, VERTICAL, apply_theme

    apply_theme(orientation=LANDSCAPE)
    land = layout.safe_width()
    apply_theme(orientation=VERTICAL)
    vert = layout.safe_width()
    # vertical is narrower but keeps a similar *proportion* of usable width
    assert vert < land
    assert vert / config.frame_width == pytest.approx(land / (16 * 8 / 9), abs=0.02)


def test_is_vertical_tracks_orientation():
    from manimations.theme import LANDSCAPE, VERTICAL, apply_theme

    apply_theme(orientation=LANDSCAPE)
    assert layout.is_vertical() is False
    apply_theme(orientation=VERTICAL)
    assert layout.is_vertical() is True


def test_spread_fits_a_row_that_would_overflow():
    """A row too wide for the frame is shrunk, never left to overflow."""
    from manim import Square
    from manimations.theme import VERTICAL, apply_theme

    apply_theme(orientation=VERTICAL)
    squares = [Square(side_length=1.2) for _ in range(4)]  # 4.8 units total
    group = layout.spread(squares, gap=0.3)
    assert group.width <= layout.safe_width() + 0.02
    assert len(group) == 4


def test_pair_keeps_both_inside_safe_area():
    from manim import Square
    from manimations.theme import VERTICAL, apply_theme

    apply_theme(orientation=VERTICAL)
    a, b = Square(side_length=2.0), Square(side_length=2.0)
    layout.pair(a, b)
    half = layout.safe_width() / 2
    assert a.get_left()[0] >= -half - 0.02
    assert b.get_right()[0] <= half + 0.02


def test_stacked_fits_tall_content():
    from manim import Square
    from manimations.theme import VERTICAL, apply_theme

    apply_theme(orientation=VERTICAL)
    squares = [Square(side_length=1.5) for _ in range(6)]  # 9 units tall
    group = layout.stacked(squares, gap=0.2)
    assert group.height <= layout.safe_height() + 0.02


def test_offending_detects_offscreen():
    from manim import Square

    inside = Square(side_length=1.0)
    outside = Square(side_length=1.0).move_to([20, 0, 0])
    offenders = layout.offending_mobjects([inside, outside])
    assert outside in offenders
    assert inside not in offenders
