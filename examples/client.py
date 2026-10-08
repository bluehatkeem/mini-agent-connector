#!/usr/bin/env python3
"""Minimal authenticated protocol-v1 client; never automatically retries actions."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8765')
    parser.add_argument('--token-file', type=Path, default=Path('.runtime/device-token'))
    parser.add_argument('--health', action='store_true')
    parser.add_argument('--text', default='Connectivity test: what is two plus two? Do not use tools.')
    parser.add_argument('--pcm', type=Path, help='PCM16LE mono 16kHz, 0.1 to 12 seconds')
    parser.add_argument('--speak', action='store_true', help='Request synthesized audio')
    parser.add_argument('--output', type=Path, help='Save returned PCM audio here')
    args = parser.parse_args()
    if not args.url.startswith('http://'):
        parser.error('Use the trusted-LAN HTTP connector URL')
    token = args.token_file.expanduser().read_text().strip()
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, data=None, voice=False):
        headers = {'Authorization': 'Bearer ' + token,
                   'Content-Type': 'application/octet-stream' if voice else 'application/json',
                   'X-Gero-Speak': str(args.speak).lower()}
        req = urllib.request.Request(args.url.rstrip('/') + path, data=data, headers=headers)
        with http.open(req, timeout=25) as response:
            return response.read()

    if args.health:
        print(request('/health').decode())
        return
    if args.pcm:
        receipt = json.loads(request('/v1/voice', args.pcm.read_bytes(), voice=True))
    else:
        receipt = json.loads(request('/v1/requests', json.dumps({'text': args.text, 'speak': args.speak}).encode()))
    print('Request:', receipt['id'], flush=True)
    deadline = time.monotonic() + 540  # Covers queue, cold STT, agent and synthesis.
    while time.monotonic() < deadline:
        job = json.loads(request('/v1/requests/' + receipt['id']))
        if job['status'] in ('done', 'error'):
            print(json.dumps(job, indent=2))
            if job['status'] == 'error':
                raise SystemExit(1)
            if args.speak and job.get('audio_error'):
                raise SystemExit('Text succeeded, but speech failed')
            if args.output and job.get('pcm_url'):
                args.output.write_bytes(request(job['pcm_url']))
                print('Saved PCM audio')
            return
        time.sleep(1)
    raise SystemExit('Timed out; check action status before resubmitting')


if __name__ == '__main__':
    main()
