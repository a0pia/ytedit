# Hype Studio

Teknoloji haberlerini bulup Türkçe kısa video projelerine dönüştüren, Mac için cam görünümünde bir üretim paneli. RSS haberlerinden konu seçin, senaryoyu ve başlığı düzenleyin, yerel seslendirme ve senkron altyazıyla 9:16 video oluşturun. Videoyu inceleyip indirin; isteğe bağlı YouTube bağlantısıyla kendi kanalınıza yükleyin.

![Hype Studio yönetim paneli](docs/dashboard.png)

Varsayılan üretim yolu API anahtarı ve ücretli abonelik istemez. RSS başlıkları ve kısa alıntıları kaynak bağlantısıyla taslak girdisi olarak alınır; video için uygulamanın ürettiği hareketli grafikler ve başlık kartları kullanılır. Başka yayınların videoları veya lisansı belirsiz stok görüntüler otomatik indirilmez. Haber sıralaması RSS içeriği ve güncellik üzerinden yapılır; tüm internetin gerçek zamanlı izlenmesi veya doğrulanmış trend ölçümü değildir. RSS erişimi, içeriği yeniden yayımlama lisansı vermez.

## Mac'te kurulum

Gerekenler: macOS, Python 3.11+, Node.js 22.12+, FFmpeg ve internet bağlantısı. Apple Silicon ve Intel cihazlarda ilgili araçların kendi mimarinize uygun sürümlerini kullanın. Homebrew zaten kuruluysa:

```bash
git clone https://github.com/a0pia/ytedit.git
cd ytedit
brew install python@3.12 node ffmpeg
HYPE_PYTHON="$(brew --prefix python@3.12)/bin/python3.12" ./scripts/setup.sh
npm start
```

`setup.sh` Python sanal ortamını oluşturur, Python ve kilitlenmiş Node bağımlılıklarını yükler, varsa mevcut `.env` dosyanızı korur. İlk kurulum paket indirmek için internet kullanır. Electron yerel Python sunucusunu başlatır ve ayrı bir masaüstü penceresi açar; pencere kapandığında kendisinin başlattığı sunucuyu durdurur. Zaten çalışan Hype Studio sunucusunu kullanırsa onu kapatmaz.

Sonraki açılışlarda `scripts/Start-Hype-Studio.command` dosyasına çift tıklayabilirsiniz. Terminal'den `npm start` da kullanılabilir. Bu sürüm kaynak kodundan çalışan bir Mac masaüstü uygulamasıdır; Python ve FFmpeg içeren, imzalanmış/noter onaylı bir DMG paketi henüz hazırlanmış değildir.

Tarayıcıdan çalıştırmak için:

```bash
npm run dev
```

Ardından `http://127.0.0.1:8787` adresini açın. Sunucu yalnızca bu cihazın yerel arabirimini dinler. Başka cihazlara veya herkese açık internete açmak için tasarlanmamıştır. Electron görünümü macOS üzerinde, web arayüzü güncel tarayıcılarda kullanılabilir; bulut ortamında Mac pencere davranışı doğrulanamaz.

Linux geliştirme ortamında aynı komutlar kullanılabilir. FFmpeg yanında ücretsiz yerel seslendirme için `espeak-ng` gerekir (`sudo apt install ffmpeg espeak-ng`). Grafik ortamı bulunmayan bir sunucuda Electron yerine `npm run dev` kullanın.

Bu deponun Debian trixie/amd64 bulut makinesinde `./scripts/setup-cloud.sh` komutunu kullanın. Betik eSpeak'i Debian'ın imzalı paketlerinden `/workspace/.tools/espeak` altına açar; sistem paketlerini değiştirmez ve `sudo` istemez. Python, Node ve FFmpeg'in ortamda hazır bulunmasını bekler. Paket önbellekleri `/workspace/.cache/hype-studio` altında tutulur. Sonra `npm run dev` ile başlatın. Her bulut görevi zaten ayrı bir ortamda çalışır; mevcut checkout'u kullanın, ek Git worktree oluşturmayın.

Bulut ortamının ağ izin listesi varsa haber yenilemek için `shiftdelete.net`, `www.theverge.com`, `techcrunch.com` ve `feeds.arstechnica.com` alanlarına HTTPS erişimi gerekebilir. Ağ erişimi yoksa uygulama bunu bildirir; mevcut projeler ve elle girilen haberlerle yerel üretime devam edebilirsiniz.

