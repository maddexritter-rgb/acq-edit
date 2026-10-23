"""Canonical visible two-layer shadow for Filmcraft editable caption adapters.

Geometry is expressed at a rendered 75px caption size, then scaled with the glyphs.
Filmcraft's shadow_blur is three times Gaussian sigma. These values are specific
to its native compositor; do not feed them into Premiere or the ASS renderer.
"""
import math

PROFILE_ID = 'filmcraft-visible-two-layer-v1'
LAYER_ORDER = ('wide', 'tight', 'text')


def scoped_shadow_profile(caption_policy, *, brand, production_type):
    """Resolve a native-inspected override from the exact retrieved stage scope."""
    if not isinstance(caption_policy, dict) or caption_policy.get('brand') != brand or \
            caption_policy.get('production_type') != production_type or caption_policy.get('stage') != 'captions':
        return None
    backend = caption_policy.get('settings', {}).get('caption_shadow', {}).get('backends', {}).get('filmcraft', {})
    if backend.get('status') != 'native_inspected':
        return None
    return backend.get('profile')


def shadow_layer_props(layer, rendered_font_px=75, shadow_profile=None):
    """Return graphics.set props; keep foreground voice colors in its text runs."""
    if layer not in LAYER_ORDER:
        raise ValueError(f'Unknown caption layer: {layer}')
    if not math.isfinite(rendered_font_px) or rendered_font_px <= 0:
        raise ValueError('rendered_font_px must be finite and positive')
    props = {'fill': True, 'stroke': False, 'stroke2': False,
             'background': False, 'shadow': layer != 'text'}
    if layer == 'text':
        return props
    scale = rendered_font_px / 75
    dx, dy, spread, blur = ((2, 2, 9, 48) if layer == 'wide'
                            else (4, 6, 4, 12))
    opacity = 100
    if shadow_profile is not None:
        if not isinstance(shadow_profile, dict) or set(shadow_profile) != {'id', 'wide_opacity', 'tight_opacity'}:
            raise ValueError('Scoped shadow profile needs id, wide_opacity and tight_opacity')
        if not isinstance(shadow_profile['id'], str) or not shadow_profile['id'].strip():
            raise ValueError('Scoped shadow profile needs a stable id')
        for key in ('wide_opacity', 'tight_opacity'):
            v = shadow_profile[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 100:
                raise ValueError('Shadow opacity must be finite and within 0..100')
        opacity = shadow_profile[layer + '_opacity']
    props.update(fill_color=[0, 0, 0, 0], shadow_color='#000000',
                 shadow_opacity=opacity,
                 shadow_angle=90 + math.degrees(math.atan2(dy, dx)),
                 shadow_distance=math.hypot(dx, dy) * scale,
                 shadow_size=spread * scale, shadow_blur=blur * scale)
    return props
