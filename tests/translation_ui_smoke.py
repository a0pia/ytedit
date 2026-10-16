"""Optional integration smoke: real UI/backend/media with a local deterministic model fixture.
This validates transport and the workflow, NOT the quality of a real language model.
Requires Playwright and Chromium; never contacts a paid API or uploads to YouTube.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server, WSGIRequestHandler

from app.server import create_app

EN_TITLE = 'New chip cuts energy use by 20 percent'
EN_SUMMARY = 'The company says its new chip uses 20 percent less energy. The results come from internal tests. Independent verification has not yet been published.'
TR_TITLE = 'Yeni çip enerji tüketimini yüzde 20 azaltıyor'
TR_SUMMARY = 'Şirket, yeni çipinin yüzde 20 daha az enerji tükettiğini söylüyor. Sonuçlar şirket içi testlere dayanıyor. Bağımsız doğrulama henüz yayımlanmadı.'
SOURCE = 'https://example.org/translation-fixture'


class ModelFixture(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *_):
        pass

    def respond(self, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.respond({'models': [{'name': 'fixture-model'}]})

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert request['model'] == 'fixture-model'
        assert 'Türkçe' in request['messages'][0]['content']
        payload = json.loads(request['messages'][-1]['content'])
        self.calls.append(payload)
        translated = {'title': TR_TITLE, 'summary': TR_SUMMARY}
        if 'script' in payload:
            translated = {'title': TR_TITLE, 'script': TR_TITLE + '. ' + TR_SUMMARY,
                          'description': 'Türkçe teknoloji haberi.', 'tags': ['Teknoloji', 'Shorts']}
        self.respond({'message': {'content': json.dumps(translated, ensure_ascii=False)}})


class QuietRequest(WSGIRequestHandler):
    def log(self, *_):
        pass


@contextmanager
def running(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def seed_news(data):
    article = {'id': 'translation-fixture', 'title': EN_TITLE, 'summary': EN_SUMMARY, 'url': SOURCE,
               'source': 'Deneme kaynağı', 'published': datetime.now(timezone.utc).isoformat(),
               'score': 75, 'category': 'Teknoloji'}
    with sqlite3.connect(Path(data) / 'studio.sqlite3') as db:
        db.execute('INSERT INTO documents VALUES(?,?,?)', ('news', article['id'], json.dumps(article)))


def run():
    target = Path('artifacts')
    target.mkdir(exist_ok=True)
    model = ThreadingHTTPServer(('127.0.0.1', 0), ModelFixture)
    with running(model), tempfile.TemporaryDirectory(prefix='hype-turkish-ui-') as data, patch.dict(os.environ, {
        'OLLAMA_BASE_URL': f'http://127.0.0.1:{model.server_port}', 'OLLAMA_MODEL': 'fixture-model',
        'OPENAI_API_KEY': '', 'ANTHROPIC_API_KEY': '', 'ELEVENLABS_API_KEY': '', 'ELEVENLABS_VOICE_ID': ''}):
        application = create_app(data)
        seed_news(data)
        service = make_server('127.0.0.1', 0, application, threaded=True, request_handler=QuietRequest)
        with running(service), sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True,
                args=['--no-sandbox'] if os.getenv('HYPE_BROWSER_NO_SANDBOX') == '1' else [])
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            base = f'http://127.0.0.1:{service.server_port}'
            page.goto(base, wait_until='networkidle')
            page.locator('.nav-item[data-view="news"]').click()
            page.locator('.news-card [data-action="translate-news"]').first.click()
            expect(page.locator('#translation-original-title')).to_have_text(EN_TITLE)
            expect(page.locator('#translation-original-summary')).to_have_text(EN_SUMMARY)
            page.locator('#translation-provider').select_option('ollama')
            page.locator('#translate-article').click()
            expect(page.locator('#translation-title')).to_have_value(TR_TITLE, timeout=15000)
            expect(page.locator('#translation-summary')).to_have_value(TR_SUMMARY)
            page.screenshot(path=str(target / 'turkish-translation.png'), full_page=True)
            with page.expect_response(lambda r: r.url.endswith('/api/projects') and r.request.method == 'POST') as created:
                page.locator('#create-translated-project').click()
            project = created.value.json()
            assert created.value.status == 201, project
            assert project['language'] == 'tr' and project['source_url'] == SOURCE
            assert project['translation']['original_title'] == EN_TITLE
            assert project['translation']['original_summary'] == EN_SUMMARY
            expect(page.locator('#edit-title')).to_have_value(TR_TITLE)
            assert TR_SUMMARY in page.locator('#edit-script').input_value()
            page.locator('#video-design').select_option('kinetic')
            page.locator('#render-project').click()
            expect(page.locator('#preview-video')).to_have_attribute('src', re.compile(r'/media/.+\.mp4$'), timeout=90000)
            expect(page.locator('#preview-video')).to_have_js_property('videoWidth', 720, timeout=15000)
            expect(page.locator('#preview-video')).to_have_js_property('videoHeight', 1280)
            result = page.request.get(base + '/api/projects/' + project['id']).json()
            assert result['design'] == 'kinetic' and result['scene_count'] >= 2
            assert result['speech'] and result['language'] == 'tr'
            srt = page.request.get(base + result['subtitle_url']).text()
            assert 'yüzde 20' in ' '.join(srt.split())
            source_video = Path(data) / 'renders' / result['video_url'].removeprefix('/media/')
            shutil.copy2(source_video, target / 'turkish-animated-fixture.mp4')
            page.locator('#preview-video').evaluate('(v)=>{v.muted=true;v.play()}')
            page.wait_for_timeout(1200)
            page.locator('#preview-video').evaluate('(v)=>v.pause()')
            page.screenshot(path=str(target / 'turkish-animated-studio.png'), full_page=True)
            # Existing foreign-language video text can also be translated in place.
            english = page.request.post(base + '/api/projects', data={
                'title': EN_TITLE, 'summary': EN_SUMMARY, 'source': 'Deneme kaynağı', 'url': SOURCE, 'mode': 'template'}).json()
            page.locator('.nav-item[data-view="videos"]').click()
            # The UI refreshes its list on focus; reload once to include the API-created fixture.
            page.reload(wait_until='networkidle')
            page.locator('.nav-item[data-view="videos"]').click()
            page.get_by_role('button', name=EN_TITLE + ' projesini aç', exact=True).click()
            page.locator('#editor-translation-provider').select_option('ollama')
            page.locator('#translate-project').click()
            expect(page.locator('#confirm-dialog')).to_be_visible()
            page.locator('#confirm-accept').click()
            expect(page.locator('#edit-title')).to_have_value(TR_TITLE, timeout=15000)
            translated = page.request.get(base + '/api/projects/' + english['id']).json()
            assert translated['language'] == 'tr' and 'video_url' not in translated
            assert translated['translation']['original_script'].startswith(EN_TITLE)
            assert SOURCE in translated['description']
            browser.close()
            assert ModelFixture.calls and not errors, errors
    print('PASS: foreign news -> local HTTP translation -> Turkish project -> actual kinetic MP4/voice/SRT, plus existing-project translation. Model responses were deterministic fixtures, not a real model quality test.')


if __name__ == '__main__':
    run()
