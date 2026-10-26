def project_source_candidate(selection, candidate, evidence):
    """Bind the eligible catalog recording to an unchanged project-owned source.

    Full decoded PCM equality permits container/codec normalization, never edits,
    offsets, gain, fades or replacement recordings. Approval stays on the catalog.
    """
    import subprocess
    binding = selection.get('project_source')
    if binding is None:
        return candidate, evidence
    if not isinstance(binding, dict) or binding.get('schema') != 'edit.music-project-source/v1':
        raise BridgeError('Invalid project music source binding')
    target = selection.get('target', {})
    project = Path(target.get('project_path', ''))
    media = Path(binding.get('path', ''))
    if not project.is_absolute() or project.parent.name != '10_WORK' or not media.is_absolute():
        raise BridgeError('Music binding requires the project storage convention')
    source_root = (project.parent.parent / '00_SOURCE').resolve()
    if not media.resolve().is_relative_to(source_root):
        raise BridgeError('Music must be a project-owned source')
    if any(not isinstance(binding.get(k), str) or len(binding[k]) != 64 or
           any(c not in '0123456789abcdef' for c in binding[k])
           for k in ('catalog_sha256', 'sha256', 'decoded_pcm_sha256')):
        raise BridgeError('Music binding requires exact SHA256 pins')
    catalog = artifact(candidate['path'], binding['catalog_sha256'])
    owned = artifact(media, binding['sha256'])
    for path in (candidate['path'], str(media)):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', path,
                                 '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2',
                                 '-c:a', 'pcm_s24le', '-f', 'hash', '-hash', 'sha256', '-'],
                                capture_output=True, text=True, timeout=120, check=True)
        if result.stdout.strip() != 'SHA256=' + binding['decoded_pcm_sha256']:
            raise BridgeError('Project music differs from the complete catalog recording')
    return {**candidate, 'path': str(media)}, evidence + [catalog, owned]
