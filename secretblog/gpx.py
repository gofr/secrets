import itertools
import math

import gpxpy
import gpxpy.parser


# Based on https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Python
def point2tile(point, zoom):
    """Return the (`zoom`, x, y) tuple for GPXTrackPoint `point`.

    Find the Web Mercator tile coordinates for a latitude/longitude.

    Raise a ValueError if the latitude is outside the Web Mercator range.
    """
    if abs(point.latitude) > 85.051129:
        raise ValueError("Latitude {point.latitude} is outside the Web Mercator range.")
    lat_rad = math.radians(point.latitude)
    n = 2**zoom
    x = int((point.longitude + 180) / 360 * n) % n
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
    return (zoom, x, y)


def _neighbors(coord, size, expand, wrap):
    """Return a list of numbers in the range `coord` +/- `expand`.

    `size` is the total amount of numbers available, from 0 to `size` - 1.
    When the neighborhood extends outside of that range, if `wrap` is True,
    wrap around and continue expanding the neighborhood there. If `wrap` is
    False, don't extend beyond the ends.

    E.g.
    neighbors(5, 7, True, 2) returns [3, 4, 5, 6, 0].
    neighbors(1, 7, False, 2) returns [0, 1, 2, 3].
    """
    neighborhood = list(range(max(0, coord - expand), min(size, coord + expand + 1)))
    if wrap:
        if coord - expand < 0:
            neighborhood = list(range((coord - expand) % size, size)) + neighborhood
        if coord + expand >= size:
            neighborhood.extend(range(0, (coord + expand + 1) % size))
    return neighborhood


def tile2neighborhood(tile, expand):
    """Return a set with `tile` and all tiles up to `expand` distance away."""
    zoom, x, y = tile
    n = 2**zoom
    return set(itertools.product(
        [zoom], _neighbors(x, n, expand, wrap=True), _neighbors(y, n, expand, wrap=False)))


class GPX(gpxpy.gpx.GPX):
    def get_map_tiles(self, zoom, expand=2):
        """Return set of Web Mercator projection map tiles that cover all tracks.

        Find all the tiles at `zoom` level, plus all tiles up to `expand`
        around it that are needed to cover all the tracks.
        Each tile is a (zoom, x, y) tuple.
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

        Each polyline is a list of (latitude, longitude) tuples.
        """
        lines = []
        for track in self.tracks:
            for segment in track.segments:
                lines.append([(p.latitude, p.longitude) for p in segment.points])
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
