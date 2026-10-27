"""Validated local execution/trust choices; never disable TLS or repair system packages."""
import os
from pathlib import Path
import shutil
import ssl
import subprocess


def trusted_environment(env=None, system_ca=Path('/etc/ssl/cert.pem')):
    result = dict(os.environ if env is None else env)
    if result.get('NODE_TLS_REJECT_UNAUTHORIZED')=='0' or result.get('PYTHONHTTPSVERIFY')=='0' or result.get('NPM_CONFIG_STRICT_SSL','').lower()=='false':
        raise ValueError('TLS verification is disabled in the environment. Remove the insecure override and configure system/company trust before downloading.')
    for name in ('SSL_CERT_FILE', 'NODE_EXTRA_CA_CERTS', 'REQUESTS_CA_BUNDLE', 'PIP_CERT', 'NPM_CONFIG_CAFILE'):
        if result.get(name):
            file = Path(result[name]).expanduser()
            try:
                ssl.create_default_context(cafile=str(file))
                result[name]=str(file.absolute())
            except (OSError, ssl.SSLError) as error:
                raise ValueError(f'{name} does not name a readable valid CA bundle. Repair the company/system certificate configuration; TLS verification stays enabled.') from error
    configured=next((result[k] for k in ('SSL_CERT_FILE','REQUESTS_CA_BUNDLE','PIP_CERT','NPM_CONFIG_CAFILE','NODE_EXTRA_CA_CERTS') if result.get(k)),None)
    if configured:
        for key in ('SSL_CERT_FILE','NODE_EXTRA_CA_CERTS','PIP_CERT'):result.setdefault(key,configured)
    # The Mac's existing CA bundle fixes missing Homebrew OpenSSL certificate files.
    # Explicit company choices always win. No downloaded certificates or global writes.
    if system_ca.is_file():
        ssl.create_default_context(cafile=str(system_ca))
        result.setdefault('SSL_CERT_FILE', str(system_ca))
        result.setdefault('NODE_EXTRA_CA_CERTS', result['SSL_CERT_FILE'])
        result.setdefault('PIP_CERT', result['SSL_CERT_FILE'])
    context = ssl.create_default_context(cafile=result.get('SSL_CERT_FILE'))
    if not context.get_ca_certs():
        raise ValueError('No trusted CA certificates available. Restore system/company trust before downloading; do not disable TLS verification.')
    result['PYTHONDONTWRITEBYTECODE'] = '1'
    return result


def select_node(env=None):
    env = dict(os.environ if env is None else env)
    explicit = env.get('ACQ_EDIT_NODE')
    candidates = [explicit] if explicit else [
        '/opt/homebrew/opt/node@24/bin/node', '/usr/local/opt/node@24/bin/node',
        shutil.which('node', path=env.get('PATH')),
    ]
    for candidate in dict.fromkeys(x for x in candidates if x):
        try:
            executable = str(Path(candidate).resolve(strict=True))
            version = subprocess.check_output([executable, '--version'], env=env, text=True,
                                              stderr=subprocess.PIPE, timeout=10).strip()
            if int(version.lstrip('v').split('.')[0]) >= 24:
                return executable
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    raise ValueError('No working Node.js 24+ executable. Repair Node through your existing Homebrew/Workbrew installation, then create a verified ACQ runtime; do not edit the Premiere profile.')


def execution_environment(env=None):
    result = trusted_environment(env)
    node = select_node(result)
    result['ACQ_EDIT_NODE'] = node
    result['PATH'] = str(Path(node).parent) + os.pathsep + result.get('PATH', '')
    return result

if __name__=='__main__':
    import sys
    if len(sys.argv)<2:raise SystemExit('Supply the installer subprocess to run with verified trust and Node')
    os.execvpe(sys.argv[1],sys.argv[1:],execution_environment())
