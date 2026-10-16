# Uygulama fikri — orijinal prompt

şunu yapmak istiyorum internette teknoloji ile güncel hype olan haberleri tespit edip bunları editleyeyip reels short formatında editleyip açıklama başlık yazabilecek sonra bunu youtube da paylaşacak bir uygulama tasarlamak istiyorum bunu yapabilir miyiz videoda ki altyazıları falanda yapacak

## Sonradan eklenen istekler

- macOS üzerinde çalışan, uygulamanın yönetilebildiği bir masaüstü arayüzü.
- Paylaşılan görseldeki gibi yarı saydam koyu panel, yan menü ve renkli kartlar.
- Haber keşfi, kısa video kurgusu, seslendirme, altyazı, başlık ve açıklama hazırlama.
- Kullanıcı onayıyla YouTube'a yükleme.
- Varsayılan üretim akışında ücretli API gerekmemesi ve ücretsiz içerikler kullanılması.
- ElevenLabs gibi ses servislerine isteğe bağlı bağlantı.
- ChatGPT/Claude hesabı bağlama isteği: Pro abonelikler API erişimi sağlamadığından, ücretsiz alternatif olarak yerel Ollama desteği; ücretli API bağlantıları yalnızca isteğe bağlı.
- Tema için tekrar paylaşılan referansa göre yönetim paneli görünümü: üstte dumanlı gri, altta lacivert buzlu cam yüzey; canlı sarı, turuncu, mor, yeşil ve mavi kartlar; solda menü, sağda üretim hareketleri.

## Türkçe ve animasyon için eklenen istekler

- Yabancı haberler seçildiğinde video başlığı, anlatımı, açıklaması ve etiketleri Türkçeye çevrilsin; seslendirme ve altyazılar Türkçe olsun.
- Orijinal haber metni ve kaynak korunarak çeviri karşılaştırılabilsin.
- Videolar tek görsel üzerinde dönmesin: dikkat çeken hareketli giriş, sahne değişimleri, animasyonlu yazılar ve vurgu kartları kullanılsın.
- Ücretsiz, uygulamanın kendisinin oluşturduğu grafikler ve yerel araçlar varsayılan olmaya devam etsin.

## Harici ses dosyası için eklenen istek

birde elevelabs api si paralıymış videodaki metni bize verse video sonra ben kendim manuel elevenlabste ses dosyasını oluşturup uygulamaya atsam sonra uygulama bu ses dosyasına göre edit yapsa olur mu bu şekilde

- Güncel Türkçe seslendirme metni kopyalanabilsin ve TXT olarak indirilebilsin.
- ElevenLabs web sitesi veya başka bir araçta kullanıcı tarafından hazırlanan MP3/WAV kaydı projeye yüklenebilsin; bu yol için ücretli ses API'si çağrılmasın.
- Video süresi ve animasyonlu sahneler yüklenen kaydın süresine göre hazırlansın.
- Altyazı süreleri konuşma/sessizlik aralıklarından tahmin edilsin, kullanıcı başlangıç/bitiş saniyelerini düzeltebilsin. Kaydın aynı senaryo metnini içermesi gereksinimi açıkça belirtilsin.

## Anlatıcı karakter için eklenen istek

projedeki sunum kısmını beğenemiyorum böyle bana özgü bir tema oluşturalım bir karakter anlatıyor gibi olsun bir kurgusal karakter olabilir influencer gibi düşünebilirsin sunumları daha dikkat çekici yapmak lazım örnek şöyle bir şey olabilir anlatıcı olur ara sahnelerde gelir gibi sistemi internette biraz araştır

- Göz, kaş ve baş kontrolleri olan bir 2D kukla (Character Animator / VTuber benzeri) anlatıcı.
- Giriş, ara sahneler ve kapanışta büyük plan; diğer sahnelerde köşe penceresinden yorum.
- Ağız hareketi seslendirmeye göre; karakter adı ve görünümü seçilebilir.

## Kapsül teması ve ikonik karakter için eklenen istek

daha ikonik bi karakter yapabilir miyiz birde sunumun temasını beğenmiyorum şu tarz tema md si oluştur sunum temasını ona göre ayarla

