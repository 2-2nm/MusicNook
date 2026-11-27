"""Dominant / accent colour of a cover, shared by the Player and playlist pages."""

HUE_BINS = 24


def pick_accent(pixels):
    """Accent colour the way Windows picks one from a wallpaper. `pixels` is an iterable of (h, s, v): hue 0-359,
    saturation and value 0-1. Dark, grey and washed-out pixels are ignored (a mostly black cover must not give
    a muddy brown), the rest vote for their hue, weighted by how vivid they are. The strongest hue wins and
    its pixels are averaged. Returns (h, s, v), or None when nothing on the cover is colourful."""
    weight = [0.0] * HUE_BINS
    hits = [[] for _ in range(HUE_BINS)]
    total = 0
    for h, sat, val in pixels:
        total += 1
        if h < 0 or sat < 0.28 or val < 0.22:
            continue
        w = sat * sat * val  # vivid and bright pixels count more
        i = int(h * HUE_BINS / 360) % HUE_BINS
        weight[i] += w
        hits[i].append((h, sat, val, w))
    if not total:
        return None
    # a hue's score includes its neighbours, so one colour split over two bins is not beaten by a single bin
    score = [weight[i] + 0.5 * (weight[i - 1] + weight[(i + 1) % HUE_BINS]) for i in range(HUE_BINS)]
    best = max(range(HUE_BINS), key=score.__getitem__)
    if weight[best] < 0.004 * total:  # almost no colour on the cover: grey / black / white artwork
        return None
    centre = (best + 0.5) * 360 / HUE_BINS
    sw = sh = ss = sv = 0.0
    for h, sat, val, w in hits[best]:
        sh += ((h - centre + 180) % 360 - 180) * w  # hue offset from the bin centre (handles the red wrap)
        ss += sat * w
        sv += val * w
        sw += w
    return ((centre + sh / sw) % 360, ss / sw, sv / sw)
