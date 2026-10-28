#!/usr/bin/env python3
"""Local credential entry. Provider keys never travel through agent arguments or logs."""
import argparse
import fcntl
import getpass
import html
import re
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

KEYS = ('ASSEMBLYAI_API_KEY', 'GEMINI_API_KEY')


def save_keys(root, values):
    if not isinstance(values, dict) or set(values) - set(KEYS):
        raise ValueError('Use the two labeled key fields.')
    if any(not isinstance(v, str) or len(v) > 4096 or any(c.isspace() for c in v.strip()) for v in values.values()):
        raise ValueError('Paste only the key, without spaces or extra text.')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Serialize read/merge/replace so simultaneous setup windows preserve updates.
    fd = os.open(root / 'credentials.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        target = root / 'credentials.json'
        if target.is_symlink():
            raise ValueError('Cannot save to a linked credential file.')
        data = json.loads(target.read_text()) if target.exists() else {}
        if not isinstance(data, dict):
            raise ValueError('Existing credential file needs repair.')
        for key, value in values.items():
            if value.strip():
                data[key] = value.strip()
        if any(not isinstance(data.get(key), str) or not data[key].strip() for key in KEYS):
            raise ValueError('Please add both keys. Blank fields keep keys already saved.')
        fd, name = tempfile.mkstemp(prefix='.credentials-', dir=root)
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(data, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, target)
        finally:
            if os.path.exists(name):
                os.unlink(name)


PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connect ACQ Edit</title>
<style nonce="NONCE">body{background:#111318;color:#f5f5f5;font:17px system-ui;margin:0;padding:36px 20px}main{max-width:480px;margin:5vh auto;background:#1c2028;padding:32px;border-radius:20px}h1{font-size:30px}p{color:#bac3d0;line-height:1.5}label{display:block;margin:24px 0 8px;font-weight:650}input{box-sizing:border-box;width:100%;padding:14px;border:1px solid #626d80;border-radius:8px;background:#111318;color:white;font:inherit}a{color:#a6c5ff}button{padding:13px 20px;border:0;border-radius:8px;font:inherit;cursor:pointer;margin:24px 8px 0 0;background:#bdd4ff;color:#101827}button.secondary{background:#343b49;color:white}small{display:block;margin-top:8px;color:#bac3d0}#status{min-height:48px}</style>
<main><h1>Connect your editing tools</h1><p>Paste your two keys below. They stay on this Mac and are not sent to your chat. No files to edit.</p>
<form id="form"><label for="assembly">AssemblyAI key</label><input id="assembly" name="ASSEMBLYAI_API_KEY" type="password" autocomplete="off" spellcheck="false" maxlength="4096"><small>Finds spoken words and their timing. <a href="https://www.assemblyai.com/dashboard" target="_blank" rel="noreferrer">Get your key ↗</a></small>
<label for="gemini">Gemini key</label><input id="gemini" name="GEMINI_API_KEY" type="password" autocomplete="off" spellcheck="false" maxlength="4096"><small>Helps inspect video and audio. <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">Get your key ↗</a></small>
<p>Already connected? Leave a field blank to keep its saved key.</p><button id="save">Save keys</button><button class="secondary" type="button" id="cancel">Cancel</button></form><p id="status" role="status" aria-live="polite"></p></main>
<script nonce="NONCE">
const token=location.hash.slice(1);history.replaceState(null,'','/');
const form=document.getElementById('form'),status=document.getElementById('status');
async function submit(action){
 const buttons=[...document.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
 try{
  const values=action==='save'?Object.fromEntries([...form.querySelectorAll('input')].map(input=>[input.name,input.value])):{};
  const response=await fetch('/'+action,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(values)});
  const result=await response.json();status.textContent=result.message;
  if(response.ok){form.reset();form.hidden=true;}else{buttons.forEach(b=>b.disabled=false);}
 }catch{status.textContent='This setup window has closed or expired. Ask your agent to reopen key setup.';buttons.forEach(b=>b.disabled=false);}
}
form.addEventListener('submit',event=>{event.preventDefault();submit('save')});
document.getElementById('cancel').addEventListener('click',()=>submit('cancel'));
if(!token){status.textContent='Ask your agent to reopen key setup to get a fresh setup link.';form.hidden=true;}
</script></html>'''


def form_page(title, introduction, fields):
    """Reuse one secret-entry UI for editing and delivery; field definitions are toolkit-owned."""
    markup = ''.join(f'<label for="{html.escape(key)}">{html.escape(label)}</label>'
                     f'<input id="{html.escape(key)}" name="{html.escape(key)}" type="password" autocomplete="off" spellcheck="false" maxlength="4096">'
                     f'<small>{html.escape(help_text)}'
                     + (f' <a href="{html.escape(url, quote=True)}" target="_blank" rel="noreferrer">Open account page ↗</a>' if url else '')
                     + '</small>'
                     for key, label, help_text, url in fields)
    page = PAGE.replace('Connect your editing tools', html.escape(title)).replace(
        'Paste your two keys below. They stay on this Mac and are not sent to your chat. No files to edit.', html.escape(introduction))
    return re.sub(r'(?<=<form id="form">).*?(?=<p>Already connected)', lambda _: markup, page, flags=re.S)


def make_server(root, page=PAGE, saver=save_keys):
    token = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log request bodies, URLs, headers or keys.

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def reply(self, code, body, html=False):
            payload = body.encode() if html else json.dumps({'message': body}).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.headers.get('Host') != self.server.address or self.path != '/':
                self.reply(404, 'Not found.'); return
            self.reply(200, page.replace('NONCE', nonce), html=True)

        def do_POST(self):
            if (self.headers.get('Host') != self.server.address
                    or self.headers.get('Origin') != 'http://' + self.server.address
                    or not secrets.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), ('Bearer ' + token).encode('ascii'))):
                self.reply(403, 'Reopen key setup from your agent.'); return
            if self.path not in ('/save', '/cancel'):
                self.reply(404, 'Not found.'); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    self.reply(400, 'Use the setup form.'); return
                values = json.loads(self.rfile.read(length))
            except (ValueError, TimeoutError):
                self.reply(400, 'Use the setup form.'); return
            if self.path == '/cancel':
                self.server.result = 'cancelled'
                self.reply(200, 'Setup cancelled. Your saved keys are unchanged.'); return
            try:
                saver(root, values)
            except ValueError:
                self.reply(400, 'Check the fields: paste each requested value. Blank keeps an existing value.'); return
            except OSError:
                self.reply(500, 'Could not save locally. Ask your agent to check local file access.'); return
            self.server.result = 'saved'
            self.reply(200, 'Keys saved! You can close this window. Your agent will check the connections next.')

    server = HTTPServer(('127.0.0.1', 0), Handler)
    server.address = '127.0.0.1:' + str(server.server_port)
    server.result = None
    server.timeout = 1
    return server, 'http://' + server.address + '/#' + token


def run_browser(root, page=PAGE, saver=save_keys, no_open=False):
    server, url = make_server(root, page, saver)
    print('Paste your keys into the local setup form, then click Save keys:\n' + url, flush=True)
    try:
        if not no_open:
            try:
                webbrowser.open(url)
            except Exception:
                print('Open the setup link above in your browser.', flush=True)
        deadline = time.monotonic() + 900
        while server.result is None and time.monotonic() < deadline:
            server.handle_request()
        if server.result != 'saved':
            raise ValueError('Key setup cancelled or expired. Rerun credentials to continue.')
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('home', type=Path)
    parser.add_argument('--terminal', action='store_true', help='Optional hidden prompts in an interactive terminal')
    parser.add_argument('--no-open', action='store_true', help='Print setup link without opening browser')
    args = parser.parse_args()
    if args.terminal:
        if not sys.stdin.isatty():
            raise ValueError('Use the default browser form when no interactive terminal is available.')
        save_keys(args.home, {key: getpass.getpass(key + ' (blank keeps current): ') for key in KEYS})
    else:
        run_browser(args.home, no_open=args.no_open)
    print('Keys saved locally with mode 0600. Values were not printed.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyboardInterrupt):
        print('Key setup did not complete. Reopen credentials to retry; existing saved keys are preserved.', file=sys.stderr)
        sys.exit(1)