- Referans: açık gri panel, koyu çerçeve, hap düğmeler, neon limon vurgu, zaman çizelgesi ve kartlı bir dashboard.
- Tema kuralları `docs/TEMA.md` dosyasında; video sahneleri bu temaya göre (`style: "capsule"`).
- Siluetiyle tanınan maskot anlatıcı: Volt.

## Kuzgun ve dikkat ritmi için eklenen istek

karakteri beğenmedim karakter bir kuzgun olsun birde sahneler hep birbiriyle aynı gibi böyle öyle olmalı ki izleyen kişi hep videoya odak kalsın dikkati dağılsa bile tekrar odağını toplayabilsin

- Varsayılan anlatıcı: Kuzgun (gaga ağız gibi açılır).
- Kısa ve değişken sahneler, kamera hareketleri, kelime kelime altyazı ve geçiş sesleriyle dikkat ritmi.

## Kuzgunun gerçek kuş gibi davranması için eklenen istek

gerçek bir kuş gibi yap butonların üstüne falan veya focus falan videoya zoom atsın falan dinamik bir video olsun

- Kuzgun sahneler arasında uçar, butonlara/kartlara/altyazı kenarına konar, gagalar, zıplar.
- Kamera kuşun konduğu yere yakınlaşır, ardından içeriğe kayar.

## Gerçekçi kuzgun, gömülü altyazı, renk döngüsü ve widget zoom'u

ön profil değilde yan profil olsun kuşun gerçek bir kuzgun gibi dursun yani böyle realistik

birde alt yazı kısmını beğenmedim altyazıyı videoya gömerek yap daha böyle dikkat çekici ve dinamik olsun ve slaytların rengi değişsin her 2 slaytta sonra ana renge geri dönsün böyle widget e zoom atsın falan sonra zoom geri gelsin gibi dinamik render olsun

- Kuzgun gerçekçi yan profil; baktığı yöne döner.
- Altyazı kutusuz, konturlu, kelime kelime beliren kısa parçalar.
- Sahne renkleri: Ana → iki renkli sahne → Ana.
- Kamera her sahnede widget'a yakınlaşıp geri açılır.

## Siluet kuzgun, Aopia markası, trend paletler ve logolar

şu tarz bir tasarım olsun kuzgunun birde sol üste hype yazmasın Aopia yazsın ve tema hep mor pembe falan olmasın viral olan renk paletlerini bul internetten ve hikaye örgüsüne göre logo falanda koyabilirsin ... örnek claude ile ilgili haber yapıyoruz claude logo gelsin gibi birde internette etkileyici sunum skill falan varsa onlarıda kullanabilirsin

- Kuzgun: tek renk gerçekçi siluet, uçuş/ötme/gagalama pozları.
- Sol üst marka: Aopia.
- Renk paketleri: Pinterest 2026, WGSN 2026, theme-factory temaları, marka paketleri; habere göre otomatik.
- Marka logoları kullanıcı tarafından yüklenir; videoda giriş ve markanın geçtiği sahnelerde görünür.

## Siber anlatıcı ve koyu tema

kedi olmamış daha siber bir şey yap böyle teknoloji ile ilgili bir kanal olacağı için yaş kitlesi büyük olacak

- Seçim: Android spiker (Vega) + koyu siber tema.
- Otomatik palet koyu siber paketlerden; haberde marka varsa vurgu markanın rengi.

## Tipografi haritası

robota bir kayakçı gözlüğü tak

videolarda zoom u direk yapma tipografi haritası falan oluştursn metni incelesin vurgulanmak isteyen yere o anda vurgulasın ve tüm slaytlarda olmasın

- Vega'ya aynalı kayak gözlüğü.
- Metin kelime kelime puanlanır (sayı, marka, dönüş kelimesi, güçlü ifade, soru/ünlem); zoom ve büyük altyazı yalnızca seçilen birkaç anda.

## Remotion ve Apify

videoyu daha iyi nasıl yaparız diye internette biraz araştırma yaptım apify ve https://github.com/remotion-dev/remotion bunu buldum bunları projeye entegre et

- Seçim: Tamamen Remotion'a geçiş (bireysel lisans). Video planı Python'da, çizim Remotion'da, ses FFmpeg ile.
- Apify: sosyal trendler ve haber görselleri (token yalnızca yerel .env içinde).
