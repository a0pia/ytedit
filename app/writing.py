"""Explicit optional AI providers; the default template never calls a paid API."""
import json
import os
import re
import requests

SYSTEM = '''Türkçe teknoloji haberi kısa video editörüsün. Yalnızca verilen kaynak metnini kullan.
Bilmediğin ayrıntıları, sayıları veya alıntıları uydurma. Haberi doğruladığını iddia etme.
JSON döndür: title (en fazla 95 karakter), script (en fazla 900 karakter, yaklaşık 30–60 saniye),
description (kaynak bağlantısını içerir), tags (en fazla 8 kısa metin). Script yalnızca seslendirilecek metindir.
Özet İngilizceyse Türkçeye çevir. Kaynak yetersizse belirsizliği belirt.'''


def template(article):
    title = article['title'][:95]
    summary = article.get('summary', '').strip()
    # Preserve source wording rather than fabricate an ungrounded Turkish translation.
    heading = title if title.endswith(('.', '!', '?', '…')) else title + '.'
    script = f'{heading} {summary}'.strip()
    if len(script) > 900:
        script = script[:897].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
    return dict(title=title, script=script,
                description=f"{title}\n\nKaynak: {article.get('source', 'Manuel')}\n{article.get('url', '')}\n\n#Shorts #Teknoloji",
                tags=['Shorts', 'Teknoloji'], generation_mode='template',
                editorial_note='Şablon kaynak dilini korur. Yayından önce Türkçeleştirin ve haberi doğrulayın.')


def generate(article, mode):
    if mode == 'template':
        return template(article)
    user = json.dumps(article, ensure_ascii=False)
    if mode == 'ollama':
        base = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
        response = requests.post(base + '/api/chat', json={
            'model': os.getenv('OLLAMA_MODEL', 'llama3.2:3b'), 'stream': False, 'format': 'json',
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}, timeout=(5, 180))
        response.raise_for_status()
        content = response.json()['message']['content']
    elif mode == 'openai':
        key = os.getenv('OPENAI_API_KEY')
        if not key:
            raise ValueError('OPENAI_API_KEY ayarlanmamış. API ayrı ücretlendirilir; Pro aboneliği kullanılamaz.')
        response = requests.post('https://api.openai.com/v1/chat/completions', headers={'Authorization': f'Bearer {key}'}, json={
            'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), 'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': user}]}, timeout=(5, 90))
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content']
    elif mode == 'anthropic':
        key = os.getenv('ANTHROPIC_API_KEY')
        if not key:
            raise ValueError('ANTHROPIC_API_KEY ayarlanmamış. API ayrı ücretlendirilir; Pro aboneliği kullanılamaz.')
        response = requests.post('https://api.anthropic.com/v1/messages', headers={'x-api-key': key, 'anthropic-version': '2023-06-01'}, json={
            'model': os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5'), 'max_tokens': 1000,
            'system': SYSTEM, 'messages': [{'role': 'user', 'content': user}]}, timeout=(5, 90))
        response.raise_for_status()
        content = response.json()['content'][0]['text']
    else:
        raise ValueError('Bilinmeyen senaryo sağlayıcısı')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Model boş bir yanıt döndürdü. Yeniden deneyin veya metni elle düzenleyin.')
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise ValueError('Model geçerli JSON döndürmedi. Yeniden deneyin veya metni elle düzenleyin.') from None
    if not isinstance(result, dict):
        raise ValueError('Model geçerli bir senaryo nesnesi döndürmedi.')
    for field, limit in [('title', 100), ('script', 1200), ('description', 4500)]:
        if not isinstance(result.get(field), str) or not result[field].strip() or len(result[field]) > limit:
            raise ValueError('Model geçerli uzunlukta bir senaryo döndürmedi. Metni elle düzenleyin.')
    if not isinstance(result.get('tags'), list) or any(not isinstance(t, str) or not t.strip() or len(t) > 60 for t in result['tags']) or len(result['tags']) > 12 or sum(map(len, result['tags'])) > 450:
        raise ValueError('Model geçerli etiketler döndürmedi.')
    url = article.get('url', '')
    if url and url not in result['description']:
        citation = '\n\nKaynak: ' + url
        result['description'] = result['description'][:4500 - len(citation)] + citation
    # Models may return additional keys; never let them become IDs, paths or job state.
    result = {key: result[key] for key in ('title', 'script', 'description', 'tags')}
    result['generation_mode'] = mode
    result['editorial_note'] = 'Model taslağıdır. İddiaları ve çeviriyi kaynakla karşılaştırın.'
    return result
