#!/usr/bin/env python3
"""
Simple server for Statement Organizer dashboard.
Run: python3 serve.py
Then open: http://localhost:3000
"""

import json
import os
import subprocess
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).parent

def get_api_key():
    env_file = BASE_DIR / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith('ANTHROPIC_API_KEY='):
                return line.split('=', 1)[1].strip()
    return os.environ.get('ANTHROPIC_API_KEY', '')

def get_status():
    statements_dir = BASE_DIR / 'Statements'
    logs_dir = statements_dir / 'Logs'
    now = datetime.now()
    this_month = now.strftime('%Y-%m')

    # Find all leaf account folders (Banks / Credit_Cards subfolders)
    account_folders = sorted([
        p for p in statements_dir.rglob('*')
        if p.is_dir() and p.name in ('Banks', 'Credit_Cards')
        and 'Logs' not in p.parts
    ])

    accounts = []
    total_csvs = 0
    for folder in account_folders:
        csvs = sorted(folder.glob('*.csv'), key=lambda f: f.stat().st_mtime, reverse=True)
        rel = str(folder.relative_to(statements_dir))
        label = rel.replace('/', ' › ').replace('_', ' ')
        files = [{'name': f.name, 'mtime': f.stat().st_mtime} for f in csvs]
        total_csvs += len(files)
        accounts.append({'path': rel, 'label': label, 'files': files})

    # Reports and logs this month
    reports_this_month = []
    last_run_ts = None
    if logs_dir.exists():
        for f in sorted(logs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not f.is_file():
                continue
            if this_month in f.name:
                reports_this_month.append(f.name)
            if last_run_ts is None and f.suffix == '.log':
                last_run_ts = f.stat().st_mtime

    # Unprocessed = CSVs modified after the last log run
    unprocessed = sum(
        1 for acc in accounts for f in acc['files']
        if last_run_ts is None or f['mtime'] > last_run_ts
    )

    return {
        'accounts': accounts,
        'total_accounts': len(accounts),
        'accounts_with_files': sum(1 for a in accounts if a['files']),
        'total_csvs': total_csvs,
        'unprocessed': unprocessed,
        'reports_this_month': len(reports_this_month),
        'report_files': reports_this_month,
        'last_run': datetime.fromtimestamp(last_run_ts).strftime('%b %d at %-I:%M %p') if last_run_ts else None,
        'this_month': now.strftime('%B %Y'),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress request logs

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            content = (BASE_DIR / 'statement-dashboard.html').read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)

        elif self.path == '/api/status':
            self.send_json(200, get_status())

        elif self.path == '/api/logs':
            logs_dir = BASE_DIR / 'Statements' / 'Logs'
            files = []
            if logs_dir.exists():
                files = sorted(
                    [f.name for f in logs_dir.iterdir() if f.is_file()],
                    reverse=True
                )
            self.send_json(200, {'files': files})

        elif self.path == '/api/open-statements':
            statements_dir = BASE_DIR / 'Statements'
            statements_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(['open', str(statements_dir)])
            self.send_json(200, {'ok': True})

        elif self.path == '/api/open-reports':
            logs_dir = BASE_DIR / 'Statements' / 'Logs'
            logs_dir.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(['open', str(logs_dir)])
            self.send_json(200, {'ok': True})

        elif self.path.startswith('/api/logs/'):
            filename = Path(self.path[10:]).name  # strip path traversal
            filepath = BASE_DIR / 'Statements' / 'Logs' / filename
            if not filepath.exists():
                self.send_json(404, {'error': 'Not found'})
            else:
                self.send_json(200, {'filename': filename, 'content': filepath.read_text()})

        else:
            self.send_json(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path == '/api/chat':
            api_key = get_api_key()
            if not api_key or api_key == 'your_api_key_here':
                self.send_json(500, {'error': 'ANTHROPIC_API_KEY not set in .env'})
                return

            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))

            payload = json.dumps({
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 1024,
                'system': 'You are a helpful assistant for the Statement Organizer tool. Help users process bank/credit card statements, fix Python script errors, and manage their financial data. Be concise and practical.',
                'messages': body.get('messages', [])
            }).encode()

            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                }
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    self.send_json(200, json.loads(resp.read()))
            except urllib.error.HTTPError as e:
                self.send_json(e.code, json.loads(e.read()))
        else:
            self.send_json(404, {'error': 'Not found'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f'Dashboard running at http://localhost:{port}')
    HTTPServer(('', port), Handler).serve_forever()
