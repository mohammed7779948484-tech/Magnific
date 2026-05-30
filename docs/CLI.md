# CLI — أوامر سطر الأوامر

> توثيق كامل لجميع أوامر سطر الأوامر المتاحة مع الأمثلة والتفاصيل.

---

## التشغيل العام

```bash
python main.py <command> [options]
```

---

## الأمر: `serve`

تشغيل سيرفر API المحلي (FastAPI).

### الصيغة

```bash
python main.py serve --cookies <file> [options]
```

### الخيارات

| الخيار | النوع | الافتراضي | الوصف |
|--------|-------|----------|-------|
| `--cookies` | string | **مطلوب** | مسار ملف الكوكيز |
| `--base-url` | string | magnific.com | عنوان URL الأساسي |
| `--host` | string | `0.0.0.0` | عنوان الربط |
| `--port` | int | `8080` | منفذ السيرفر |
| `--poll-interval` | int | `5` | فترة فحص الحالة (ثواني) |
| `--poll-timeout` | int | `180` | مهلة التوليد (ثواني) |
| `--rate-limit` | int | `20` | حد الطلبات لكل دقيقة |
| `--log-level` | string | `info` | مستوى السجلات: debug, info, warning, error |

### أمثلة

**تشغيل أساسي:**
```bash
python main.py serve --cookies /path/to/pinj_magnific.txt
```

**تشغيل على منفذ مختلف:**
```bash
python main.py serve --cookies cookies.txt --port 3000
```

**تشغيل مع debug:**
```bash
python main.py serve --cookies cookies.txt --log-level debug
```

**ربط بموقع مختلف (freepik.com):**
```bash
python main.py serve --cookies cookies.txt --base-url https://www.freepik.com
```

---

## الأمر: `image`

توليد صورة باستخدام أحد نماذج الصور.

### الصيغة

```bash
python main.py image --cookies <file> -p <prompt> [options]
```

### الخيارات

| الخيار | النوع | الافتراضي | الوصف |
|--------|-------|----------|-------|
| `--cookies` | string | **مطلوب** | مسار ملف الكوكيز |
| `--base-url` | string | magnific.com | عنوان URL الأساسي |
| `-p` / `--prompt` | string | **مطلوب** | نص وصف الصورة |
| `-m` / `--model` | string | `imagen-nano-banana-2` | slug النموذج |
| `-r` / `--ratio` | string | `1:1` | نسبة العرض/الارتفاع |
| `-s` / `--res` | string | `4k` | الدقة: 1k, 2k, 4k |
| `-o` / `--output` | string | `output.png` | مسار ملف الإخراج |
| `--negative-prompt` | string | null | وصف ما لا تريده |
| `--reference` | string | — | صورة مرجعية (يمكن تكراره) |
| `--ref-type` | string | `reference` | نوع المرجع: reference, style |
| `--ref-category` | string | `product` | فئة المرجع |

### نسب العرض/الارتفاع المتاحة

`1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `21:9`

### النماذج المتاحة

| Slug | الاسم |
|------|-------|
| `imagen-nano-banana-2` | Nano Banana 2 |
| `imagen-nano-banana-pro` | Nano Banana Pro |
| `google-imagen-4` | Google Imagen 4 |
| `gpt-1-5-high` | GPT 1.5 High |
| `flux-2-pro` | Flux 2 Pro |
| `seedream-5-lite` | Seedream 5 Lite |

### أمثلة

**توليد صورة بسيطة (1:1, 4k):**
```bash
python main.py image --cookies cookies.txt \
  -p "a majestic golden dragon flying over a medieval castle at sunset" \
  -o dragon.png
```

**صورة 16:9 بدقة 2k:**
```bash
python main.py image --cookies cookies.txt \
  -p "a cyberpunk cityscape at night" \
  --ratio 16:9 --res 2k \
  -o cityscape.png
```

**صورة بنموذج محدد:**
```bash
python main.py image --cookies cookies.txt \
  -p "a photorealistic cat wearing sunglasses" \
  -m google-imagen-4 --ratio 1:1 --res 4k \
  -o cat.png
```

**صورة مع negative prompt:**
```bash
python main.py image --cookies cookies.txt \
  -p "a portrait of a woman" \
  --negative-prompt "blurry, low quality, watermark" \
  -o portrait.png
```

**صورة مع صورة مرجعية:**
```bash
python main.py image --cookies cookies.txt \
  -p "@hero in a futuristic armor standing in rain" \
  --reference "/path/to/hero.jpg|hero" \
  --ref-type reference --ref-category character \
  -o hero_armor.png
```

**صورة اقتصادية (Seedream 5 Lite):**
```bash
python main.py image --cookies cookies.txt \
  -p "a simple logo for a tech startup" \
  -m seedream-5-lite --res 1k \
  -o logo.png
```

**صورة عمودية (9:16):**
```bash
python main.py image --cookies cookies.txt \
  -p "a tall skyscraper against a sunset sky" \
  --ratio 9:16 --res 2k \
  -o skyscraper.png
