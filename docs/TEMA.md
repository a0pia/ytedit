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
- **Altyazı kapsülü:** `ink` dolgu, 36 px köşe, beyaz kalın metin.
- **Alt zaman çubuğu:** Beyaz kapsül; solda koyu takvim dairesi, her sahne için bir nokta; geçerli sahne koyu kapsül bölüm ve limon nokta ile işaretlenir. İlerleme çubuğu görevini görür.

## 6. Hareket ve kamera

Video iki katmandan oluşur: **dünya** (panel içeriği, kartlar, anlatıcı) ve **arayüz** (çerçeve, sekme, çipler, altyazı kapsülü, alt zaman çubuğu). Dünya 1,2 kat büyük bir tuvale çizilir ve sanal bir kamera üzerinde hareket eder; arayüz sabit kalır. Böylece görüntü sürekli canlıdır ama göz her zaman tutunacak sabit bir çerçeve bulur.

| Sahne | Kamera |
| --- | --- |
| Giriş / Ara sahne | Yüze "punch-in": kesmede %12 yakın, 0,3 sn'de yerine oturur, sonra yavaş itme |
| Anahtar kelime | Sert punch-in (%18) |
| Odak, Yakın plan | Yavaş itme (push-in) |
| Gündemde | Yavaş geri çekilme (pull-out) |
| Senaryodan | Yatay kayma (drift) |
| Adım adım | İkinci karta doğru aşağı kayma (tilt) |

| Öğe | Hareket | Süre |
| --- | --- | --- |
| Düğüm | Ölçek 0 → 112 → 100 | 380 ms |
| Zaman çizgisi | Soldan sağa çizim | 520 ms |
| Kart | 40 px aşağıdan kayarak + solma | 320 ms |
| Anahtar kelime | %150'den %100'e düşüş + limon kapsül açılması | 200 ms |
| Sahne geçişi | Panel renginde perde + limon tarama çizgisi + whoosh sesi | 420 ms |

## 7. Dikkat ritmi (izleyiciyi videoda tutmak)

Amaç, dikkati dağılan izleyicinin birkaç saniye içinde yeniden videoya bağlanmasıdır. Kurallar:

1. **Her 2,5–3 saniyede bir kesme.** Sahne süresi hedefi 2,8 sn (yüklenen seste altyazı sınırlarına göre en az 2,2 sn).
2. **Ardışık iki sahne aynı düzende olmaz.** Döngü: Odak → Anahtar kelime → Ara sahne → Gündemde → Senaryodan → Adım adım → Yakın plan → Ara sahne.
3. **Kompozisyon da değişir:** anlatıcı büyük plan → köşe penceresi → hiç yok (anahtar kelime) → tekrar büyük plan. Göz, yeni bir çerçeve gördüğünde odağı yeniden toplar.
4. **Soru cümleleri anlatıcıya döner.** Senaryodaki "?" cümlesi her zaman karakterin konuşma balonuyla gösterilir (yeniden kanca).
5. **Kapanış anlatıcıyla yapılır** ("Son söz").
6. **Kelime kelime altyazı:** o an söylenen kelime limon renkte yanar; göz sesi takip eder.
7. **Ses ipuçları:** her kesmede yumuşak whoosh, anahtar kelime ve ikinci kart gelişinde kısa "pop". Sesler uygulama içinde sentezlenir, anlatımın altında kalır ve kapatılabilir.
8. **Her hareket bir işe yarar.** Süs için hareket eklenmez; hareket ya yeni bilgiyi ya da sahne değişimini işaret eder.

## 8. Anlatıcı karakter: Kuzgun

Kuzgun, temanın imza karakteridir. Bir bakışta tanınması için silueti üç öğeye dayanır: **dikenli taç tüyleri, büyük gaga, limon halkalı gözler**.

- **Gövde ve baş:** Parlak kuzgun siyahı (`#1B1E29`), başın üstünde mavi-mor bir parlama.
- **Gözler:** Beyaz göz, koyu göz bebeği, limon iris halkası. Göz kırpınca limon bir çizgiye iner; bakış göz bebeklerinin kaymasıdır.
- **Kaşlar:** Gri-mavi tüy kaşlar; sahne geçişlerinde, soru ve ünlemlerde kalkar.
- **Gaga = ağız:** Üst gaga sabit, alt gaga seslendirmenin şiddetine göre açılır. O/U seslerinde gaga daralır, M/B/P'de kapanır.
- **Atkı:** Limon atkı ve sarkan ucu; temanın vurgu rengini karaktere taşır.
- **El sallama:** Girişte kanadını kaldırıp sallar.

### Gerçek kuş gibi davranış

Kuzgun sabit bir pencerede durmaz; ekranda dolaşır:

- **Uçuş:** Her kesmede kanat çırparak bir yay çizip yeni yerine uçar (0,55 sn), uçarken gövdesi gittiği yöne eğilir.
- **Konma noktaları:** Arayüzün kendisine konar: girişte ve ara sahnelerde altyazı kapsülünün üstüne (büyük plan), odak sahnesinde altyazı kenarının sağına, "Gündemde" butonunun, anahtar kelime kapsülünün, alıntı işaretinin ve "+" butonunun üstüne. Adım adım sahnesinde birinci karttan ikinci karta seker.
- **Konunca:** Kanatlarını toplar, küçük bir yaylanma yapar ve konduğu şeyi gagalar.
- **Beklerken:** Başını kuşlar gibi kısa, kesik hareketlerle çevirir; ara sıra yerinde zıplar; içeriğe doğru bakar.
- **Kamera:** Kuş konarken kamera onun üzerine yakınlaşır, sonra yavaşça sahnenin içeriğine kayar. Göz önce canlı olanı, sonra bilgiyi bulur.

Kullanım kuralları: Kuzgun'un renkleri değiştirilmez; limon yalnızca iris, atkı ve göz kırpma çizgisinde bulunur. Büyük planda baş çerçevenin yatay ortasındadır; köşe penceresinde koyu daire, limon halka ve altta limon isim etiketiyle görünür.

Alternatif karakterler (Volt, Nova, Kaan, Ece) aynı rig'i kullanır.

## 9. Yapılmaması gerekenler

- Limon metni açık zemine yazmak.
- Kartları keskin köşeli veya gölgesi ağır yapmak.
- Senaryoda olmayan rakamları grafik etiketi olarak göstermek.
- Aynı anda ikiden fazla kartı ekranda tutmak; anlatıcıya yer kalmalı.
- Aynı sahne düzenini art arda kullanmak veya bir sahneyi 4 saniyeden uzun tutmak.
