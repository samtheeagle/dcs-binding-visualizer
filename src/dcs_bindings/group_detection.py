"""Shared group detection logic for finding connected button markers in images."""

import cv2
import numpy as np

from .models import DetectedMarker


def detect_groups(image_path: str, markers: list[DetectedMarker]) -> list[dict]:
    """Detect connected button groups by scanning for lines between markers.

    Args:
        image_path: Path to the device image.
        markers: List of detected markers with positions.

    Returns:
        List of groups: [{"buttons": [1, 2, 3], "layout": "vertical"}, ...]
    """
    img = cv2.imread(str(image_path))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    pos_map = {m.number: m for m in markers}

    def check_line(p1, p2):
        x1, y1 = p1.center_x, p1.center_y
        x2, y2 = p2.center_x, p2.center_y
        dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if dist < 30 or dist > 135:
            return False
        num_samples = int(dist) // 3
        skip = 20 / dist
        dark = 0
        total = 0
        for t in np.linspace(skip, 1 - skip, num_samples):
            x = int(x1 + t * (x2 - x1))
            y = int(y1 + t * (y2 - y1))
            if 0 <= x < gray.shape[1] and 0 <= y < gray.shape[0]:
                if gray[y, x] < 180:
                    dark += 1
                total += 1
        return total > 0 and (dark / total) > 0.5

    connected = []
    marker_list = list(pos_map.values())
    for i, p1 in enumerate(marker_list):
        for p2 in marker_list[i + 1:]:
            if check_line(p1, p2):
                connected.append((p1.number, p2.number))

    # Union-find with max group size 5
    parent = {}
    size = {}

    def find(x):
        if x not in parent:
            parent[x] = x
            size[x] = 1
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb and size[ra] + size[rb] <= 5:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]

    for a, b in connected:
        union(a, b)

    groups = {}
    for a, b in connected:
        for x in (a, b):
            r = find(x)
            groups.setdefault(r, set()).add(x)

    # Determine layout type for each group
    results = []
    for root, members in sorted(groups.items(), key=lambda x: min(x[1])):
        if len(members) < 2:
            continue
        buttons = sorted(members)
        xs = [pos_map[n].center_x for n in buttons]
        ys = [pos_map[n].center_y for n in buttons]
        x_spread = max(xs) - min(xs)
        y_spread = max(ys) - min(ys)

        if len(buttons) >= 4 and x_spread > 50 and y_spread > 50:
            layout = "hat"
        elif x_spread > y_spread:
            layout = "horizontal"
        else:
            layout = "vertical"

        results.append({"buttons": buttons, "layout": layout})

    return results