```

---

## الأمر: `video`

توليد فيديو باستخدام أحد نماذج الفيديو.

### الصيغة

```bash
python main.py video --cookies <file> -p <prompt> [options]
```

### الخيارات

| الخيار | النوع | الافتراضي | الوصف |
|--------|-------|----------|-------|
| `--cookies` | string | **مطلوب** | مسار ملف الكوكيز |
| `--base-url` | string | magnific.com | عنوان URL الأساسي |
| `-p` / `--prompt` | string | **مطلوب** | نص وصف الفيديو |
| `-m` / `--model` | string | `bytedance-seedance-pro-2.0` | slug النموذج |
| `-r` / `--ratio` | string | `16:9` | نسبة العرض/الارتفاع |
| `-d` / `--duration` | int | `5` | المدة بالثواني |
| `--resolution` | string | `1080p` | الدقة: 1080p, 720p, 480p |
| `-o` / `--output` | string | `output.mp4` | مسار ملف الإخراج |
| `--negative-prompt` | string | `""` | وصف ما لا تريده |
| `--ref-image` | string | — | صورة مرجعية (file\|name أو url\|name) |
| `--ref-video` | string | — | فيديو مرجعي (file\|name أو url\|name) |
| `--ref-audio` | string | — | صوت مرجعي (file\|name أو url\|name) |
| `--sound` | flag | false | إضافة مؤثرات صوتية AI |

### النماذج المتاحة

| Slug | الاسم | المدة | Multi-shot | صوت |
|------|-------|-------|-----------|-----|
| `bytedance-seedance-pro-2.0` | Seedance 2.0 Pro | 4-15s | 6 | نعم |
| `bytedance-seedance-fast-2.0` | Seedance 2.0 Fast | 4-15s | 6 | نعم |
| `bytedance-seedance-pro-1.5` | Seedance 1.5 Pro | 4-15s | 3 | نعم |
| `bytedance-seedance-lite-1.5` | Seedance 1.5 Lite | 4-10s | 3 | نعم |
| `kling-omni3` | Kling Omni3 | 5-10s | 6 | لا |
| `kling-omni1` | Kling O1 | 5-10s | 0 | لا |
| `google-veo3_1` | Google Veo 3.1 | 8s | 0 | لا |
| `runway-act-two` | Runway Act Two | 5-10s | 0 | لا |
| `wan-2-7` | Wan 2.7 | 5-10s | 5 | لا |

### أمثلة

**فيديو بسيط (5 ثواني, 16:9):**
```bash
python main.py video --cookies cookies.txt \
  -p "a golden eagle soaring over mountains at sunrise" \
  -o eagle.mp4
```

**فيديو 10 ثواني بدقة 720p:**
```bash
python main.py video --cookies cookies.txt \
  -p "a cat playing with a ball of yarn" \
  --duration 10 --resolution 720p \
  -o cat.mp4
```

**فيديو مع مؤثرات صوتية:**
```bash
python main.py video --cookies cookies.txt \
  -p "thunderstorm over the ocean with lightning" \
  --duration 8 --sound \
  -o storm.mp4
```

**فيديو بنموذج سريع:**
```bash
python main.py video --cookies cookies.txt \
  -p "waves gently crashing on a beach at sunset" \
  -m bytedance-seedance-fast-2.0 --duration 5 \
  -o waves.mp4
```

**فيديو 21:9 (سينمائي):**
```bash
python main.py video --cookies cookies.txt \
  -p "a drone shot flying over a desert landscape" \
  --ratio 21:9 --duration 8 \
  -o desert.mp4
```

**فيديو مع صورة مرجعية:**
```bash
python main.py video --cookies cookies.txt \
  -p "the person walks slowly through the corridor" \
  --ref-image "/path/to/person.jpg|hero" \
  -o walking.mp4
```

**فيديو مع صورة مرجعية من URL:**
```bash
python main.py video --cookies cookies.txt \
  -p "animate this scene with gentle camera movement" \
  --ref-image "https://example.com/image.jpg|scene" \
  -o animated.mp4
```

**فيديو عمودي (9:16):**
```bash
python main.py video --cookies cookies.txt \
  -p "a vertical pan of a waterfall in a tropical forest" \
  --ratio 9:16 --duration 6 \
  -o waterfall.mp4
```

**فيديو بدقة منخفضة (480p) للاقتصاد:**
```bash
python main.py video --cookies cookies.txt \
  -p "a simple animation of a bouncing ball" \
  --resolution 480p --duration 4 \
  -o ball.mp4
```

---

## الأمر: `models`

عرض قائمة جميع النماذج المتاحة.

### الصيغة

```bash
python main.py models
```

### المخرجات

```
============================================================
  Available Image Models
============================================================
  imagen-nano-banana-2          Nano Banana 2               credits: 75-150
  imagen-nano-banana-pro        Nano Banana Pro              credits: 100-200
  google-imagen-4               Google Imagen 4              credits: 75-150
  gpt-1-5-high                 GPT 1.5 High                credits: 100-200
  flux-2-pro                    Flux 2 Pro                  credits: 50-175
  seedream-5-lite              Seedream 5 Lite             credits: 50

============================================================
  Available Video Models
============================================================
  bytedance-seedance-pro-2.0    Seedance 2.0 Pro            duration: 4-15s
  bytedance-seedance-fast-2.0   Seedance 2.0 Fast           duration: 4-15s
  ...
```

---

## Auto-Retry عند Rate Limit

أمر `video` يحتوي على آلية إعادة محاولة تلقائية عند استلام HTTP 429:

- **عدد المحاولات**: 5
- **الانتظار**: 15s × (رقم المحاولة) = 15s, 30s, 45s, 60s, 75s
- **السبب**: منصة Magnific تسمح بعدد محدود من التوليدات المتزامنة

يمكن رؤية الرسائل في السجلات:
```
WARNING | Rate limited, waiting 15s before retry (1/5)...
WARNING | Rate limited, waiting 30s before retry (2/5)...
```
