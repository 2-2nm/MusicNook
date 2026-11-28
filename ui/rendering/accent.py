"""Dominant / accent colour of a cover, shared by the Player and playlist pages."""

HUE_BINS = 24

# How colourful a cover has to be (share of its pixels that are neither dark nor grey) before its glow is fully
# vivid. Below SHARE_LOW the glow is a dark, muted tone (a mostly black cover with a coloured title gives almost
# no glow); in between it grows smoothly.
SHARE_LOW, SHARE_FULL = 0.15, 0.40
DIM_S, DIM_V = 0.45, 0.24      # the dark, muted tone of a nearly colourless cover
FALLBACK_HUE = 225.0           # its hue when the cover has no usable colour at all (the app's blue)


def _pick(pixels):
    """(h, s, v, colour_share) of the strongest hue, or None when nothing on the cover is colourful.
    colour_share is the fraction of the pixels that voted (not dark, grey or washed out)."""
    weight = [0.0] * HUE_BINS
    hits = [[] for _ in range(HUE_BINS)]
    total = colourful = 0
    for h, sat, val in pixels:
        total += 1
        if h < 0 or sat < 0.28 or val < 0.22:
            continue
        colourful += 1
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
    return ((centre + sh / sw) % 360, ss / sw, sv / sw, colourful / total)


def pick_accent(pixels):
    """Accent colour the way Windows picks one from a wallpaper. `pixels` is an iterable of (h, s, v): hue 0-359,
    saturation and value 0-1. Dark, grey and washed-out pixels are ignored (a mostly black cover must not give
    a muddy brown), the rest vote for their hue, weighted by how vivid they are. The strongest hue wins and
    its pixels are averaged. Returns (h, s, v), or None when nothing on the cover is colourful."""
    r = _pick(pixels)
    return None if r is None else r[:3]


def glow_hsv(pixels, fallback_hue: float = FALLBACK_HUE):
    """(h, s, v) of the glow for a cover (hue 0-360, s and v 0-1), or None when there are no pixels at all.

    The hue is the one pick_accent finds, pushed towards a vivid tone. How vivid it ends up depends on how much of
    the cover is colourful: a cover that is mostly black (or grey) gets a dark, muted glow even when its title or
    a small figure is bright blue; a colourful cover gets the full vivid glow."""
    pixels = list(pixels)
    if not pixels:
        return None
    r = _pick(pixels)
    if r is None:
        return (fallback_hue, DIM_S, DIM_V)
    h, sat, val, share = r
    vivid_s, vivid_v = min(0.95, max(sat, 0.55)), min(0.95, max(val, 0.75))
    t = max(0.0, min(1.0, (share - SHARE_LOW) / (SHARE_FULL - SHARE_LOW)))
    t = t * t * (3 - 2 * t)  # smoothstep: no sudden jump between "dark" and "vivid"
    return (h, DIM_S + (vivid_s - DIM_S) * t, DIM_V + (vivid_v - DIM_V) * t)