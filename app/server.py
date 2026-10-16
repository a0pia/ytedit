"""Local Hype Studio server. Run with: python -m app.server."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import threading
import time
import unicodedata
from urllib.parse import urlparse
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, Response
import requests
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from . import audio, media, news, presenter, writing, youtube, translation

ROOT = Path(__file__).resolve().parent.parent
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ACTIVE_STATUSES = {'queued', 'rendering', 'uploading', 'translating', 'processing_audio'}
VIDEO_FIELDS = ('video_url', 'subtitle_url', 'video_path', 'duration', 'render_options',
                'provider', 'voice', 'speech', 'subtitle_timing', 'scene_count', 'design')
load_dotenv(ROOT / '.env')


def now():
    return datetime.now(timezone.utc).isoformat()


def script_hash(script):
    normalized = ' '.join(unicodedata.normalize('NFC', script).split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def invalidate_video(value):
    for key in VIDEO_FIELDS:
        value.pop(key, None)
    value.update(status='draft', progress=0, error=None)


def create_app(data_dir=None, testing=False):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    data = Path(data_dir or os.getenv('HYPE_DATA_DIR', ROOT / 'data')).expanduser().resolve()
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    data.chmod(0o700)
    (data / 'renders').mkdir(exist_ok=True)
    (data / 'audio').mkdir(exist_ok=True)
    secret_path = data / '.session-key'
    if not secret_path.exists():
        fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(secrets.token_hex(32))
    app.secret_key = secret_path.read_text().strip()
    app.config.update(TESTING=testing, MAX_CONTENT_LENGTH=64 * 1024,
                      SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_HTTPONLY=True, DATA_DIR=data)
    database = data / 'studio.sqlite3'
    token_path = data / 'youtube-tokens.json'
    pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix='studio')
    jobs_lock = threading.Lock()
    active = set()
    render_slot = threading.Semaphore(1)
    refresh_lock = threading.Lock()
    refresh_time = [0.0]
    oauth_states = {}
    oauth_lock = threading.Lock()
    ollama_cache = {'checked': 0, 'ready': False}
    translation_slots = threading.Semaphore(2)

    @contextmanager
    def connection():
        db = sqlite3.connect(database, timeout=15)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            with db:
                yield db
        finally:
            db.close()

    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))')
        db.execute('CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, text TEXT, kind TEXT, created TEXT)')
        # A process restart cannot leave jobs pretending to run.
        for pid, body in db.execute("SELECT id,body FROM documents WHERE kind='project'"):
            project = json.loads(body)
            if project.get('status') in ACTIVE_STATUSES:
                if project.get('status') == 'uploading':
                    project['upload_uncertain'] = True
                project.update(status='error', error='İşlem uygulama kapandığı için tamamlanamadı. Tekrar deneyin.')
                db.execute("UPDATE documents SET body=? WHERE kind='project' AND id=?", (json.dumps(project), pid))

    def put(kind, doc):
        with connection() as db:
            db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?)', (kind, doc['id'], json.dumps(doc, ensure_ascii=False)))
        return doc

    def get(kind, ident):
        with connection() as db:
            row = db.execute('SELECT body FROM documents WHERE kind=? AND id=?', (kind, ident)).fetchone()
        if not row:
            raise ValueError('Kayıt bulunamadı')
        return json.loads(row[0])

    def all_docs(kind):
        with connection() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM documents WHERE kind=? ORDER BY rowid DESC', (kind,))]

    def audio_file(value):
        """Only a canonical file owned by this project may be streamed or rendered."""
        ident, stored = value.get('id', ''), value.get('audio_path')
        if not re.fullmatch(r'[a-f0-9]{32}', ident) or not isinstance(stored, str):
            return None
        base = data / 'audio' / ident
        candidate = Path(stored)
        try:
            relative = candidate.relative_to(base)
            if len(relative.parts) != 2 or not re.fullmatch(r'[a-f0-9]{32}', relative.parts[0]) or relative.name != 'audio.wav':
                return None
            if any(path.is_symlink() for path in (data / 'audio', base, candidate.parent, candidate)):
                return None
            if candidate.is_file() and candidate.resolve().is_relative_to(base.resolve()):
                return candidate
        except (OSError, ValueError):
            pass
        return None

    def valid_audio(value):
        metadata = value.get('audio')
        return (isinstance(metadata, dict) and metadata.get('script_hash') == script_hash(value['script'])
                and audio_file(value) is not None)

    def public_project(value):
        result = {key: item for key, item in value.items() if key not in
                  {'video_path', 'audio_path', 'audio_captions', 'audio_timing_mode'}}
        if isinstance(value.get('audio'), dict):
            result['audio'] = {**value['audio'], 'valid': valid_audio(value),
                               'url': f'/api/projects/{value["id"]}/audio/file'}
        return result

    def remove_owned_directory(target):
        # Never follow stored paths or directory symlinks when removing assets.
        if target.parent.is_symlink():
            raise ValueError('Dosya dizini güvenli değil.')
        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)

    def cached_news():
        result = []
        for item in all_docs('news'):
            stamp = item.get('published') or item.get('fetched_at')
            try:
                date = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - date).total_seconds() > 7 * 86400:
                    continue
            except (ValueError, TypeError, AttributeError):
                continue
            result.append(item)
        return sorted(result, key=lambda item: item['score'], reverse=True)

    def news_state():
        try:
            return get('meta', 'news-refresh')
        except ValueError:
            return {'sources': [{'source': name, 'status': 'unknown', 'count': 0, 'error': None} for name, _ in news.FEEDS],
                    'last_refreshed': None}

    def event(text, kind='info'):
        with connection() as db:
            db.execute('INSERT INTO activity(text,kind,created) VALUES(?,?,?)', (text, kind, now()))
            db.execute('DELETE FROM activity WHERE id NOT IN (SELECT id FROM activity ORDER BY id DESC LIMIT 100)')

    def project(ident):
        try:
            return get('project', ident)
        except ValueError:
            from flask import abort
            abort(404, description='Proje bulunamadı')

    def is_busy(ident):
        return ident in active or project(ident).get('status') in ACTIVE_STATUSES

    def body():
        if not request.is_json:
            raise ValueError('JSON gövdesi gerekli')
        value = request.get_json()
        if not isinstance(value, dict):
            raise ValueError('JSON nesnesi gerekli')
        return value

    def validate(fields, partial=False):
        result = {}
        for name, maximum in [('title', 100), ('script', 1200), ('description', 4500)]:
            if name not in fields:
                if not partial:
                    raise ValueError(f'{name} alanı gerekli')
                continue
            value = fields[name]
            if not isinstance(value, str) or len(value) > maximum or (name in {'title', 'script'} and not value.strip()):
                raise ValueError(f'{name} metin olmalı; en fazla {maximum} karakter.')
            result[name] = value.strip()
        if 'tags' in fields:
            tags = fields['tags']
            if not isinstance(tags, list) or len(tags) > 12 or any(not isinstance(t, str) or not t.strip() or len(t) > 60 for t in tags) or sum(map(len, tags)) > 450:
                raise ValueError('En fazla 12 etiket, toplam 450 karakter kullanın.')
            result['tags'] = tags
        return result

    def article_input(fields):
        if fields.get('news_id'):
            return get('news', str(fields['news_id']))
        title, summary = fields.get('title', ''), fields.get('summary', '')
        source, url = fields.get('source', 'Manuel'), fields.get('url', '')
        if not isinstance(title, str) or not title.strip() or len(title) > 300 or not isinstance(summary, str) or len(summary) > 2000:
            raise ValueError('Başlık gerekli (en fazla 300), özet en fazla 2000 karakter olmalı.')
        if not isinstance(url, str) or len(url) > 2000 or (url and not news.canonical_url(url)):
            raise ValueError('Geçerli bir kaynak bağlantısı kullanın.')
        if not isinstance(source, str) or len(source) > 100:
            raise ValueError('Kaynak en fazla 100 karakter olmalı.')
        return dict(title=title.strip(), summary=summary.strip(), source=source, url=url)

    @app.before_request
    def local_only():
        # Multipart audio gets a separate limit; JSON requests remain capped at 64 KiB.
        if request.method == 'POST' and re.fullmatch(r'/api/projects/[a-f0-9]{32}/audio', request.path):
            request.max_content_length = MAX_UPLOAD_BYTES + 64 * 1024
            request.max_form_parts = 4
        if app.testing:
            return
        # Block DNS rebinding and cross-origin writes to the local API.
        if request.host.split(':')[0] not in {'127.0.0.1', 'localhost'}:
            return jsonify(error='Yalnızca yerel bağlantıya izin verilir.'), 403
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} or request.path == '/api/youtube/connect':
            origin = request.headers.get('Origin')
            if origin and (urlparse(origin).scheme != 'http' or urlparse(origin).netloc != request.host):
                return jsonify(error='Geçersiz istek kaynağı.'), 403
            if request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify(error='Siteler arası isteğe izin verilmedi.'), 403

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        if request.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, (ValueError, media.MediaError, audio.AudioError)):
            return jsonify(error=str(exc)), 400
        if isinstance(exc, requests.RequestException):
            # Request URLs and response bodies can contain credentials. Never echo them.
            code = getattr(getattr(exc, 'response', None), 'status_code', None)
            return jsonify(error=f'Dış servise erişilemedi{f" (HTTP {code})" if code else ""}. Bağlantıyı ve sağlayıcı ayarlarını kontrol edin.'), 502
        logging.error('Request failed: %s', type(exc).__name__)
        return jsonify(error='İşlem tamamlanamadı. Ayarları ve giriş metnini kontrol edin.'), 500

    @app.get('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    @app.get('/api/status')
    def status():
        caps = media.capabilities()
        projects = all_docs('project')
        if time.monotonic() - ollama_cache['checked'] > 15:
            try:
                response = requests.get(os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/') + '/api/tags', timeout=(0.3, 0.5))
                response.raise_for_status()
                models = [item.get('name') for item in response.json().get('models', [])]
                ollama_cache['ready'] = os.getenv('OLLAMA_MODEL', 'llama3.2:3b') in models
            except (requests.RequestException, ValueError, TypeError):
                ollama_cache['ready'] = False
            ollama_cache['checked'] = time.monotonic()
        return jsonify(app='hype-studio', api_version=4, app_version='0.4.0', project_root=str(ROOT), data_dir=str(data),
                       **caps, ai=ollama_cache['ready'],
                       audio_upload={'formats': ['mp3', 'wav'], 'max_bytes': MAX_UPLOAD_BYTES,
                                     'max_duration': audio.MAX_DURATION, 'subtitle_timing': 'estimated'},
                       youtube=token_path.exists() and youtube.configured(), youtube_configured=youtube.configured(),
                       stats={'news': len(cached_news()), 'projects': len(projects),
                              'ready': sum(p.get('status') == 'ready' and bool(p.get('video_url')) for p in projects),
                              'active': sum(p.get('status') in ACTIVE_STATUSES for p in projects)},
                       translation={'target_language': 'tr', 'default_provider': 'ollama',
                                    'providers': {'ollama': ollama_cache['ready'], 'openai': bool(os.getenv('OPENAI_API_KEY')),
                                                  'anthropic': bool(os.getenv('ANTHROPIC_API_KEY'))},
                                    'model': os.getenv('OLLAMA_MODEL', 'llama3.2:3b'),
                                    'setup_commands': ['brew install ollama', 'brew services start ollama',
                                                       'ollama pull ' + os.getenv('OLLAMA_MODEL', 'llama3.2:3b')]},
                       providers={'tts': caps.get('provider', 'local'), 'ai': 'Şablon / isteğe bağlı Ollama'},
                       configured={'openai': bool(os.getenv('OPENAI_API_KEY')), 'anthropic': bool(os.getenv('ANTHROPIC_API_KEY')),
                                   'elevenlabs': bool(os.getenv('ELEVENLABS_API_KEY') and os.getenv('ELEVENLABS_VOICE_ID'))},
                       warnings=([caps.get('ffmpeg_error') or 'FFmpeg kurulumu gerekli.'] if not caps.get('ffmpeg') else [])
                       + ([caps.get('tts_error') or 'Yerel ses motoru bulunamadı. Hazır ses dosyası yükleyebilir veya sessiz video seçebilirsiniz.'] if not caps.get('tts') else []))

    @app.get('/api/activity')
    def activity():
        with connection() as db:
            rows = db.execute('SELECT text,kind,created FROM activity ORDER BY id DESC LIMIT 25').fetchall()
        return jsonify(items=[dict(zip(('text', 'kind', 'created'), row)) for row in rows])

    @app.get('/api/news')
    def news_list():
        state = news_state()
        return jsonify(items=cached_news(), cached=True, sources=state['sources'], last_refreshed=state['last_refreshed'],
                       warning='Puanlar güncellik ve anahtar kelimelerden hesaplanır; gerçek izlenme veya doğrulama puanı değildir.')

    @app.post('/api/news/refresh')
    def refresh():
        if not refresh_lock.acquire(blocking=False):
            return jsonify(error='Haber taraması zaten sürüyor.'), 409
        try:
            if time.monotonic() - refresh_time[0] < 30:
                return jsonify(error='Kaynakları korumak için taramalar arasında 30 saniye bekleyin.'), 429
            refresh_time[0] = time.monotonic()
            fetched = news.fetch_news_detailed()
            items, warning, sources = fetched['items'], fetched['warning'], fetched['sources']
            successful = {entry['source'] for entry in sources if entry['status'] == 'ok'}
            retained = [item for item in cached_news() if item['source'] not in successful]
            merged = {item['id']: item for item in retained}
            merged.update({item['id']: item for item in items})
            refreshed = now()
            with connection() as db:
                db.execute("DELETE FROM documents WHERE kind='news'")
                db.executemany('INSERT INTO documents VALUES(?,?,?)', [('news', item['id'], json.dumps(item, ensure_ascii=False)) for item in merged.values()])
                db.execute('INSERT OR REPLACE INTO documents VALUES(?,?,?)', ('meta', 'news-refresh', json.dumps(
                    {'id': 'news-refresh', 'sources': sources, 'last_refreshed': refreshed}, ensure_ascii=False)))
            if items:
                event(f'{len(items)} güncel haber alındı.', 'success')
            else:
                event('RSS kaynaklarından yeni haber alınamadı.', 'warning')
            return jsonify(items=cached_news(), cached=bool(retained), sources=sources, last_refreshed=refreshed,
                           warning=warning or ('Kaynaklar güncel haber döndürmedi.' if not items else 'Puanlar yaklaşık editoryal sıralamadır.'))
        finally:
            refresh_lock.release()

    @app.get('/api/projects')
    def projects():
        values = all_docs('project')
        search = request.args.get('search', '').strip().casefold()
        status = request.args.get('status', 'all')
        if status not in {'all', 'draft', 'queued', 'rendering', 'ready', 'error', 'uploading', 'uploaded', 'translating', 'processing_audio'}:
            raise ValueError('Geçersiz proje durumu')
        if search:
            values = [p for p in values if search in ' '.join(str(p.get(key, '')) for key in ('title', 'script', 'source')).casefold()]
        if status == 'uploaded':
            values = [p for p in values if p.get('youtube_id')]
        elif status != 'all':
            values = [p for p in values if p.get('status') == status and (status != 'ready' or not p.get('youtube_id'))]
        return jsonify(items=[public_project(p) for p in values])

    @app.post('/api/translate')
    def translate_article():
        fields = body()
        article = article_input(fields)
        provider = translation.provider_name(fields.get('provider', 'ollama'))
        if not translation_slots.acquire(blocking=False):
            return jsonify(error='Çeviri işlemleri dolu. Devam eden çevirinin bitmesini bekleyin.'), 429
        try:
            result = translation.translate_article(article, provider)
            event(f'Haber Türkçeye çevrildi: {result["title"]}', 'success')
            return jsonify(result)
        finally:
            translation_slots.release()

    @app.post('/api/projects')
    def create_project():
        fields = body()
        article = article_input(fields)
        mode = fields.get('mode', 'template')
        language = fields.get('language', 'tr' if mode != 'template' else 'original')
        if not isinstance(language, str) or language not in {'tr', 'original'}:
            raise ValueError('İçerik dili Türkçe veya kaynak dili olmalı.')
        translated = None
        if 'translation' in fields:
            if fields.get('news_id') or language != 'tr':
                raise ValueError('Çevrilen metni Türkçe içerik olarak gönderin; kaynak haber kimliğiyle özgün metni geri yüklemeyin.')
            translated = translation.metadata(fields['translation'])
        draft = writing.generate(article, mode)
        validate(draft)
        result = dict(id=uuid.uuid4().hex, **draft, source=article['source'], source_url=article['url'], language=language,
                      status='draft', progress=0, created=now(), updated=now(), error=None)
        if translated:
            result.update(translation=translated, editorial_note='Türkçe çeviri taslağı. Kaynak metinle karşılaştırın; Türkçe ses ve altyazı bu metinden üretilir.')
        put('project', result)
        event(f'Taslak oluşturuldu: {result["title"]}', 'success')
        return jsonify(public_project(result)), 201

    @app.get('/api/projects/<ident>')
    def project_get(ident):
        return jsonify(public_project(project(ident)))

    @app.get('/api/projects/<ident>/script')
    def download_script(ident):
        result = project(ident)
        return Response(result['script'], content_type='text/plain; charset=utf-8', headers={
            'Content-Disposition': f'attachment; filename="hype-script-{result["id"]}.txt"'})

    @app.get('/api/projects/<ident>/audio/file')
    def stream_audio(ident):
        path = audio_file(project(ident))
        if path is None:
            from flask import abort
            abort(404, description='Ses dosyası bulunamadı.')
        return send_from_directory(path.parent, path.name, mimetype='audio/wav', conditional=True)

    @app.post('/api/projects/<ident>/audio')
    def upload_audio(ident):
        with jobs_lock:
            original = project(ident)
            if is_busy(ident):
                return jsonify(error='İşlem sürerken ses dosyası değiştirilemez.'), 409
            if len(active) >= 3:
                return jsonify(error='İşlem kuyruğu dolu. Bir işlemin bitmesini bekleyin.'), 429
            active.add(ident)
            put('project', {**original, 'status': 'processing_audio', 'error': None})
        version = None
        try:
            uploaded = request.files.get('file')
            if uploaded is None or not uploaded.filename:
                raise ValueError('MP3 veya WAV ses dosyası seçin.')
            filename = secure_filename(uploaded.filename.replace('\\', '/').split('/')[-1])
            extension = Path(filename).suffix.lower()
            if extension not in {'.mp3', '.wav'}:
                raise ValueError('Yalnızca MP3 veya WAV dosyası yükleyin.')
            base = data / 'audio' / ident
            if (data / 'audio').is_symlink() or base.is_symlink():
                raise ValueError('Ses dosyası dizini güvenli değil.')
            base.mkdir(mode=0o700, exist_ok=True)
            version = base / uuid.uuid4().hex
            version.mkdir(mode=0o700)
            raw = version / ('input' + extension)
            size = 0
            with raw.open('xb') as output:
                while chunk := uploaded.stream.read(64 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        from flask import abort
                        abort(413, description='Ses dosyası en fazla 25 MB olabilir.')
                    output.write(chunk)
            if not size:
                raise ValueError('Ses dosyası boş olamaz.')
            canonical = version / 'audio.wav'
            duration = audio.normalize_audio(raw, canonical)
            captions = audio.plan_captions(original['script'], canonical)
            raw.unlink()
            result = {**original, 'audio_path': str(canonical), 'updated': now(), 'audio': {
                'filename': filename, 'duration': duration, 'uploaded_at': now(),
                'script_hash': script_hash(original['script']), 'captions': captions, 'timing_mode': 'estimated'}}
            invalidate_video(result)
            with jobs_lock:
                put('project', result)
                active.discard(ident)
        except Exception:
            if version is not None:
                shutil.rmtree(version, ignore_errors=True)
            with jobs_lock:
                put('project', original)
                active.discard(ident)
            raise
        finally:
            with jobs_lock:
                active.discard(ident)
        old = audio_file(original)
        if old and old != canonical:
            try:
                remove_owned_directory(old.parent)
            except OSError:
                logging.warning('Previous audio asset could not be removed')
        event(f'Ses dosyası eklendi: {result["title"]}', 'success')
        return jsonify(public_project(result))

    @app.delete('/api/projects/<ident>/audio')
    def delete_audio(ident):
        with jobs_lock:
            result = project(ident)
            if is_busy(ident):
                return jsonify(error='İşlem sürerken ses dosyası silinemez.'), 409
            remove_owned_directory(data / 'audio' / ident)
            result.pop('audio', None)
            result.pop('audio_path', None)
            if result.get('render_options', {}).get('tts_provider') == 'uploaded':
                invalidate_video(result)
            result['updated'] = now()
            put('project', result)
        return jsonify(public_project(result))

    @app.patch('/api/projects/<ident>/audio/timings')
    def edit_audio_timings(ident):
        fields = body()
        with jobs_lock:
            result = project(ident)
            if is_busy(ident):
                return jsonify(error='İşlem sürerken altyazı zamanları değiştirilemez.'), 409
            if not valid_audio(result):
                raise ValueError('Önce güncel senaryoya uygun ses dosyası yükleyin.')
            duration = audio.inspect_audio(audio_file(result))['duration']
            captions = audio.validate_captions(fields.get('captions'), result['script'], duration)
            result['audio'] = {**result['audio'], 'captions': captions, 'timing_mode': 'manual', 'duration': duration}
            if result.get('render_options', {}).get('tts_provider') == 'uploaded':
                invalidate_video(result)
            result['updated'] = now()
            put('project', result)
        return jsonify(public_project(result))

    @app.post('/api/projects/<ident>/translate')
    def translate_existing_project(ident):
        fields = body()
        provider = translation.provider_name(fields.get('provider', 'ollama'))
        with jobs_lock:
            original = project(ident)
            if is_busy(ident):
                return jsonify(error='İşlem sürerken proje çevrilemez.'), 409
            if original.get('youtube_id'):
                return jsonify(error='Yayımlanmış videoyu korumak için önce projeyi çoğaltın, ardından kopyayı Türkçeye çevirin.'), 409
            if len(active) >= 3 or not translation_slots.acquire(blocking=False):
                return jsonify(error='Çeviri kuyruğu dolu. Bir işlemin bitmesini bekleyin.'), 429
            active.add(ident)
            put('project', {**original, 'status': 'translating', 'error': None})
        try:
            translated = translation.translate_project(original, provider)
            validate(translated)
            result = {**original, **translated, 'status': 'draft', 'progress': 0, 'error': None, 'updated': now()}
            for key in ('video_url', 'subtitle_url', 'video_path', 'duration', 'render_options', 'provider',
                        'voice', 'speech', 'subtitle_timing', 'scene_count', 'design'):
                result.pop(key, None)
            with jobs_lock:
                put('project', result)
                active.discard(ident)
            event(f'Video metinleri Türkçeye çevrildi: {result["title"]}', 'success')
            return jsonify(public_project(result))
        except Exception:
            with jobs_lock:
                put('project', original)
                active.discard(ident)
            raise
        finally:
            translation_slots.release()

    @app.patch('/api/projects/<ident>')
    def project_edit(ident):
        fields = validate(body(), partial=True)
        with jobs_lock:
            result = project(ident)
            if is_busy(ident):
                return jsonify(error='İşlem sürerken taslak düzenlenemez.'), 409
            changed = any(result.get(key) != value for key, value in fields.items())
            changes_video = any(key in fields and result.get(key) != fields[key] for key in ('title', 'script'))
            result.update(fields)
            if changed:
                result['updated'] = now()
            if changes_video:
                for key in ['video_url', 'subtitle_url', 'video_path', 'duration', 'render_options',
                            'provider', 'voice', 'speech', 'subtitle_timing', 'scene_count', 'design']:
                    result.pop(key, None)
                result['status'] = 'draft'
                result['progress'] = 0
            put('project', result)
        return jsonify(public_project(result))

    @app.post('/api/projects/<ident>/duplicate')
    def duplicate_project(ident):
        original = project(ident)
        keys = ('title', 'script', 'description', 'tags', 'source', 'source_url', 'generation_mode', 'editorial_note', 'language', 'translation')
        result = {key: original[key] for key in keys if key in original}
        result.update(id=uuid.uuid4().hex, title=original['title'][:90] + ' — kopya', status='draft',
                      progress=0, error=None, created=now(), updated=now())
        put('project', result)
        event(f'Proje kopyalandı: {result["title"]}', 'success')
        return jsonify(public_project(result)), 201

    @app.get('/api/projects/<ident>/export')
    def export_project(ident):
        original = project(ident)
        keys = ('id', 'title', 'script', 'description', 'tags', 'source', 'source_url', 'generation_mode',
                'editorial_note', 'created', 'updated', 'language', 'translation')
        export = {key: original[key] for key in keys if key in original}
        export['schema_version'] = 1
        return Response(json.dumps(export, ensure_ascii=False, indent=2), content_type='application/json; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="hype-project-{original["id"]}.json"'})

    @app.delete('/api/projects/<ident>')
    def delete_project(ident):
        with jobs_lock:
            result = project(ident)
            if is_busy(ident):
                return jsonify(error='İşlem sürerken proje silinemez.'), 409
            if not re.fullmatch(r'[a-f0-9]{32}', ident):
                raise ValueError('Geçersiz proje kimliği')
            # Never trust stored video_path for deletion and never follow a symlink.
            for kind in ('renders', 'audio'):
                remove_owned_directory(data / kind / ident)
            with connection() as db:
                db.execute("DELETE FROM documents WHERE kind='project' AND id=?", (ident,))
            event(f'Proje silindi: {result["title"]}')
        return jsonify(ok=True)

    def render_job(ident, opts):
        try:
            with render_slot:
                result = project(ident)
                result.update(status='rendering', updated=now())
                put('project', result)
                def progress(value):
                    result.update(progress=value, updated=now())
                    put('project', result)
                target = data / 'renders' / ident / uuid.uuid4().hex[:12]
                render_input = dict(result)
                if opts.get('tts_provider') == 'uploaded':
                    render_input.update(audio_path=str(audio_file(result)),
                                        audio_captions=result['audio']['captions'],
                                        audio_timing_mode=result['audio']['timing_mode'])
                output = media.render(render_input, target, opts, progress)
                video = Path(output['video_path']).resolve()
                subtitle = Path(output['subtitle_path']).resolve()
                result.update({key: output[key] for key in ('provider', 'voice', 'speech', 'subtitle_timing', 'scene_count', 'design') if key in output})
                result.update(status='ready', progress=100, error=None, duration=output['duration'],
                              video_path=str(video), video_url='/media/' + str(video.relative_to(data / 'renders')),
                              subtitle_url='/media/' + str(subtitle.relative_to(data / 'renders')),
                              render_options=opts, updated=now())
                with jobs_lock:
                    put('project', result)
                    active.discard(ident)
                event(f'Video hazır: {result["title"]}', 'success')
        except Exception as exc:
            result = get('project', ident)
            message = str(exc) if isinstance(exc, (ValueError, media.MediaError, audio.AudioError)) else 'Video üretimi başarısız. FFmpeg ve ses dosyasını kontrol edin.'
            result.update(status='error', error=message[:500], updated=now())
            with jobs_lock:
                put('project', result)
                active.discard(ident)
            event(f'Video üretilemedi: {result["title"]}', 'error')
        finally:
            with jobs_lock:
                active.discard(ident)

    @app.post('/api/projects/<ident>/render')
    def render_video(ident):
        opts = body()
        if opts.get('style', 'aurora') not in {'aurora', 'sunset'} or opts.get('tts_provider', 'local') not in {'local', 'elevenlabs', 'uploaded'} or not isinstance(opts.get('speech', True), bool):
            raise ValueError('Geçersiz video ayarları')
        if 'speech_rate' in opts and (isinstance(opts['speech_rate'], bool) or not isinstance(opts['speech_rate'], int) or not 100 <= opts['speech_rate'] <= 240):
            raise ValueError('Konuşma hızı 100 ile 240 arasında olmalı.')
        if opts.get('video_design', 'kinetic') not in {'kinetic', 'host', 'classic'}:
            raise ValueError('Video tasarımı anlatıcılı, animasyonlu sahneler veya klasik olmalı.')
        if opts.get('host_look', 'nova') not in presenter.LOOKS:
            raise ValueError('Geçersiz anlatıcı karakteri.')
        if not isinstance(opts.get('host_name', ''), str) or len(opts.get('host_name', '')) > presenter.MAX_NAME:
            raise ValueError(f'Anlatıcı adı en fazla {presenter.MAX_NAME} karakter olabilir.')
        opts = {key: opts[key] for key in ('style', 'tts_provider', 'speech', 'speech_rate', 'video_design',
                                           'host_look', 'host_name') if key in opts}
        with jobs_lock:
            result = project(ident)
            if is_busy(ident):
                return jsonify(error='Bu proje için işlem zaten sürüyor.'), 409
            if len(active) >= 3:
                return jsonify(error='Üretim kuyruğu dolu. Bir işlemin bitmesini bekleyin.'), 429
            if opts.get('tts_provider') == 'uploaded':
                if not opts.get('speech', True):
                    raise ValueError('Yüklenen ses için seslendirme açık olmalı.')
                if not valid_audio(result):
                    raise ValueError('Güncel senaryoyu seslendirip MP3 veya WAV olarak yükleyin. Metin değiştiyse yeni kayıt gerekli.')
                duration = audio.inspect_audio(audio_file(result))['duration']
                audio.validate_captions(result['audio'].get('captions'), result['script'], duration)
            active.add(ident)
            result.update(status='queued', progress=0, error=None)
            put('project', result)
            pool.submit(render_job, ident, opts)
        return jsonify(public_project(result)), 202

    @app.get('/media/<path:filename>')
    def media_file(filename):
        if Path(filename).suffix.lower() not in {'.mp4', '.srt'}:
            from flask import abort
            abort(404)
        return send_from_directory(data / 'renders', filename, conditional=True)

    @app.get('/api/youtube/connect')
    def connect():
        state = secrets.token_urlsafe(32)
        url = youtube.authorization_url(state)
        # The desktop app opens Google in the system browser, with a separate cookie jar.
        # Keep an expiring, single-use nonce in this local server instead of a session cookie.
        with oauth_lock:
            expired = [key for key, started in oauth_states.items() if time.time() - started > 600]
            for key in expired:
                oauth_states.pop(key, None)
            oauth_states[state] = time.time()
        return jsonify(url=url)

    @app.get('/oauth/youtube/callback')
    def callback():
        state = request.args.get('state', '')
        with oauth_lock:
            started = oauth_states.pop(state, 0)
        if not state or not started or time.time() - started > 600:
            return 'Bağlantı isteği geçersiz veya süresi dolmuş. Uygulamadan yeniden deneyin.', 400
        if request.args.get('error') or not request.args.get('code'):
            return 'YouTube bağlantısı tamamlanmadı. Bu pencereyi kapatabilirsiniz.', 400
        youtube.exchange(request.args['code'], token_path)
        event('YouTube hesabı bağlandı.', 'success')
        return '<!doctype html><html lang="tr"><meta charset="utf-8"><title>Hype Studio</title><p>YouTube bağlandı. Uygulamaya dönebilirsiniz.</p></html>'

    @app.post('/api/youtube/disconnect')
    def disconnect():
        with jobs_lock:
            if any(get('project', ident).get('status') == 'uploading' for ident in active):
                return jsonify(error='Yükleme sürerken hesap bağlantısı kaldırılamaz.'), 409
        token_path.unlink(missing_ok=True)
        return jsonify(ok=True)

    def upload_job(ident, privacy):
        try:
            result = get('project', ident)
            details = youtube.upload(result, result['video_path'], token_path, privacy)
            result.update(**details, status='ready', error=None, upload_uncertain=False, updated=now())
            with jobs_lock:
                put('project', result)
                active.discard(ident)
            event(f'YouTube yüklemesi tamamlandı: {result["title"]}', 'success')
        except Exception:
            result = get('project', ident)
            result.update(status='ready', upload_uncertain=True,
                          error='YouTube yüklemesi doğrulanamadı. Yeniden denemeden önce YouTube Studio kanalını kontrol edin.', updated=now())
            with jobs_lock:
                put('project', result)
                active.discard(ident)
            event('YouTube yüklemesi doğrulanamadı; kanalınızı kontrol edin.', 'error')
        finally:
            with jobs_lock:
                active.discard(ident)

    @app.post('/api/projects/<ident>/upload')
    def upload_video(ident):
        opts = body()
        if opts.get('confirm') is not True:
            raise ValueError('Yükleme için açık onay gerekli.')
        privacy = opts.get('privacy', 'private')
        if privacy not in {'private', 'unlisted', 'public'}:
            raise ValueError('Geçersiz gizlilik seçimi')
        if not token_path.exists() or not youtube.configured():
            raise ValueError('Önce YouTube hesabınızı bağlayın.')
        with jobs_lock:
            result = project(ident)
            if is_busy(ident):
                return jsonify(error='Bu proje için işlem sürüyor.'), 409
            if len(active) >= 3:
                return jsonify(error='İşlem kuyruğu dolu. Bir işlemin bitmesini bekleyin.'), 429
            if result.get('upload_uncertain') and opts.get('retry_confirmed') is not True:
                return jsonify(error='Önce YouTube Studio kanalını kontrol edin. Tekrar yükleme için ayrıca onay gerekli.',
                               requires_retry_confirmation=True), 409
            if not result.get('video_path') or not Path(result['video_path']).is_file():
                raise ValueError('Önce videoyu üretin.')
            if result.get('youtube_id'):
                return jsonify(error='Bu proje zaten YouTube’a yüklendi. Yeni bir proje oluşturun.'), 409
            active.add(ident)
            result.update(status='uploading', error=None)
            put('project', result)
            pool.submit(upload_job, ident, privacy)
        return jsonify(public_project(result)), 202

    return app


if __name__ == '__main__':
    # Avoid Werkzeug request logs: OAuth callback URLs contain one-time codes.
    logging.getLogger('werkzeug').disabled = True
    create_app().run(host='127.0.0.1', port=int(os.getenv('HYPE_PORT', '8787')), debug=False, threaded=True)
