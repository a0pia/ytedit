"""Local Hype Studio server. Run with: python -m app.server."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlparse
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
import requests
from werkzeug.exceptions import HTTPException

from . import media, news, writing, youtube

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')


def now():
    return datetime.now(timezone.utc).isoformat()


def create_app(data_dir=None, testing=False):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    data = Path(data_dir or os.getenv('HYPE_DATA_DIR', ROOT / 'data')).expanduser().resolve()
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    data.chmod(0o700)
    (data / 'renders').mkdir(exist_ok=True)
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
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='studio')
    jobs_lock = threading.Lock()
    active = set()
    render_slot = threading.Semaphore(1)
    refresh_lock = threading.Lock()
    refresh_time = [0.0]
    oauth_states = {}
    oauth_lock = threading.Lock()
    ollama_cache = {'checked': 0, 'ready': False}

    def connection():
        db = sqlite3.connect(database, timeout=15)
        db.execute('PRAGMA journal_mode=WAL')
        return db

    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))')
        db.execute('CREATE TABLE IF NOT EXISTS activity (id INTEGER PRIMARY KEY, text TEXT, kind TEXT, created TEXT)')
        # A process restart cannot leave jobs pretending to run.
        for pid, body in db.execute("SELECT id,body FROM documents WHERE kind='project'"):
            project = json.loads(body)
            if project.get('status') in {'rendering', 'uploading'}:
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

    @app.before_request
    def local_only():
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
        if isinstance(exc, (ValueError, media.MediaError)):
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
        return jsonify(app='hype-studio', **caps, ai=ollama_cache['ready'],
                       youtube=token_path.exists(), youtube_configured=youtube.configured(),
                       stats={'news': len(all_docs('news')), 'projects': len(projects),
                              'ready': sum(bool(p.get('video_url')) for p in projects)},
                       providers={'tts': caps.get('provider', 'local'), 'ai': 'Şablon / isteğe bağlı Ollama'},
                       configured={'openai': bool(os.getenv('OPENAI_API_KEY')), 'anthropic': bool(os.getenv('ANTHROPIC_API_KEY')),
                                   'elevenlabs': bool(os.getenv('ELEVENLABS_API_KEY') and os.getenv('ELEVENLABS_VOICE_ID'))},
                       warnings=[] if caps.get('tts') else ['Yerel ses motoru bulunamadı. Kurulum kılavuzuna bakın veya sessiz video seçin.'])

    @app.get('/api/activity')
    def activity():
        with connection() as db:
            rows = db.execute('SELECT text,kind,created FROM activity ORDER BY id DESC LIMIT 25').fetchall()
        return jsonify(items=[dict(zip(('text', 'kind', 'created'), row)) for row in rows])

    @app.get('/api/news')
    def news_list():
        return jsonify(items=sorted(all_docs('news'), key=lambda item: item['score'], reverse=True), cached=True,
                       warning='Puanlar güncellik ve anahtar kelimelerden hesaplanır; gerçek izlenme veya doğrulama puanı değildir.')

    @app.post('/api/news/refresh')
    def refresh():
        if not refresh_lock.acquire(blocking=False):
            return jsonify(error='Haber taraması zaten sürüyor.'), 409
        try:
            if time.monotonic() - refresh_time[0] < 30:
                return jsonify(error='Kaynakları korumak için taramalar arasında 30 saniye bekleyin.'), 429
            refresh_time[0] = time.monotonic()
            items, warning = news.fetch_news()
            if items:
                with connection() as db:
                    db.execute("DELETE FROM documents WHERE kind='news'")
                    db.executemany('INSERT INTO documents VALUES(?,?,?)', [('news', item['id'], json.dumps(item, ensure_ascii=False)) for item in items])
                event(f'{len(items)} güncel haber alındı.', 'success')
            else:
                event('RSS kaynaklarından yeni haber alınamadı.', 'warning')
            return jsonify(items=items or all_docs('news'), cached=not bool(items), warning=warning or ('Kaynaklar yanıt vermedi; kayıtlı haberler korunuyor.' if not items else 'Puanlar yaklaşık editoryal sıralamadır.'))
        finally:
            refresh_lock.release()

    @app.get('/api/projects')
    def projects():
        return jsonify(items=all_docs('project'))

    @app.post('/api/projects')
    def create_project():
        fields = body()
        if fields.get('news_id'):
            article = get('news', str(fields['news_id']))
        else:
            title = fields.get('title', '')
            summary = fields.get('summary', '')
            source = fields.get('source', 'Manuel')
            url = fields.get('url', '')
            if not isinstance(title, str) or not title.strip() or len(title) > 300 or not isinstance(summary, str) or len(summary) > 2000:
                raise ValueError('Başlık gerekli (en fazla 300), özet en fazla 2000 karakter olmalı.')
            if not isinstance(url, str) or len(url) > 2000 or (url and urlparse(url).scheme not in {'http', 'https'}):
                raise ValueError('Geçerli bir kaynak bağlantısı kullanın.')
            if not isinstance(source, str) or len(source) > 100:
                raise ValueError('Kaynak en fazla 100 karakter olmalı.')
            article = dict(title=title, summary=summary, source=source, url=url)
        draft = writing.generate(article, fields.get('mode', 'template'))
        validate(draft)
        result = dict(id=uuid.uuid4().hex, **draft, source=article['source'], source_url=article['url'],
                      status='draft', progress=0, created=now(), updated=now(), error=None)
        put('project', result)
        event(f'Taslak oluşturuldu: {result["title"]}', 'success')
        return jsonify(result), 201

    @app.get('/api/projects/<ident>')
    def project_get(ident):
        return jsonify(project(ident))

    @app.patch('/api/projects/<ident>')
    def project_edit(ident):
        fields = validate(body(), partial=True)
        with jobs_lock:
            result = project(ident)
            if ident in active:
                return jsonify(error='İşlem sürerken taslak düzenlenemez.'), 409
            result.update(fields, updated=now())
            if result.get('video_url'):
                # Existing video is explicitly stale after editorial changes.
                for key in ['video_url', 'subtitle_url', 'video_path', 'duration']:
                    result.pop(key, None)
                result['status'] = 'draft'
            put('project', result)
        return jsonify(result)

    def render_job(ident, opts):
        try:
            with render_slot:
                result = project(ident)
                def progress(value):
                    result.update(progress=value, updated=now())
                    put('project', result)
                target = data / 'renders' / ident / uuid.uuid4().hex[:12]
                output = media.render(result, target, opts, progress)
                video = Path(output['video_path']).resolve()
                subtitle = Path(output['subtitle_path']).resolve()
                result.update(status='ready', progress=100, error=None, duration=output['duration'],
                              video_path=str(video), video_url='/media/' + str(video.relative_to(data / 'renders')),
                              subtitle_url='/media/' + str(subtitle.relative_to(data / 'renders')),
                              render_options=opts, updated=now())
                put('project', result)
                event(f'Video hazır: {result["title"]}', 'success')
        except Exception as exc:
            result = get('project', ident)
            message = str(exc) if isinstance(exc, (ValueError, media.MediaError)) else 'Video üretimi başarısız. FFmpeg ve yerel ses motorunu kontrol edin.'
            result.update(status='error', error=message[:500], updated=now())
            put('project', result)
            event(f'Video üretilemedi: {result["title"]}', 'error')
        finally:
            with jobs_lock:
                active.discard(ident)

    @app.post('/api/projects/<ident>/render')
    def render_video(ident):
        opts = body()
        if opts.get('style', 'aurora') not in {'aurora', 'sunset'} or opts.get('tts_provider', 'local') not in {'local', 'elevenlabs'} or not isinstance(opts.get('speech', True), bool):
            raise ValueError('Geçersiz video ayarları')
        opts = {key: opts[key] for key in ('style', 'tts_provider', 'speech') if key in opts}
        with jobs_lock:
            result = project(ident)
            if ident in active:
                return jsonify(error='Bu proje için işlem zaten sürüyor.'), 409
            if len(active) >= 3:
                return jsonify(error='Üretim kuyruğu dolu. Bir işlemin bitmesini bekleyin.'), 429
            active.add(ident)
            result.update(status='rendering', progress=0, error=None)
            put('project', result)
            pool.submit(render_job, ident, opts)
        return jsonify(result), 202

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
        token_path.unlink(missing_ok=True)
        return jsonify(ok=True)

    def upload_job(ident, privacy):
        try:
            result = get('project', ident)
            details = youtube.upload(result, result['video_path'], token_path, privacy)
            result.update(**details, status='ready', error=None, updated=now())
            put('project', result)
            event(f'YouTube yüklemesi tamamlandı: {result["title"]}', 'success')
        except Exception:
            result = get('project', ident)
            result.update(status='ready', error='YouTube yüklemesi doğrulanamadı. Yeniden denemeden önce YouTube Studio kanalını kontrol edin.', updated=now())
            put('project', result)
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
            if ident in active:
                return jsonify(error='Bu proje için işlem sürüyor.'), 409
            if not result.get('video_path') or not Path(result['video_path']).is_file():
                raise ValueError('Önce videoyu üretin.')
            if result.get('youtube_id'):
                return jsonify(error='Bu proje zaten YouTube’a yüklendi. Yeni bir proje oluşturun.'), 409
            active.add(ident)
            result.update(status='uploading', error=None)
            put('project', result)
            pool.submit(upload_job, ident, privacy)
        return jsonify(result), 202

    return app


if __name__ == '__main__':
    # Avoid Werkzeug request logs: OAuth callback URLs contain one-time codes.
    logging.getLogger('werkzeug').disabled = True
    create_app().run(host='127.0.0.1', port=int(os.getenv('HYPE_PORT', '8787')), debug=False, threaded=True)
