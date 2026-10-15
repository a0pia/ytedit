"""User-authorized YouTube OAuth and resumable upload. Tokens stay on this machine."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlencode

import requests

SCOPE = 'https://www.googleapis.com/auth/youtube.upload'


def configured():
    return bool(os.getenv('YOUTUBE_CLIENT_ID') and os.getenv('YOUTUBE_CLIENT_SECRET'))


def redirect_uri():
    return os.getenv('YOUTUBE_REDIRECT_URI', f"http://127.0.0.1:{os.getenv('HYPE_PORT', '8787')}/oauth/youtube/callback")


def authorization_url(state):
    if not configured():
        raise ValueError('YouTube için .env dosyasında YOUTUBE_CLIENT_ID ve YOUTUBE_CLIENT_SECRET ayarlayın. Google Cloud OAuth istemcisi gerekir.')
    return 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({
        'client_id': os.environ['YOUTUBE_CLIENT_ID'], 'redirect_uri': redirect_uri(),
        'response_type': 'code', 'scope': SCOPE, 'access_type': 'offline',
        'prompt': 'consent', 'state': state,
    })


def save_tokens(path, tokens):
    path = Path(path)
    tokens['expires_at'] = time.time() + int(tokens.get('expires_in', 3600)) - 60
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(tokens, stream)
    tmp.replace(path)
    path.chmod(0o600)


def exchange(code, path):
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'code': code, 'client_id': os.environ['YOUTUBE_CLIENT_ID'],
        'client_secret': os.environ['YOUTUBE_CLIENT_SECRET'],
        'redirect_uri': redirect_uri(), 'grant_type': 'authorization_code'}, timeout=(5, 30))
    response.raise_for_status()
    tokens = response.json()
    if not tokens.get('access_token'):
        raise ValueError('Google erişim belirteci döndürmedi.')
    save_tokens(path, tokens)


def access_token(path):
    path = Path(path)
    if not path.exists():
        raise ValueError('Önce Ayarlar bölümünden YouTube hesabını bağlayın.')
    tokens = json.loads(path.read_text())
    if tokens.get('expires_at', 0) > time.time():
        return tokens['access_token']
    if not tokens.get('refresh_token'):
        raise ValueError('YouTube bağlantısının süresi dolmuş; hesabı tekrar bağlayın.')
    response = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id': os.environ['YOUTUBE_CLIENT_ID'], 'client_secret': os.environ['YOUTUBE_CLIENT_SECRET'],
        'refresh_token': tokens['refresh_token'], 'grant_type': 'refresh_token'}, timeout=(5, 30))
    response.raise_for_status()
    updated = response.json()
    updated['refresh_token'] = updated.get('refresh_token', tokens['refresh_token'])
    save_tokens(path, updated)
    return updated['access_token']


def upload(project, path, token_path, privacy='private'):
    if privacy not in {'private', 'unlisted', 'public'}:
        raise ValueError('Geçersiz gizlilik seçimi')
    path = Path(path)
    headers = {'Authorization': 'Bearer ' + access_token(token_path)}
    with requests.Session() as session:
        start = session.post('https://www.googleapis.com/upload/youtube/v3/videos', params={
            'uploadType': 'resumable', 'part': 'snippet,status'}, headers={**headers,
            'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': str(path.stat().st_size)}, json={
            'snippet': {'title': project['title'][:100], 'description': project['description'][:5000],
                        'tags': project.get('tags', [])[:12], 'categoryId': '28'},
            'status': {'privacyStatus': privacy, 'selfDeclaredMadeForKids': False}}, timeout=(5, 30))
        start.raise_for_status()
        location = start.headers.get('Location', '')
        # Only send access tokens to Google's upload host.
        from urllib.parse import urlparse
        if urlparse(location).scheme != 'https' or urlparse(location).hostname not in {'www.googleapis.com', 'upload.youtube.com', 'youtube.googleapis.com'}:
            raise ValueError('Google güvenli bir yükleme adresi döndürmedi.')
        with path.open('rb') as stream:
            response = session.put(location, headers={**headers, 'Content-Type': 'video/mp4',
                                   'Content-Length': str(path.stat().st_size)}, data=stream, timeout=(10, 300))
        response.raise_for_status()
        video_id = response.json().get('id')
        if not video_id:
            raise ValueError('YouTube video kimliği döndürmedi.')
        return {'youtube_id': video_id, 'youtube_url': f'https://www.youtube.com/watch?v={video_id}',
                'uploaded_at': datetime.now(timezone.utc).isoformat(), 'privacy': privacy}