## İlk video

1. Haberleri yenileyin ve bir teknoloji haberini seçin. Harici haberler için internet gerekir; kaynağı ve tarihi kontrol edin.
2. Kısa video projesi oluşturun. Üretilen senaryoyu, başlığı ve açıklamayı düzenleyin; iddiaları kaynaklardan doğrulayın.
3. Ücretsiz yerel seslendirmeyle videoyu oluşturun. FFmpeg özgün grafik arka planları, konuşma sesini ve senkron altyazıları tek MP4 dosyasında birleştirir.
4. Önizlemeyi izleyin. Türkçe telaffuz, altyazı zamanlaması ve haber doğruluğunu gözden geçirip dosyayı indirin.
5. YouTube hesabını isteğe bağlı bağlayın. Hazırladığınız videoyu onaylayıp yükleyin; yayın durumunu bilinçli seçin.

Haber metinleri de telifli olabilir. Haberi kendi kısa anlatımınızla özetleyin, kaynağı belirtin ve yayımlamadan önce kullanılan içeriğin haklarını değerlendirin. YouTube'un özgünlük ve tekrar kullanılan içerik kuralları ayrıca geçerlidir.

## Ses ve dil modeli seçenekleri

| Seçenek | Maliyet ve gereksinim |
| --- | --- |
| Yerel senaryo şablonu | Varsayılan. API anahtarı ve model indirmesi gerekmez. Kaynak dilini korur; çeviri veya yaratıcı yeniden yazım yapmaz. Metni düzenleyebilir ya da Ollama seçebilirsiniz. |
| macOS `say` | Varsayılan ücretsiz seslendirme. Cihazda kurulu seslerden yararlanır. Türkçe ses yoksa Sistem Ayarları → Erişilebilirlik → Seslendirilen İçerik bölümünden Türkçe sesi indirin. |
| Linux eSpeak | Ücretsiz ve yerel. Ses kalitesi ticari servislerden daha basittir. |
| Ollama | İsteğe bağlı, cihazda çalışan ücretsiz dil modeli. Model indirme, RAM ve disk gerekir. |
| ElevenLabs | İsteğe bağlı resmi API bağlantısı. Kendi anahtarınız ve ses kimliğiniz gerekir; ücretsiz kota ve ticari kullanım koşullarını sağlayıcı belirler. |
| OpenAI / Anthropic | İsteğe bağlı resmi API bağlantıları. Kendi API anahtarınız gerekir; kullanım ücretli olabilir. |

**ChatGPT Plus/Pro ve Claude Pro abonelikleri API kredisi sağlamaz.** Bu web aboneliklerini bağlayıp sınırsız veya ücretsiz API kullanımı sunmak mümkün değildir. Uygulama bu hesapların oturum çerezlerini almaz. Ücret istemiyorsanız varsayılan yerel üretimi veya Ollama'yı seçin; ücretli sağlayıcıları etkinleştirmeyin.

Ollama isterseniz resmi uygulamasını kurup modeli indirin:

```bash
ollama pull llama3.2:3b
```

Ollama çalışırken panelde yerel modeli seçin. Varsayılan servis adresi `http://127.0.0.1:11434`, model adı `llama3.2:3b`. İlk indirme birkaç GB disk kullanabilir. İşlemci/GPU hızına göre üretim süresi değişir. Ollama temel video üretimi için zorunlu değildir.

## YouTube bağlantısı

YouTube yüklemek için kendi Google Cloud OAuth istemciniz gerekir; bağlamadan MP4 üretip indirmeye devam edebilirsiniz.

1. Google Cloud Console'da bir proje oluşturup **YouTube Data API v3** hizmetini etkinleştirin.
2. OAuth izin ekranını yapılandırın. Uygulama test modundaysa Google hesabınızı test kullanıcısı ekleyin.
3. **Web application** türünde OAuth istemcisi oluşturun. Yetkili yönlendirme adresine tam olarak `http://127.0.0.1:8787/oauth/youtube/callback` ekleyin.
4. İstemci kimliği ve sırrını yerel `.env` dosyanıza girip uygulamayı yeniden başlatın. Google hesabınızın parolasını uygulamaya vermeyin.
5. Panelden YouTube'u bağlayın. İzin işlemi sistem tarayıcısında açılır ve yerel uygulamaya döner.

