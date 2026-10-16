# Kapsül — Hype Studio video teması

Kapsül, Hype Studio videolarının varsayılan sunum temasıdır. Referansı, açık sıcak gri yüzeyli, kalın kömür rengi çerçeveli, hap (pill) biçimli düğmeler ve neon limon vurgularıyla kurulmuş bir veri paneli (dashboard) tasarımıdır. Videolar bir "yayın stüdyosu paneli" gibi görünür: haber bir zaman çizelgesi üzerinde ilerler, kartlar düğümlere bağlanır, anlatıcı karakter bu panelin sunucusudur.

Uygulama: `app/capsule.py` (sahne düzeni ve kamera), `app/presenter.py` (anlatıcı rig'i), `app/sfx.py` (geçiş sesleri). API'de `style: "capsule"`.

## 1. İlke

- **Sakin yüzey, tek çığlık rengi.** Zemin nötr ve açık; dikkat yalnızca neon limonla çekilir. Limon hiçbir zaman metin rengi olarak açık zeminde kullanılmaz; sadece dolgu, düğüm, vurgu çizgisi ve işaret ışığıdır.
- **Her şey kapsül.** Düğmeler, etiketler, altyazı kutusu, ilerleme çubuğu ve karakterin başı aynı yuvarlatılmış hap formundan türetilir.
- **Bilgi bağlanır.** Kartlar ince çizgilerle zaman çizelgesindeki düğümlere bağlanır; izleyici neyin nereden geldiğini görür.
- **Uydurma veri yok.** Grafik dalgaları dekoratiftir; ekranda rakam, istatistik veya iddia yalnızca senaryodan birebir alınan ifadelerle gösterilir.

## 2. Renk jetonları

| Jeton | Hex | Kullanım |
| --- | --- | --- |
| `frame` | `#3C3D3F` | Dış çerçeve, sekme arka planı |
| `panel` | `#E8E7E2` | Ana yüzey |
| `panel-deep` | `#DCDBD5` | Yüzey içindeki gölge alanları, pasif çipler |
| `card` | `#F6F5F1` | Kartlar, aktif çip, konuşma balonu |
| `ink` | `#2B2C2E` | Ana metin, koyu hap etiketler, altyazı kutusu |
| `ink-soft` | `#77787A` | Küçük etiketler, ikincil metin |
| `lime` | `#D9F23A` | Tek vurgu rengi: düğümler, aktif nokta, dalga, karakter detayları |
| `signal-red` | `#E8735A` | Zaman çizgisinin başlangıç tonu |
| `signal-green` | `#9CCB5A` | Zaman çizgisinin bitiş tonu |
| `line` | `#2B2C2E` %75 saydam | İnce bağlantı çizgileri |

Karanlık sahne yoktur; kontrast koyu kartlar (`ink`) ile sağlanır.

## 3. Tipografi

- Yazı tipi: macOS'ta Arial, Linux'ta DejaVu Sans (sistemde hazır, ek font indirilmez).
- **Başlıklar ince/normal ağırlık** (`\b0`), büyük punto, sıkı satır aralığı (1,12). Referanstaki "Hypertension", "Cardiology" gibi sakin ve büyük.
- **Etiketler** küçük (16–19 px), normal harf, `ink-soft`.
- **Altyazılar kalın** (44 px), beyaz, `ink` kapsül içinde — okunabilirlik süsten önce gelir.

| Rol | Boyut | Ağırlık | Renk |
| --- | --- | --- | --- |
| Sekme başlığı | 46 | normal | `ink` |
| Sahne başlığı / kanca | 66 → 38 (sığdırılır) | normal | `ink` |
| Kart metni | 54 → 32 | normal | `ink` |
| Çip metni | 18 | normal | `ink` |
| Altyazı | 44 | kalın | beyaz |

## 4. Yerleşim (720 × 1280, 9:16)

```
 ┌───────────────┐  ← frame #3C3D3F
 │ ╭─ Hype ─╮ (çip)(çip) │  0–150   Sekme + sahne çipleri
 │ ╰────────╯───────────╮│
 │  ◉────────────────⊕  │  ~240    Zaman çizgisi: limon düğüm → koyu artı
 │   Başlık / kart       │  280–700 İçerik
 │        (anlatıcı)     │  480–930 Anlatıcı (büyük plan) veya PiP rozet
 │ ╭ altyazı ─────────╮  │  936–1114 Koyu altyazı kapsülü
 │ ╰──────────────────╯  │
 │ (▣ · · ▬▬ · · ·)     │  1160–1224 Alt zaman çubuğu (sahne noktaları)
 └───────────────────────┘
```

- Kenar boşluğu: 40 px; kart iç boşluğu 36 px; köşe yarıçapı: panel 44, kart 36, çip ve kapsül yükseklik/2.
- Sekme ile panel arası içbükey kavisle birleşir (referanstaki "Cardiology" sekmesi).

## 5. Bileşenler

- **Sekme:** Sol üstte panel renginde, içinde "Hype" ve küçük "Teknoloji" etiketi.
- **Çipler:** Sağ üstte hap düğmeler. Aktif sahnenin etiketi `card` dolgulu, diğeri yarı saydam. Örnek etiketler: *Gündem, Odak, Kart, Yakın plan, Ara sahne, Son söz*.
- **Zaman çizgisi:** Kırmızıdan yeşile geçen ince çizgi; solda limon düğüm (içinde belge simgesi), sağda koyu "+" düğümü. Sahne başında çizgi soldan sağa çizilir, düğüm yaylanarak büyür.
- **Bağlantı çizgisi:** Düğümden aşağı inip yumuşak köşeyle karta bağlanan 2 px çizgi.
- **Kart:** `card` dolgu, 36 px köşe, sağ üstte beyaz daire içinde simge, altta limon/gri dekoratif dalga (sürekli kayar).
- **Koyu hap etiket:** `ink` dolgu, solda beyaz daire simge, beyaz metin (referanstaki "Aspirin ×2").
- **Vurgu çizgisi:** Yakın plan sahnesinde ilk satırın altında limon fosforlu kalem şeridi.
- **Gömülü altyazı:** Kutu yok; konturlu, kelime kelime beliren büyük harfler (bkz. 8).
- **Alt zaman çubuğu:** Beyaz kapsül; solda koyu takvim dairesi, her sahne için bir nokta; geçerli sahne koyu kapsül bölüm ve limon nokta ile işaretlenir. İlerleme çubuğu görevini görür.

## 6. Renk paketleri ve sahne renkleri

**Varsayılan: koyu siber tema.** Otomatik seçimde video koyu siber paketle üretilir: neredeyse siyah paneller (`#0A0F1C` boşluk, `#062A30` koyu deniz, `#1A2130` grafit, `#07170F` matrix, `#0E1838` iyon), koyu cam kartlar ve her sahnede tek neon vurgu (camgöbeği `#2EE6FF`, nane `#7CFFB2`, kehribar `#FFB547`, matrix yeşili `#3DFF8B`, elektrik mavisi `#4D8BFF`). Pencerenin köşelerinde HUD köşe çerçeveleri, panelde ince tarama çizgileri vardır. Haberde marka geçiyorsa ana vurgu markanın rengidir (ör. Claude → kil `#D97757`). Mor/pembe ağırlıklı paket otomatik seçilmez. Aşağıdaki açık paketler panelden elle seçilebilir.

Her video bir **renk paketi** kullanır. Paket; çerçeve rengi, vurgu ("pop") rengi ve sahne paletlerinden oluşur. Her kesmede panelin rengi değişir; iki renkli sahneden sonra paketin ana rengine dönülür (Ana → A → B → Ana → C → D → Ana …).

**Otomatik seçim:** Haberde bir marka geçiyorsa (başlık iki kat sayılır) markanın paketi seçilir; ör. Claude/Anthropic haberinde krem–kil–kömür tonları. Marka yoksa güncel trend paketlerinden biri haberin başlığına göre sabit olarak seçilir. Panelden elle de seçilebilir.

| Paket | Renkler | Kaynak |
| --- | --- | --- |
| Pinterest 2026 | Cool Blue `#D7EFFF`, Wasabi `#E9F056`, Plum Noir `#351E28`, Persimmon `#FF5C34`, Jade `#AEB8A0` | Pinterest Palette 2026 |
| Transformative Teal | Cloud Dancer (yaklaşık `#F0EEE9`), teal `#0F6B6E`, altın `#F2C14E` | WGSN × Coloro 2026, Pantone 2026 (hex değerleri yaklaşık) |
| Ocean Depths | `#1A2332`, `#2D8B8B`, `#A8DADC`, `#F1FAEE` | Anthropic theme-factory (Apache 2.0) |
| Sunset Boulevard | `#E76F51`, `#F4A261`, `#E9C46A`, `#264653` | theme-factory |
| Tech Innovation | `#0066FF`, `#00FFFF`, `#1E1E1E`, `#FFFFFF` | theme-factory |
| Golden Hour | `#F4A900`, `#C1666B`, `#D4B896`, `#4A403A` | theme-factory |
| Forest Canopy | `#2D4A2B`, `#7D8471`, `#A4AC86`, `#FAF9F6` | theme-factory |
| Kapsül | `#E8E7E2`, limon `#D9F23A`, gece `#34405A`, lila, mercan | Bu proje |
| Marka paketleri | Claude/Anthropic, OpenAI, Google/Gemini, Apple, NVIDIA, Meta, Microsoft, Samsung, Tesla/X | Marka renklerine yakın tonlar |

Her sahne paletinde metin rengi otomatik kontrol edilir: kart metni ile kart arasında en az 4,5:1 kontrast aranır. Kuzgun silueti açık panelde koyu, koyu panelde açık renktir.

### Marka ve logo

- Sol üstteki marka adı **Aopia**'dır (`VIDEO_BRAND` ortam değişkeniyle değiştirilebilir); daire içinde baş harfi.
- Haberin markası için panelden **resmi logo** yüklenebilir (PNG, JPG, WEBP, SVG; en fazla 3 MB). Uygulama logoyu yerelde PNG'ye çevirir; internetten logo indirmez, depoda logo bulunmaz.
- Logo girişte sahnenin sol üstünde beyaz bir karonun içinde, markanın geçtiği diğer sahnelerde "+" düğmesinin yerinde görünür ve kamerayla birlikte yakınlaşır.
- Logo yüklenmemişse markanın adı, paketin vurgu renginde bir etiketle gösterilir.

## 7. Kamera ve hareket

Video iki katmandan oluşur: **dünya** (panel içeriği, kartlar, kuzgun) ve **arayüz** (çerçeve, sekme, çipler, altyazı, alt zaman çubuğu). Dünya 1,2 kat büyük bir tuvale çizilir ve sanal bir kamera üzerinde hareket eder; arayüz sabit kalır.

**Tipografi haritası ve vurgu zoom'u:** Kamera her sahnede otomatik yakınlaşmaz; görüntü çoğu zaman sabittir. Uygulama seslendirme metnini kelime kelime inceleyip bir tipografi haritası çıkarır ve her kelimeye puan verir: rakam ve birimler (ör. "yüzde 40", "3 milyar"), marka adları, "ama/ancak/peki/çünkü" gibi dönüş kelimelerinden sonraki kelime, "en/ilk/rekor/yeni" gibi güçlü ifadeler, soru ve ünlem cümlelerinin sonu. En güçlü anlar seçilir: en fazla yaklaşık 6,5 saniyede bir ve aralarında en az 3,5 saniye olacak şekilde. Kamera yalnızca bu anlarda, kelime söylenmeden hemen önce o sahnenin ana öğesine yaklaşır, kelime boyunca bekler ve geri açılır. Aynı anda altyazıdaki kelime büyük ve vurgu renginde gelir, kısa bir "pop" sesi çalar. Seçilen vurgular panelde videonun özetinde listelenir.

| Öğe | Hareket | Süre |
| --- | --- | --- |
| Vurgu zoom'u | Yalnızca tipografi haritasının seçtiği kelimelerde: yaklaş → bekle → geri açıl | ~1,5 sn |
| Düğüm | Ölçek 0 → 112 → 100 | 380 ms |
| Kart | 40 px aşağıdan kayarak + solma | 320 ms |
| Anahtar kelime | %150'den %100'e düşüş + vurgu kapsülü açılması | 200 ms |
| Sahne geçişi | Yeni sahne renginde perde + vurgu renginde tarama çizgisi + whoosh | 420 ms |

## 8. Gömülü altyazı

Altyazı ayrı bir kutuda durmaz; videonun üzerine **gömülüdür**:

- 1–4 kelimelik kısa parçalar, BÜYÜK HARF, 62 px kalın.
- Beyaz yazı, 6 px kömür kontur ve yumuşak gölge: hangi renkli sahnede olursa olsun okunur.
- Kelimeler söylendikçe tek tek belirir; o an söylenen kelime limon renktedir ve hafif büyüyüp yerine oturur ("pop").
- Her parça birkaç derece farklı eğimle gelir; altyazı da sahne gibi canlı durur.
- Konum: alt zaman çubuğunun hemen üstü; kamera hareketinden etkilenmez.

## 9. Dikkat ritmi (izleyiciyi videoda tutmak)

1. **Her 2,5–3 saniyede bir kesme.** Sahne süresi hedefi 2,8 sn (yüklenen seste altyazı sınırlarına göre en az 2,2 sn).
2. **Ardışık iki sahne aynı düzende olmaz.** Döngü: Odak → Anahtar kelime → Ara sahne → Gündemde → Senaryodan → Adım adım → Yakın plan → Ara sahne.
3. **Renk ve kompozisyon değişir:** her kesmede panel rengi değişir, kuzgun büyük plan ile küçük konma noktaları arasında gidip gelir.
4. **Soru cümleleri kuzguna döner** (konuşma balonu); **kapanış kuzgunla yapılır** ("Son söz").
5. **Kelime kelime altyazı** gözü sesle birlikte taşır.
6. **Ses ipuçları:** her kesmede whoosh, anahtar kelime ve ikinci kart gelişinde kısa "pop". Uygulama içinde sentezlenir, kapatılabilir.
7. **Her hareket bir işe yarar:** hareket ya yeni bilgiyi ya da sahne değişimini işaret eder.

## 10. Anlatıcı: Vega (android spiker)

Teknoloji kanalının yetişkin izleyicisine hitap eden varsayılan anlatıcı **Vega**'dır: bilim kurgu filmlerindeki gibi şık, insansı bir android haber spikeri.

- **Yüz:** Mat metal (`#D3DAE3`) kafa, sağ yanda gölge, alında parlama, ince panel dikişleri.
- **Kayak gözlüğü:** Başın etrafından dolanan kayış, burun oyuklu geniş çerçeve ve sahnenin vurgu renginde yansıyan aynalı cam (üzerinde çapraz parlama). Gözler camın arkasından parlayan badem ışıklardır; kırpınca ışık ince bir çizgiye iner, bakış ışıkların kaymasıdır.
- **Ağız = ses ekolayzırı:** Susarken sönük ince bir ışık çubuğu; konuşurken sesin şiddetine göre inip çıkan 7 ışık çubuğu.
- **Işıklar:** Kulak modülleri, şakaklar, boyun altındaki devre çizgileri ve göğüs çekirdeği vurgu renginde parlar; şakak ve devre ışıkları sesle yoğunlaşır. Neon parçalar hafif ışık saçar (blur).
- **Kaşlar:** Vizörün üstünde iki ince çubuk; sahne geçişlerinde ve sorularda kalkar.
- **Gövde:** Koyu takım, omuz plakaları, segmentli mekanik boyun.

Vega girişte ve ara sahnelerde sahnenin ortasında büyük plan, diğer sahnelerde sağ alttaki yuvarlak ekranda (vurgu renginde halkalı) görünür; anahtar kelime sahnesinde ekrandan çekilir.

Alternatif anlatıcılar: Kuzgun (kuzgun silueti), Volt, Nova, Kaan, Ece.

## 11. Yapılmaması gerekenler

- Neon vurgu rengini koyu zeminde uzun metin rengi olarak kullanmak; uzun metin açık renkte kalır.
- Aynı anda ikiden fazla kartı ekranda tutmak; anlatıcıya yer kalmalı.
- Aynı sahne düzenini art arda kullanmak veya bir sahneyi 4 saniyeden uzun tutmak.
- Senaryoda olmayan rakamları grafik etiketi olarak göstermek.
