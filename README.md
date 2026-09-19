# 🎥 Recorder CLI (v0.3.0)

Wayland masaüstü ortamları (Hyprland, Sway, GNOME, KDE) için donanım hızlandırmalı (GPU VAAPI/NVENC), döngüsel bellekli (dashcam/circular loop) sürekli ekran ve ses kayıt aracı.

Arka planda [`gpu-screen-recorder`](https://git.dec05eba.com/gpu-screen-recorder/about/) motorunu kullanarak CPU'ya neredeyse hiç yük bindirmeden doğrudan GPU video kodlayıcısı üzerinden 60-144 FPS hızında kristal netliğinde kayıt alır.

---

## ✨ Özellikler

- **Donanım Hızlandırmalı Kodlama (GPU):** AMD (VAAPI), NVIDIA (NVENC) ve Intel üzerinde yerel **HEVC (H.265)**, **AV1** ve **H.264** desteği.
- **Sürekli Döngüsel Kayıt (Circular Buffer / Dashcam):** Belirlenen segment süresinde (varsayılan 30 dk) kayıt alır. Belirlenen maksimum video sınırına ulaşıldığında en eski videoyu otomatik silerek diski şişirmez.
- **Çift Ses Yakalama:** Masaüstü sistem sesini ve mikrofonu PipeWire/PulseAudio üzerinden eşzamanlı gecikmesiz kaydeder.
- **Kesintisiz Systemd Entegrasyonu:** `graphical-session.target`'a bağlı olarak sistem açılışında otomatik başlar, oturum kapandığında videoyu yarım bırakmadan temizce MP4 olarak finalize eder.
- **Akıllı Ortam Tespiti & Hata Koruması:** Erken açılışta `WAYLAND_DISPLAY` henüz oturuma aktarılmamışsa bekleme ve kurtarma (exponential backoff) uygular, hayalet dosya oluşturmaz.
- **Çözünürlük Ölçekleme & En-Boy Koruması:** 1080p, 2K (1440p), 4K, 720p veya özel çözünürlük desteği. 16:9 ve 16:10 ekran oranını otomatik algılayıp videoda esneme/bozulma olmadan orantılı ölçekler.
- **Hazır Kalite & Performans Profilleri (Presets):** Tek tıkla veya tek komutla `performance` (1080p 30fps), `balanced` (1080p 60fps), `quality` (2K 60fps), `ultra` (Native 60fps) veya `esports` (1080p 120fps) seçimi.
- **Modern Rich TUI Arayüzü:** Canlı renkli durum paneli, profil ve çözünürlük seçicisi, video tablosu, disk kullanım özeti ve etkileşimli ayar menüsü.

---

## 📦 Gereksinimler

- **İşletim Sistemi:** Wayland tabanlı herhangi bir Linux dağıtımı (Arch / CachyOS, Fedora, Ubuntu, openSUSE).
- **Donanım Kodlayıcı:** `gpu-screen-recorder`
- **Python:** Python 3.8+ (Önerilen: `uv` veya `python3-venv`)
- **Oynatıcı:** `mpv` (veya sistem varsayılan video oynatıcısı)
- **Bildirimler:** `libnotify` (`notify-send`)

Arch / CachyOS için hızlı kurulum:
```bash
sudo pacman -S --needed gpu-screen-recorder mpv libnotify
```

---

## 🚀 Kurulum

### Seçenek 1: Hızlı Otomatik Kurulum (Önerilen)
Tüm sistem bağımlılıklarını (`gpu-screen-recorder`, `mpv`, `libnotify`) otomatik kurar, depoyu çeker ve yapılandırır:

```bash
curl -sSL https://raw.githubusercontent.com/KadirBerkpolat1/recorder-cli/main/setup.sh | bash
```

### Seçenek 2: Manuel Klonlama
```bash
git clone https://github.com/KadirBerkpolat1/recorder-cli.git
cd recorder-cli
./install.sh
```

Kurulum betiği `uv` yüklüyse otomatik algılayıp saniyeler içinde sanal ortamı kurar, eksik sistem paketlerini (`mpv` vb.) tamamlar, systemd servisini kaydeder ve `recorder` komutunu `~/.local/bin/recorder` olarak kullanımınıza sunar.
---

## 💻 Komut Referansı (CLI)

| Komut | Açıklama |
|---|---|
| `recorder` | Etkileşimli Rich TUI kontrol panelini açar (durum, videolar, ayarlar). |
| `recorder record` | Arka planda ekran kaydını başlatır (`--profile`, `--res`, `--fps`, `--quality` bayraklarıyla geçici override edilebilir). |
| `recorder profile [ad]` | Kalite ve performans profillerini listeler veya uygular (örn: `recorder profile performance`). |
| `recorder stop` | Aktif kaydı zarifçe durdurur ve videoyu MP4 olarak finalize edip kaydeder. |
| `recorder status` | Kayıt, profil, çözünürlük, systemd servisi, donanım codec'i ve disk durumunu gösterir. |
| `recorder play [no]` | Belirtilen kaydı `mpv` ile oynatır (numara verilmezse en son videoyu açar). |
| `recorder open` | Kayıtların tutulduğu `~/Record` klasörünü dosya yöneticisinde (Dolphin vb.) açar. |
| `recorder delete <no>` | Belirtilen numaralı kaydı hem veritabanından hem diskten siler. |
| `recorder clean` | Tüm kayıtları onay alarak diskten temizler. |
| `recorder service <eylem>` | Systemd servisini yönetir (`enable`, `disable`, `start`, `stop`, `status`, `install`). |

---

## ⚙️ Yapılandırma (`config.json`)

Ayar dosyası `~/.config/recorder-cli/config.json` altında tutulur. TUI içindeki **Ayarlar (Settings)** menüsünden veya doğrudan JSON düzenlenerek değiştirilebilir:

```json
{
    "max_duration_sec": 1800,
    "max_recordings": 5,
    "record_mic": true,
    "codec": "hevc",
    "fps": 60,
    "quality": "very_high",
    "resolution": "native",
    "preset": "custom",
    "monitor": "screen",
    "notifications": true
}
```

### 🎯 Hazır Profiller (Presets):
| Profil Kodu | Profil Adı | Çözünürlük | FPS | Kalite | Kullanım Amacı |
|---|---|---|---|---|---|
| `performance` | ⚡ Performans | 1080p (FHD) | 30 | Medium | Düşük donanım / laptop / sıfır kasma, minimal disk yazımı. |
| `balanced` | ⚖️ Dengeli | 1080p (FHD) | 60 | High | Akıcı ve dengeli standart oyun kaydı. |
| `quality` | 🎬 Yüksek Kalite | 1440p (2K) | 60 | Very High | Güçlü sistemler ve masaüstü bilgisayarlar için. |
| `ultra` | 💎 Ultra | Native (1:1) | 60 | Ultra | Orijinal ekran çözünürlüğünde kayıpsız detay. |
| `esports` | 🚀 Espor | 1080p (FHD) | 120 | High | Hızlı FPS oyunlarında maksimum kare akıcılığı. |

### Parametre Detayları:
- `codec`: `hevc` (H.265 - önerilen), `av1` (yeni nesil yüksek sıkıştırma) veya `h264`.
- `fps`: `60`, `120`, `144` veya istenen kare hızı.
- `quality`: `ultra`, `very_high`, `high`, `medium`.
- `max_duration_sec`: Bir video dosyasının maksimum süresi (örn: 1800 sn = 30 dakika).
- `max_recordings`: `~/Record` altında tutulacak maksimum dosya sayısı (döngüsel silme).
- `record_mic`: `true` ise mikrofon ve masaüstü sesi birlikte kaydedilir.
- `monitor`: Kaydedilecek ekran (`screen` veya `DP-2`, `HDMI-A-1` gibi özel monitör adı).
- `notifications`: `true` ise masaüstü bildirimleri gönderilir.

---

## 🔄 Otomatik Açılış (Systemd User Service)

Bilgisayarı açtığınızda masaüstü oturumunun otomatik olarak arka planda sürekli kaydedilmesini (ve sadece son 5 videoyu tutmasını) istiyorsanız:

```bash
recorder service enable
```

Devre dışı bırakmak için:
```bash
recorder service disable
```

Servis, Wayland oturumuna (`graphical-session.target`) kilitlidir. Oturum kapatıldığında veya yeniden başlatıldığında o ana kadarki kaydı bozmadan son saniyesine kadar MP4 olarak kaydeder.

---

## 📁 Kayıt Formatı

Videolar `~/Record` dizinine şu formatta yazılır:
```text
YYYY-MM-DD_HH-MM-SS_HH-MM.mp4
Örnek: 2026-09-19_13-40-46_13-40.mp4
```

---

## 🗑️ Kaldırma (Uninstall)

Uygulamayı, arka plan servisini ve binary kısayollarını sistemden tamamen temizlemek için proje dizinindeki kaldırma betiğini çalıştırmanız yeterlidir:

```bash
cd recorder-cli
./uninstall.sh
```

`uninstall.sh` betiği:
1. Çalışan systemd servisini durdurur ve devre dışı bırakır (`systemctl --user stop/disable recorder.service`).
2. Varsa arka planda kalan kayıt işlemlerini sonlandırır.
3. Systemd servis dosyasını ve hedef bağlantılarını temizler.
4. `~/.local/bin/recorder` kısayolunu ve `~/.local/share/recorder-cli` dosyalarını siler.
5. İsteğe bağlı olarak yapılandırma (`~/.config/recorder-cli`) ve kaydedilen videoları (`~/Record`) silmek isteyip istemediğinizi sorar.
