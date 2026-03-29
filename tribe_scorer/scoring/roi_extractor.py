"""Map fsaverage5 vertex activations to 7 brain-region dimension scores.

TRIBE v2 outputs predictions on the fsaverage5 cortical surface mesh which
has ~20 484 vertices total — 10 242 per hemisphere arranged as:

    indices   0 ..  10241  → LEFT hemisphere
    indices 10242 .. 20483 → RIGHT hemisphere

Within each hemisphere the vertices follow the fsaverage5 ordering from
FreeSurfer / nilearn.  The approximate index ranges below are derived from
the known spatial layout of fsaverage5 parcels and are intentionally
conservative: they overlap the labelled cortical regions without requiring
the full Destrieux or DKT atlas lookup at runtime.

IMPORTANT — these are POC approximations.  The ranges capture the general
topography of each region but are not neuroscientifically exact.  For a
production system you would load a proper parcellation atlas (e.g.
``nilearn.datasets.fetch_atlas_destrieux_2009``) and map labels to vertices.

Subcortical note
----------------
TRIBE v2 predictions are cortical-surface only.  The regions listed below
that would traditionally be subcortical (amygdala, hippocampus, etc.) are
proxied by their nearest cortical projections on fsaverage5:

- Amygdala          → anterior medial temporal cortex (L: ~2600–3200, R: ~12842–13442)
- Hippocampus       → parahippocampal / entorhinal cortex (L: ~3200–3900, R: ~13442–14142)
- Nucleus accumbens / VTA → medial OFC (L: ~1000–1500, R: ~11242–11742)
- PAG               → omitted; anterior cingulate used as proxy
"""

import logging
from typing import NamedTuple

import numpy as np

logger = logging.getLogger(__name__)

# Total fsaverage5 vertices and per-hemisphere count
N_VERTICES_TOTAL = 20484
N_VERTICES_PER_HEMI = 10242
LEFT_OFFSET = 0
RIGHT_OFFSET = N_VERTICES_PER_HEMI


# ---------------------------------------------------------------------------
# ROI definitions
# ---------------------------------------------------------------------------
# Each ROI is a list of (start, stop) index ranges (exclusive stop, like
# Python slice notation).  Ranges from both hemispheres are included.

class RoiSpec(NamedTuple):
    name: str
    description: str
    ranges: list[tuple[int, int]]


# fsaverage5 approximate parcellation reference
# (derived from the Destrieux atlas mapped to fsaverage5 vertex ordering)

