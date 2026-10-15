"""Optional real-browser smoke. Start `npm run dev` first.
Install Playwright separately: .venv/bin/pip install playwright==1.55.0
Set CHROMIUM_PATH if Chromium isn't /usr/bin/chromium; no browser download needed here.
This creates one real local project and a free spoken MP4, never uploads it.
"""
import os
from pathlib import Path
import re
import uuid
from playwright.sync_api import sync_playwright, expect


with sync_playwright() as runtime:
    browser = runtime.chromium.launch(
        executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True,
        args=['--no-sandbox'] if os.getenv('HYPE_BROWSER_NO_SANDBOX') == '1' else [])
    page = browser.new_page(viewport={'width': 1500, 'height': 1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    base = 'http://127.0.0.1:' + os.getenv('HYPE_PORT', '8787')
    page.goto(base, wait_until='networkidle')
    title = "Hype Studio — kontrol " + uuid.uuid4().hex[:8]
    page.locator('[data-action="new-project"]').first.click()
    page.locator('#new-title').fill(title)
    page.locator('#new-summary').fill('Bu örnek ücretsiz Türkçe seslendirme ile hazırlandı. Altyazılar ses sürelerine göre oluşturuluyor.')
    page.locator('#new-mode').select_option('template')
    page.locator('#create-project').click()
    expect(page.locator('#edit-title')).to_have_value(title)
    # A new draft must have no pretend /undefined video or subtitle link.
    expect(page.locator('#preview-video')).not_to_have_attribute('src', re.compile('.+'))
    page.locator('#edit-script').fill('Teknoloji haberlerini kısa videolara dönüştürün. Bu örnekte ücretsiz Türkçe yerel seslendirme kullanılıyor.')
    page.locator('#save-project').click()
    expect(page.locator('#save-project')).to_be_enabled()
    page.locator('#render-project').click()
    expect(page.locator('#preview-video')).to_have_attribute('src', re.compile(r'/media/.+\.mp4$'), timeout=60000)
    expect(page.locator('#preview-video')).to_have_js_property('videoWidth', 720, timeout=15000)
    expect(page.locator('#preview-video')).to_have_js_property('videoHeight', 1280)
    media = page.locator('#preview-video').evaluate('(video)=>({src:video.src,duration:video.duration})')
    assert media['duration'] > 1
    # Saving without edits must retain the finished video.
    page.locator('#save-project').click()
    expect(page.locator('#preview-video')).to_have_attribute('src', media['src'])
    page.locator('#edit-description').fill('Güncellenen açıklama. Ücretsiz Türkçe seslendirme örneği.')
    page.locator('#save-project').click()
    expect(page.locator('#save-project')).to_be_enabled()
    expect(page.locator('#preview-video')).to_have_attribute('src', media['src'])
    subtitle = page.locator('#download-subtitles').get_attribute('href')
    response = page.request.get(subtitle)
    assert response.status == 200 and '-->' in response.text()
    target = Path('artifacts')
    target.mkdir(exist_ok=True)
    page.screenshot(path=str(target / 'studio.png'), full_page=True)
    page.locator('#upload-project').click()
    expect(page.locator('#upload-confirm')).not_to_be_checked()
    expect(page.locator('#upload-privacy')).to_have_value('private')
    page.locator('#upload-dialog [data-close-dialog]').first.click()
    # Navigation must preserve edits when the user cancels the discard warning.
    page.locator('#edit-title').fill('Henüz kaydedilmemiş başlık')
    page.locator('[data-view="videos"]').first.click()
    expect(page.locator('#confirm-dialog')).to_be_visible()
    page.locator('#confirm-cancel').click()
    expect(page.locator('#edit-title')).to_have_value('Henüz kaydedilmemiş başlık')
    page.locator('[data-view="videos"]').first.click()
    page.locator('#confirm-accept').click()
    expect(page.locator('#view-videos')).to_be_visible()
    page.locator('#project-search').fill('no-project-with-this-random-title-327817')
    expect(page.locator('.project-card')).to_have_count(0)
    page.locator('#project-search').fill(title)
    page.locator('#project-filter').select_option('ready')
    expect(page.locator('.project-card').first).to_be_visible()
    card = page.locator('.project-card').first
    with page.expect_response(lambda r: r.url.endswith('/duplicate') and r.request.method == 'POST') as copied:
        card.get_by_role('button', name=re.compile('projesini çoğalt$')).click()
    copy = copied.value.json()
    expect(page.locator('#edit-title')).to_have_value(copy['title'])
    expect(page.locator('#preview-video')).not_to_have_attribute('src', re.compile('.+'))
    exported = page.request.get(base + '/api/projects/' + copy['id'] + '/export')
    assert exported.ok and exported.json()['title'] == copy['title']
    assert 'video_path' not in exported.json()
    page.locator('[data-view="videos"]').first.click()
    page.locator('#project-filter').select_option('draft')
    remove = page.get_by_role('button', name=copy['title'] + ' projesini sil', exact=True)
    remove.click()
    page.locator('#confirm-cancel').click()
    expect(remove).to_be_visible()
    remove.click()
    with page.expect_response(lambda r: r.request.method == 'DELETE') as deleted:
        page.locator('#confirm-accept').click()
    assert deleted.value.ok
    expect(remove).to_have_count(0)
    assert page.request.get(base + '/api/projects/' + copy['id']).status == 404
    page.locator('[data-view="settings"]').first.click()
    page.screenshot(path=str(target / 'settings.png'), full_page=True)
    page.locator('[data-view="dashboard"]').first.click()
    page.screenshot(path=str(target / 'dashboard.png'), full_page=True)
    assert not errors, errors
    assert not page.locator('#system-message').is_visible()
    browser.close()
    print('PASS: draft, edit, free voice render, decoded 720x1280 video, SRT, metadata save, upload/discard/delete confirmations, search, duplicate and JSON export. No JavaScript errors.')
