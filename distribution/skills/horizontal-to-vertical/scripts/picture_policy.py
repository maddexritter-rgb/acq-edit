"""Execute recorded mirror intent without choosing a camera or an eyeline."""
def mirror_update(*, item_flip, ancestor_flips, intended_effective_flip):
    """Plan one item-local final state, including already-flipped parent nests.

    Values are inspected native states. Unknown state stays explicit rather than
    becoming an extra flip. The caller retains native item identity and evidence.
    """
    values=[item_flip, intended_effective_flip, *ancestor_flips]
    if any(type(v) is not bool for v in values):
        return {'status':'NEEDS_INSPECTION','change':False,
                'note':'Inspect item and every contributing parent flip before applying mirror intent'}
    parent=False
    for value in ancestor_flips:parent ^= value
    effective=item_flip ^ parent
    wanted_item=intended_effective_flip ^ parent
    return {'status':'PLANNED','change':wanted_item != item_flip,
            'current_effective_flip':effective,'intended_effective_flip':intended_effective_flip,
            'item_flip_before':item_flip,'item_flip_after':wanted_item,
            'verification':'Native application and composed eyeline review remain separate'}
