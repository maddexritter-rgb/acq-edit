"""Guard source-word recuts; existing skill owners still make every editorial decision."""
from pathlib import Path
from common import inside, plan, read, require, sha, fingerprint, save

OWNERS = {'captions': 'caption-clips', 'framing': 'horizontal-to-vertical',
          'audio': 'music', 'graphics': 'promo', 'textHook': 'text-hook'}


def component(spec, name):
    return {key: spec[key] for key in ['captions', 'graphics']} if name == 'textHook' else spec[name]


def prepare(project, packet):
    require(project['backend'] in ['filmcraft', 'resolve'], 'Spoken recut execution is not yet qualified for this backend')
    version_path = inside(Path(project['root']) / '20_DELIVER', packet['parentVersion'])
    version = read(version_path)
    require(version['id'] == packet['parentId'], 'Recut parent version differs from the submitted version')
    archive = version_path.parent
    require(archive.name == f"v{version['number']}-{version['id']}" and archive.parent.name == version['clipId'], 'Parent must be an immutable published version')
    for key, hash_key in [('nativeCheckpoint', 'nativeFingerprint'), ('planPath', 'planSha256'),
                          ('inspectionPath', 'inspectionSha256'), ('receiptPath', 'receiptSha256'), ('media', 'sha256')]:
        require(version.get(key) and version.get(hash_key), 'Parent lacks pinned publication evidence; reconcile/re-publish before a spoken recut')
        path = inside(archive, version[key])
        require(sha(path) == version[hash_key], 'Published parent evidence changed: ' + key)
    prior = read(version['planPath'])
    receipt = read(version['receiptPath'])
    require(prior['projectId'] == receipt['projectId'] == project['id'] and prior['backend'] == receipt['backend'] == project['backend'], 'Parent project/backend differs')
    require(prior['clipId'] == receipt['clipId'] == version['clipId'], 'Parent clip identity differs')
    require(receipt['nativeFingerprint'] == version['nativeFingerprint'], 'Parent native receipt differs')
    spec = plan(project, packet)
    require(spec['clipId'] == version['clipId'], 'A spoken recut must retain the clip identity')
    require(all(spec[key] == prior[key] for key in ['fps', 'sampleRate', 'width', 'height']), 'Recut preserves sequence clocks and canvas; format conversion needs a separate operation')
    require(spec['cuts'] != prior['cuts'], 'No changed source cuts; route styling to the finishing owner')
    require(spec['editorial']['sha256'] != prior['editorial']['sha256'], 'Spoken recut requires a fresh source-word selection')
    proof_path = inside(Path(project['root']) / '10_WORK', packet['finishingReceipt'])
    require(sha(proof_path) == packet['finishingSha256'], 'Recut finishing receipt changed')
    proof = read(proof_path)
    require(proof.get('schema') == 'acq-edit/recut-finishing-v1', 'Unsupported recut finishing receipt')
    require(proof['parentVersionId'] == version['id'] and proof['parentPlanSha256'] == version['planSha256'], 'Finishing decisions refer to another parent')
    require(proof['planSha256'] == sha(packet['plan']) and proof['cutsFingerprint'] == fingerprint(spec['cuts']), 'Dependent finishing decisions refer to stale cuts or plan')
    require(set(proof['components']) == set(OWNERS), 'Every dependent finishing owner must be addressed')
    for name, owner in OWNERS.items():
        row = proof['components'][name]
        require(row.get('owner') == owner, 'Incorrect finishing owner: ' + name)
        require(row.get('action') in ['recomputed', 'not-used'] and isinstance(row.get('reason'), str) and row['reason'].strip(), 'Explicit finishing decision required: ' + name)
        require(row.get('valueFingerprint') == fingerprint(component(spec, name)), 'Dependent layer differs from its decision: ' + name)
        if row['action'] == 'not-used' and name != 'textHook':
            require(not component(spec, name), 'Nonempty layer cannot be marked unused: ' + name)
    construction = packet['construction']
    require(inside(project['root'], construction['plan']) == inside(project['root'], packet['plan']), 'Construction refers to another plan')
    if project['backend'] == 'filmcraft':
        target = inside(Path(project['root']) / '10_WORK', construction['output'])
        require(not target.exists(), 'Recut output exists; inspect before retrying')
    else:
        for key in ['nativeProject', 'inspection']:
            target = inside(Path(project['root']) / '10_WORK', construction[key])
            require(not target.exists(), 'Recut checkpoint/inspection exists; inspect before retrying')
        require(construction['versionId'] != version['id'], 'New timeline identity required')
    verify_path = inside(Path(project['root']) / '10_WORK', packet['verification'])
    require(not verify_path.exists(), 'Recut verification already exists; inspect before retrying')
    state = read(version['inspectionPath'])
    # Render publication archives the raw state, not the outer inspection response.
    expected = fingerprint({'state': state, 'fileHash': version['nativeFingerprint']}) if project['backend'] == 'filmcraft' else fingerprint(state)
    return {'version': version, 'spec': spec, 'parentState': state, 'expected': expected,
            'verification': str(verify_path), 'planSha256': sha(packet['plan']),
            'finishingSha256': sha(proof_path)}


def record(project, packet, prepared, built):
    # Reject changed planner inputs or archived parent bytes after native construction.
    prepare_after_build(project, packet, prepared)
    proof = {'schema': 'acq-edit/recut-execution-v1', 'parentVersionId': prepared['version']['id'],
             'backend': project['backend'], 'planSha256': prepared['planSha256'],
             'finishingSha256': prepared['finishingSha256'], 'parentFingerprint': prepared['expected'],
             'parentPlanSha256': prepared['version']['planSha256'],
             'parentPreserved': True, 'construction': built, 'newNativeSha256': sha(inside(project['root'],built['nativeProject'])),
             'qualification': 'native state and pinned dependent plans; not speech listening or human approval'}
    save(prepared['verification'], proof)
    return {**built, 'parentId': prepared['version']['id'], 'recutVerification': prepared['verification']}


def prepare_after_build(project, packet, prepared):
    require(sha(packet['plan']) == prepared['planSha256'] and sha(packet['finishingReceipt']) == prepared['finishingSha256'], 'Recut planner inputs changed during construction')
    v = prepared['version']
    for key, hash_key in [('nativeCheckpoint', 'nativeFingerprint'), ('planPath', 'planSha256'),
                          ('inspectionPath', 'inspectionSha256'), ('receiptPath', 'receiptSha256'), ('media', 'sha256')]:
        require(sha(v[key]) == v[hash_key], 'Published parent changed during construction: ' + key)