Port değiştirirseniz `.env` içindeki `YOUTUBE_REDIRECT_URI` değerini ve Google Cloud'daki yönlendirme adresini aynı portla güncelleyin. OAuth test uygulamalarında izinlerin süresi dolabilir; gerektiğinde yeniden bağlanın. YouTube API kotaları ve doğrulanmamış projelerin yükleme/yayın kısıtlamaları Google tarafından belirlenir. Bazı projelerde yüklemeler denetim tamamlanana kadar gizli videolarla sınırlı olabilir. Uygulama bu sınırlamaları aşmaz ve belirli bir günlük yükleme sayısı vaat etmez.

## Yerel ayarlar ve dosyalar

`.env.example` kullanılabilir değişkenleri gösterir. Anahtarları yerel `.env` dosyanızda saklayıp uygulamayı yeniden başlatın; bu dosyayı paylaşmayın. Örnek dosyada gerçek anahtar yoktur. API anahtarları ve YouTube yetkilendirmesi kendi cihazınızda saklanır; işletim sisteminde hesabınıza erişebilen kişilerden korumak sizin sorumluluğunuzdadır. Bu geliştirme sürümünde işletim sistemi Keychain entegrasyonu bulunmaz.

- `HYPE_PORT`: yerel sunucu portu, varsayılan `8787`.
- `HYPE_DATA_DIR`: proje, OAuth belirteci ve medya dosyaları klasörü. Terminal/web modunda varsayılan `data/`; Electron'da macOS uygulama verileri içindeki `Hype Studio/data` klasörü. Aynı verilere her iki moddan ulaşmak için iki başlangıçta da bu değişkeni aynı mutlak klasöre ayarlayın.
- `LOCAL_TTS_VOICE`: macOS için isteğe bağlı kurulu ses adı, örneğin `Yelda`.
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`: yerel dil modeli adresi ve modeli.
- `OPENAI_API_KEY`, `OPENAI_MODEL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`: isteğe bağlı dil modeli API'leri.
- `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`: isteğe bağlı seslendirme API'si.
- `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REDIRECT_URI`: isteğe bağlı YouTube OAuth bilgileri.

Electron başlatıcısının farklı bir Python kullanması gerekirse `HYPE_PYTHON` değişkenini Python çalıştırılabilir dosyasının **mutlak yoluna** ayarlayın. Varsayılan proje içindeki `.venv/bin/python` dosyasıdır. Sunucu günlüğü işletim sisteminin Electron günlük klasöründeki `hype-studio-backend.log` dosyasına yazılır.

## Geliştirme ve doğrulama

```bash
npm test
npm run check:desktop
```

Python sunucusu `app/`, masaüstü başlatıcısı `desktop/`, kurulum komutları `scripts/` altındadır. İlk açılışta paketler indirilir; daha sonraki yerel video üretimi için ücretli API gerekmez. Haber yenileme, model indirme ve YouTube yükleme internet kullanır. Kullanılan açık kaynak araçların lisansları kendi projelerine aittir.

Video oluşturma zaman alabilir; uygulamayı işlem bitene kadar açık tutun. Aynı anda birden fazla ağır video üretimi, özellikle düşük bellekli cihazlarda, yavaşlığa yol açabilir. Mac kurulumu için hata alırsanız önce `ffmpeg -version`, `python3 --version` ve `node --version` çıktılarıyla önkoşulları kontrol edin. Anahtarları veya OAuth tokenlarını hata raporlarına eklemeyin.

İsteğe bağlı gerçek tarayıcı kontrolü için önce sunucuyu başlatın; ayrı bir geliştirme ortamına `playwright==1.55.0` kurup `CHROMIUM_PATH` ile Chromium çalıştırılabilir dosyasını belirtin. `.venv/bin/python tests/ui_smoke.py` manuel taslak oluşturur, ücretsiz sesli video üretir, videonun 720×1280 olarak çözüldüğünü, SRT'yi ve yükleme onayını kontrol eder. Gerçek YouTube yüklemesi yapmaz. Başarılı çıktılar `artifacts/` altına ekran görüntüsü olarak kaydedilir.

Bu geliştirme ortamında 84 otomatik test ve gerçek tarayıcı üretim akışı geçti. Canlı RSS erişimi bulut proxy politikası nedeniyle engellendi; Google hesabı verilmediğinden gerçek YouTube yüklemesi ve API anahtarı gerektiren servisler çalıştırılmadı. Mac masaüstü başlatıcısının sözdizimi kontrol edildi; macOS üzerinde çalışma testi henüz yapılmadı.
