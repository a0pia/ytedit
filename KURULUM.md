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

- 137 Python testi ve 7 masaüstü yaşam döngüsü testi başarılı.
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
