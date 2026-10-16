# Kapsül — Hype Studio video teması

Kapsül, Hype Studio videolarının varsayılan sunum temasıdır. Referansı, açık sıcak gri yüzeyli, kalın kömür rengi çerçeveli, hap (pill) biçimli düğmeler ve neon limon vurgularıyla kurulmuş bir veri paneli (dashboard) tasarımıdır. Videolar bir "yayın stüdyosu paneli" gibi görünür: haber bir zaman çizelgesi üzerinde ilerler, kartlar düğümlere bağlanır, anlatıcı karakter bu panelin sunucusudur.

Uygulama: `app/capsule.py` (sahne düzeni), `app/presenter.py` (anlatıcı rig'i). API'de `style: "capsule"`.

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
- **Altyazı kapsülü:** `ink` dolgu, 36 px köşe, beyaz kalın metin.
- **Alt zaman çubuğu:** Beyaz kapsül; solda koyu takvim dairesi, her sahne için bir nokta; geçerli sahne koyu kapsül bölüm ve limon nokta ile işaretlenir. İlerleme çubuğu görevini görür.

## 6. Hareket

| Öğe | Hareket | Süre |
| --- | --- | --- |
| Düğüm | Ölçek 0 → 110 → 100 | 380 ms |
| Zaman çizgisi | Soldan sağa çizim | 520 ms |
| Kart | 40 px aşağıdan kayarak + solma | 320 ms |
| Başlık satırları | Sırayla yukarı kayma, 100 ms gecikmeli | 380 ms |
| Dalga | Yatayda sürekli kayma | sahne boyunca |
| Sahne geçişi | Panel renginde dikey "kapak" perdesi + limon şerit | 420 ms |

Hareketler yumuşak ve kısa: panel sakin kalır, karakter canlı olandır.

## 7. Anlatıcı karakter: Volt

Volt, temanın maskotudur ve bir bakışta tanınması için tek bir siluete dayanır: **kapsül baş + anten + kulaklık**.

- **Baş:** Dikey kapsül, `card` tonunda. Siluet tek başına (siyah gölge olarak bile) tanınmalı.
- **Vizör:** Yüzü yatay kesen koyu `ink` kapsül; gözler bunun üzerinde **limon LED kapsüllerdir**. Göz kırpma LED'in ince çizgiye inmesidir; bakış LED'lerin vizör içinde kaymasıdır.
- **Kaşlar:** Vizörün üstünde iki koyu hap; sahne geçişlerinde, soru/ünlem cümlelerinde kalkar.
- **Anten:** Tepedeki limon top, konuşurken sesin şiddetine göre parlar — karakterin "yayında" işareti.
- **Kulaklık:** Limon kulaklık kapları ve koyu bant; sol kaptan ağza uzanan mikrofon.
- **Ağız:** Seslendirmenin şiddetine ve altyazıdaki harfe göre A/E/I/O/U, M-B-P, F-V şekilleri.
- **Gövde:** Koyu kapüşonlu, göğüste limon şimşek rozeti.

Kullanım kuralları: Volt'un rengi değiştirilmez (marka işareti), limon yalnızca LED gözler, anten, kulaklık ve rozette bulunur. Büyük planda baş çerçevenin yatay ortasındadır; PiP rozetinde 100 px yarıçaplı dairede, `ink` halka ve limon iç halka ile görünür. Adı alt bantta koyu hap etiketle yazılır.

Alternatif karakterler (Nova, Kaan, Ece) aynı rig'i kullanır; Kapsül temasında da çalışırlar ama temanın imza karakteri Volt'tur.

## 8. Yapılmaması gerekenler

- Limon metni açık zemine yazmak.
- Kartları keskin köşeli veya gölgesi ağır yapmak.
- Senaryoda olmayan rakamları grafik etiketi olarak göstermek.
- Aynı anda ikiden fazla kartı ekranda tutmak; anlatıcıya yer kalmalı.
