def _verified_toolkit_profile(profile=None, path=None):
    """Bind even direct helper calls to this release's ACQ Edit Agent transport."""
    root = Path('__ACQ_TOOLKIT__')
    expected_path = root/'.local/premiere-profile.json'
    selected = path or (expected_path if profile is not None else os.environ.get('PREMIERE_AGENT_PROFILE') or expected_path)
    if str(selected) != str(expected_path):
        raise BridgeError('ACQ Edit Agent MCP only: external or legacy Premiere profiles are refused. Repair this toolkit installation; no fallback.')
    sys.path.insert(0, str(root/'python'))
    from premiere_installation import verify_profile
    try:
        data = verify_profile({'premiereProfile': str(expected_path)}, root)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        raise BridgeError('ACQ Edit Agent MCP is unavailable or its profile differs. Repair the toolkit integration and open the ACQ Edit Agent panel; do not use another bridge.') from error
    if profile is not None:
        actual = dict(vars(profile)); actual['command'] = list(profile.command)
        expected = {key: value for key, value in data.items() if key != 'schema'}
        if actual != expected:
            raise BridgeError('ACQ Edit Agent MCP only: supplied transport differs from the toolkit profile; no process was started.')
    return dict(data)


