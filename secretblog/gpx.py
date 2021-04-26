import itertools
import math

import gpxpy
import gpxpy.parser


class Tile:
    __slots__ = ["zoom", "x", "y"]

    def __init__(self, zoom, x, y):
        self.zoom = zoom
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.zoom == other.zoom and self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.zoom, self.x, self.y))


# Based on https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
def point2tile(point, zoom):
    """Return a Tile(`zoom`, x, y) for GPXTrackPoint `point`.

    Find the Web Mercator tile coordinates for a latitude/longitude.

    Raise a ValueError if the latitude is outside the Web Mercator range.
    """
    if abs(point.latitude) > 85.051129:
        raise ValueError("Latitude {point.latitude} is outside the Web Mercator range.")
    lat_rad = math.radians(point.latitude)
    n = 2**zoom
    x = int((point.longitude + 180) / 360 * n) % n
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
    return Tile(zoom, x, y)


def _neighbors(coord, size, expand, wrap):
    """Return a list of numbers in the range `coord` +/- `expand`.

    `size` is the total amount of numbers available, from 0 to `size` - 1.
    When the neighborhood extends outside of that range, if `wrap` is True,
    continue expanding the neighborhood at the other end. If `wrap` is False,
    don't extend beyond the ends.

    The list will not contain duplicates when the expansion is big enough to
    cause wrapped ends to overlap.

    E.g.
    neighbors(5, 7, 2, True) returns [3, 4, 5, 6, 0].
    neighbors(1, 7, 2, False) returns [0, 1, 2, 3].
    """
    lower_limit = coord - expand
    upper_limit = coord + expand + 1
    neighborhood = list(range(max(0, lower_limit), min(size, upper_limit)))
    if wrap:
        first = neighborhood[0]
        last = neighborhood[-1]
        if lower_limit < 0:
            neighborhood = list(range(max(last + 1, lower_limit % size), size)) + neighborhood
        if upper_limit > size:
            neighborhood.extend(range(0, min(first, upper_limit % size)))
    return neighborhood


def tile2neighborhood(tile, expand):
    """Return a set with `tile` and all tiles up to `expand` distance away."""
    n = 2**tile.zoom
    return set(map(lambda t: Tile(*t), itertools.product(
        [tile.zoom],
        _neighbors(tile.x, n, expand, wrap=True),
        _neighbors(tile.y, n, expand, wrap=False)
    )))


class GPX(gpxpy.gpx.GPX):
    def get_map_tiles(self, zoom, expand=None):
        """Return set of Web Mercator projection map Tile objects to cover all tracks.

        Find all tiles at `zoom` level needed to cover all tracks, plus
        optionally all tiles up to `expand` distance away from it (horizontally
        and/or vertically).
        """
        center_tiles = set(point2tile(p, zoom) for p in self.walk(only_points=True))
        if expand:
            tiles = center_tiles.copy()
            for t in center_tiles:
                tiles.update(tile2neighborhood(t, expand))
        else:
            tiles = center_tiles
        return tiles

    def get_polylines(self):
        """Return a list of polylines, one for each track segment.

        Each polyline is a list of (longitude, latitude) tuples.
        """
        lines = []
        for track in self.tracks:
            for segment in track.segments:
                lines.append([(p.longitude, p.latitude) for p in segment.points])
        return lines

    # This overrides a built-in which is slower and buggy.
    def get_bounds(self):
        """Return the bounding box around all tracks.

        The return value is a (minimum, maximum) tuple, where both values are
        themselves (latitude, longitude) tuples.
        """
        points = list(self.walk(only_points=True))
        latitudes = [p.latitude for p in points]
        longitudes = [p.longitude for p in points]
        return ((min(latitudes), min(longitudes)), (max(latitudes), max(longitudes)))


class GPXParser(gpxpy.parser.GPXParser):
    # Override to make it use my extended GPX class instead.
    def __init__(self, xml_or_file):
        self.xml = ""
        self.init(xml_or_file)
        self.gpx = GPX()
