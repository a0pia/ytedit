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
    script = f"{title}. {summary}".strip()[:900]
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
    content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())
    result = json.loads(content)
    for field, limit in [('title', 100), ('script', 1200), ('description', 4500)]:
        if not isinstance(result.get(field), str) or not result[field].strip() or len(result[field]) > limit:
            raise ValueError('Model geçerli uzunlukta bir senaryo döndürmedi. Metni elle düzenleyin.')
    if not isinstance(result.get('tags'), list) or any(not isinstance(t, str) or len(t) > 60 for t in result['tags']) or len(result['tags']) > 12:
        raise ValueError('Model geçerli etiketler döndürmedi.')
    url = article.get('url', '')
    if url and url not in result['description']:
        result['description'] += '\n\nKaynak: ' + url
    result['generation_mode'] = mode
    result['editorial_note'] = 'Model taslağıdır. İddiaları ve çeviriyi kaynakla karşılaştırın.'
    return result
