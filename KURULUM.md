# Bulut ortamı ve geliştirme durumu

## İlk inceleme

`a0pia/ytedit` deposu ilk incelemede boştu; commit ve `main` dalı bulunmuyordu. GitHub üzerinden salt okunur Git erişimi başarılıydı. Kullanıcının sonraki isteğiyle bu çalışma kopyasında Hype Studio geliştirildi.

## Geliştirilen ilk sürüm

- Mac için Electron masaüstü başlatıcısı ve Türkçe yönetim paneli.
- Açık RSS kaynaklarından haber toplama; güncellik ve anahtar kelimelerle yaklaşık ilgi sıralaması.
- Yerel taslak kaydı, senaryo, başlık, açıklama ve etiket düzenleme.
- Varsayılan ücretsiz yerel seslendirme ve özgün grafiklerle 720×1280 MP4 üretimi.
- Ses sürelerine dayanan cümle altyazıları ve indirilebilir SRT.
- İsteğe bağlı Ollama, OpenAI, Anthropic ve ElevenLabs bağlantıları.
- Google OAuth ve açık kullanıcı onayıyla YouTube yükleme.

## Doğrulama

- 243 Python testi ve 9 masaüstü yaşam döngüsü testi başarılı.
- Gerçek Türkçe yerel sesli ve sessiz video çıktıları FFmpeg/ffprobe ile doğrulandı.
- Gerçek tarayıcıda taslak oluşturma, düzenleme, video üretme, oynatılabilir video boyutları, SRT ve yükleme onayı doğrulandı.
- Masaüstü başlatıcısının ve kurulum betiklerinin sözdizimi kontrolleri başarılı.
- Mac çalıştırma testi ve gerçek YouTube yüklemesi yapılmadı.
- Bulut proxy politikası canlı RSS kaynaklarına erişimi engelliyor. Dört kaynak alanı için ağ izni yapılandırma taslağına kaydedildi.

## Yeniden kurulum

Bulutta `/workspace/ytedit` içinde `./scripts/setup-cloud.sh`, ardından `npm run dev` çalıştırılır. Mac'te kurulum ve `npm start` adımları için README.md dosyasına bakın.

Kurulum ve başlatma yönergeleri ortam yapılandırma taslağının `install_script` ve `start_skill` alanlarına kaydedildi. Taslağın kaydedilmesi, ortamın yayımlandığı veya yeni bir görevde doğrulandığı anlamına gelmez.

## 0.2 güncellemesi

- Mac ekranına sığan genel yerleşim, daha okunaklı kartlar ve erişilebilir yan menü.
- Proje arama/filtreleme, çoğaltma, JSON dışa aktarma ve onaylı silme.
- Kaydedilmemiş taslak uyarısı ve işlem sırasında form kilidi.
- Metadata değişikliğinde hazır videonun korunması, sıra durumları ve gerçek kodlama ilerlemesi.
- Kısmi RSS hatalarında güncel önbelleğin korunması ve kaynak sağlık bilgileri.
- Homebrew/Python keşfi, proje sanal ortamının doğru kullanımı, devam eden işlerde kapanış onayı ve sahip olunan medya süreçlerinin temizlenmesi.
- Mac’in gerçek pencere davranışı ve gerçek YouTube hesabına yükleme hâlâ bu Linux makinesinde doğrulanmadı.

## 0.3: Türkçe çeviri ve animasyonlu sahneler

- Haber başlığı/özetini Türkçeye çevirip orijinaliyle karşılaştırarak Türkçe taslak oluşturma.
- Mevcut video başlığı, anlatım, açıklama ve etiketlerini tek işlemle Türkçeye çevirme; çeviri başarısızsa önceki içerik ve video korunur.
- Türkçe metinden yerel seslendirme ve senkron altyazı. Ücretsiz çeviri için Mac'te Ollama modeli gerekir; ücretli sağlayıcıya otomatik geçiş yapılmaz.
- Hareketli giriş başlığı, değişen sahne düzenleri, renkli vurgu kartları, hareketli şekiller ve sahne sayacı. Klasik tasarım seçenek olarak korunur.
- Gerçek sesli animasyonlu örnek: 22,5 saniye ve 7 sahne. Farklı zamanlardaki kareler ve sahne içindeki hareket doğrulandı.
- Yabancı haber → kontrollü yerel HTTP model yanıtı → Türkçe proje → gerçek animasyonlu MP4/ses/SRT akışı tarayıcıda doğrulandı. Bu kontrollü model yanıtları, gerçek modelin çeviri kalitesini ölçmez.
- Bu bulut ortamında `registry.ollama.ai` ve `ollama.com` adresleri proxy403 ile engellendiği için gerçek Ollama modeli indirilmedi/çalıştırılmadı. Mac'te ücretsiz kurulum adımları README.md içinde.

## 0.4: Yüklenen ses kaydı

- Güncel Türkçe senaryoyu kopyalama ve TXT olarak indirme.
- MP3/WAV kaydını yerel yükleme, dinleme, değiştirme ve kaldırma. Dosya en fazla 25 MB ve 90 saniye olabilir.
- Yüklenen kaydın gerçek süresiyle animasyonlu video ve SRT üretimi; bu yolda yerel TTS veya ses API'si çalıştırılmaz.
- Otomatik zamanlama ses enerjisi/duraklamalardan tahmin edilir; kelime tanıma yapılmaz. Zamanlar panelde elle düzeltilebilir.
- Senaryo değişirse mevcut ses uyumsuz gösterilir ve yeniden ses yükleme gerekir. Hatalı ses yüklemesi önceki ses/video kaydını korur.
- Gerçek WAV/MP3 çözme, sesin korunması, altyazı doğrulama, işlem kilitleri ve dosya temizliği testlerle doğrulandı.
