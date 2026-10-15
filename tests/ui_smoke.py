"""Optional real-browser smoke. Start `npm run dev` first.
Install Playwright separately: .venv/bin/pip install playwright==1.55.0
Set CHROMIUM_PATH if Chromium isn't /usr/bin/chromium; no browser download needed here.
This creates one real local project and a free spoken MP4, never uploads it.
"""
import os
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect


with sync_playwright() as runtime:
    browser = runtime.chromium.launch(
        executable_path=os.getenv('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True,
        args=['--no-sandbox'] if os.getenv('HYPE_BROWSER_NO_SANDBOX') == '1' else [])
    page = browser.new_page(viewport={'width': 1500, 'height': 1000}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('http://127.0.0.1:' + os.getenv('HYPE_PORT', '8787'), wait_until='networkidle')
    page.locator('[data-action="new-project"]').first.click()
    page.locator('#new-title').fill('Hype Studio — arayüz doğrulaması')
    page.locator('#new-summary').fill('Bu örnek ücretsiz Türkçe seslendirme ile hazırlandı. Altyazılar ses sürelerine göre oluşturuluyor.')
    page.locator('#new-mode').select_option('template')
    page.locator('#create-project').click()
    expect(page.locator('#edit-title')).to_have_value('Hype Studio — arayüz doğrulaması')
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
    page.locator('[data-view="videos"]').first.click()
    assert page.locator('.project-card').count() >= 1
    page.locator('[data-view="settings"]').first.click()
    page.screenshot(path=str(target / 'settings.png'), full_page=True)
    page.locator('[data-view="dashboard"]').first.click()
    page.screenshot(path=str(target / 'dashboard.png'), full_page=True)
    assert not errors, errors
    assert not page.locator('#system-message').is_visible()
    browser.close()
    print('PASS: draft, edit, free voice render, decoded 720x1280 video, SRT, unchanged save, upload confirmation, navigation. No JavaScript errors.')