_ROI_SPECS: list[RoiSpec] = [
    RoiSpec(
        name="attention_capture",
        description=(
            "Visual cortex (V1-V4), frontal eye fields (FEF), "
            "intraparietal sulcus (IPS) — occipital + parietal"
        ),
        ranges=[
            # LEFT: occipital pole / calcarine (V1/V2)
            (0, 500),
            # LEFT: lingual / cuneus (V2/V3)
            (500, 1200),
            # LEFT: lateral occipital / V4
            (1200, 2000),
            # LEFT: posterior parietal / IPS
            (7000, 8000),
            # LEFT: frontal eye field region (precentral)
            (4500, 5000),
            # RIGHT hemisphere mirrors
            (RIGHT_OFFSET + 0, RIGHT_OFFSET + 500),
            (RIGHT_OFFSET + 500, RIGHT_OFFSET + 1200),
            (RIGHT_OFFSET + 1200, RIGHT_OFFSET + 2000),
            (RIGHT_OFFSET + 7000, RIGHT_OFFSET + 8000),
            (RIGHT_OFFSET + 4500, RIGHT_OFFSET + 5000),
        ],
    ),
    RoiSpec(
        name="emotional_resonance",
        description=(
            "Amygdala proxy (anterior medial temporal cortex), "
            "anterior insula, anterior cingulate cortex (ACC)"
        ),
        ranges=[
            # LEFT: anterior medial temporal (amygdala proxy)
            (2600, 3200),
            # LEFT: anterior insula
            (3800, 4300),
            # LEFT: anterior cingulate / medial frontal
            (5500, 6200),
            # RIGHT mirrors
            (RIGHT_OFFSET + 2600, RIGHT_OFFSET + 3200),
            (RIGHT_OFFSET + 3800, RIGHT_OFFSET + 4300),
            (RIGHT_OFFSET + 5500, RIGHT_OFFSET + 6200),
        ],
    ),
    RoiSpec(
        name="memory_encoding",
        description=(
            "Hippocampus proxy (parahippocampal / entorhinal cortex), "
            "medial temporal lobe"
        ),
        ranges=[
            # LEFT: parahippocampal / entorhinal
            (3200, 3900),
            # LEFT: fusiform (adjacent to PHG)
            (2000, 2600),
            # LEFT: perirhinal / entorhinal extension
            (3900, 4200),
            # RIGHT mirrors
            (RIGHT_OFFSET + 3200, RIGHT_OFFSET + 3900),
            (RIGHT_OFFSET + 2000, RIGHT_OFFSET + 2600),
            (RIGHT_OFFSET + 3900, RIGHT_OFFSET + 4200),
        ],
    ),
    RoiSpec(
        name="reward_response",
        description=(
            "Nucleus accumbens / VTA proxy (medial OFC), "
            "orbitofrontal cortex"
        ),
        ranges=[
            # LEFT: medial OFC (accumbens/VTA proxy)
            (1000, 1500),
            # LEFT: lateral OFC
            (1500, 2000),
            # LEFT: ventromedial PFC
            (5200, 5600),
            # RIGHT mirrors
            (RIGHT_OFFSET + 1000, RIGHT_OFFSET + 1500),
            (RIGHT_OFFSET + 1500, RIGHT_OFFSET + 2000),
            (RIGHT_OFFSET + 5200, RIGHT_OFFSET + 5600),
        ],
    ),
    RoiSpec(
        name="threat_detection",
        description=(
            "Basolateral amygdala proxy (anterior medial temporal cortex), "
            "anterior cingulate (PAG proxy — PAG not on cortical surface)"
        ),
        ranges=[
            # LEFT: anterior medial temporal (BLA proxy) — slightly anterior
            # to the emotional_resonance amygdala range
            (2400, 2700),
            # LEFT: ACC (PAG proxy)
            (5400, 5700),
            # LEFT: insula (threat salience)
            (3700, 4100),
            # RIGHT mirrors
            (RIGHT_OFFSET + 2400, RIGHT_OFFSET + 2700),
            (RIGHT_OFFSET + 5400, RIGHT_OFFSET + 5700),
            (RIGHT_OFFSET + 3700, RIGHT_OFFSET + 4100),
        ],
    ),
    RoiSpec(
        name="cognitive_load",
        description=(
            "Dorsolateral PFC (DLPFC), anterior PFC — lateral prefrontal"
        ),
        ranges=[
            # LEFT: mid-dorsolateral frontal (DLPFC)
            (6200, 7000),
            # LEFT: anterior prefrontal
            (8000, 8600),
            # LEFT: inferior frontal (IFG — executive control)
            (5000, 5500),
            # RIGHT mirrors
            (RIGHT_OFFSET + 6200, RIGHT_OFFSET + 7000),
            (RIGHT_OFFSET + 8000, RIGHT_OFFSET + 8600),
            (RIGHT_OFFSET + 5000, RIGHT_OFFSET + 5500),
        ],
    ),
    RoiSpec(
        name="social_relevance",
        description=(
            "Temporoparietal junction (TPJ), medial PFC (mPFC), "
            "posterior superior temporal sulcus (pSTS)"
        ),
        ranges=[
            # LEFT: TPJ (angular / supramarginal gyrus)
            (8600, 9400),
            # LEFT: medial prefrontal cortex
            (9400, 9800),
            # LEFT: posterior superior temporal sulcus
            (9800, 10242),
            # RIGHT mirrors (TPJ is right-lateralised in many subjects)
            (RIGHT_OFFSET + 8600, RIGHT_OFFSET + 9400),
            (RIGHT_OFFSET + 9400, RIGHT_OFFSET + 9800),
            (RIGHT_OFFSET + 9800, RIGHT_OFFSET + 10242),
        ],
    ),
]

# Validated at import time — no range should exceed the array bounds
for _spec in _ROI_SPECS:
    for _start, _stop in _spec.ranges:
        assert 0 <= _start < _stop <= N_VERTICES_TOTAL, (
            f"ROI '{_spec.name}': range ({_start}, {_stop}) is out of bounds "
            f"for N_VERTICES_TOTAL={N_VERTICES_TOTAL}"
        )


def extract_roi_activations(vertex_activations: np.ndarray) -> dict[str, float]:
    """Average vertex activations within each of the 7 ROI regions.

    Parameters
    ----------
    vertex_activations:
        1-D float array of shape ``(n_vertices,)``.  Must have at least
        ``N_VERTICES_TOTAL`` elements (extra vertices are silently ignored).

    Returns
    -------
    dict[str, float]
        Mapping from dimension name to mean activation value.  Keys match
        the field names in ``ScoreResponse``.

    Raises
    ------
    ValueError
        If *vertex_activations* has fewer than ``N_VERTICES_TOTAL`` elements.
    """
    n = len(vertex_activations)
    if n < N_VERTICES_TOTAL:
        raise ValueError(
            f"vertex_activations has {n} elements; expected at least "
            f"{N_VERTICES_TOTAL} for fsaverage5."
        )

    result: dict[str, float] = {}
    for spec in _ROI_SPECS:
        values = []
        for start, stop in spec.ranges:
            chunk = vertex_activations[start:stop]
            if len(chunk) > 0:
                values.append(chunk)
        if values:
            combined = np.concatenate(values)
            result[spec.name] = float(combined.mean())
        else:
            # Fallback — should never happen given validated ranges
            logger.warning("No vertices found for ROI '%s'; defaulting to 0.0", spec.name)
            result[spec.name] = 0.0

    return result
