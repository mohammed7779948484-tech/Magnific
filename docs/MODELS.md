# MODELS — توثيق جميع النماذج

> قائمة شاملة لجميع نماذج الذكاء الاصطناعي المدعومة مع تفاصيل كل نموذج، القدرات، القيود، والأمثلة.

---

## نظرة عامة

المشروع يدعم حالياً **7 نماذج صور** و **11 نموذج فيديو**. جميع النماذج مسجلة تلقائياً في `ModelRegistry` عند تشغيل المشروع.

لعرض القائمة في CLI:
```bash
python main.py models
```

لعرضها عبر API:
```bash
GET /api/models
```

---

## نماذج الصور (Image Models)

جميع نماذج الصور تستخدم نفس تدفق العمل:
1. `start-tti-v2` — الحصول على request_token
2. `render/v4` — بدء التوليد والحصول على creation_id

### ملخص نماذج الصور

| النموذج | Slug | الكريديت | الدقات | Max Refs |
|---------|------|----------|--------|----------|
| Nano Banana 2 | `imagen-nano-banana-2` | 75-150 | 1k, 2k, 4k | 14 |
| Nano Banana Pro | `imagen-nano-banana-pro` | 100-200 | 1k, 2k, 4k | 14 |
| Google Imagen 4 | `google-imagen-4` | 75-150 | 1k, 2k, 4k | 14 |
| GPT 1.5 High | `gpt-1-5-high` | 100-200 | 1k, 2k, 4k | 14 |
| Flux 2 Pro | `flux-2-pro` | 50-175 | 1k, 2k, 4k | 14 |
| GPT 2 | `gpt-2` | 25-2100 | 1k, 2k, 4k | 16 |
| Seedream 5 Lite | `seedream-5-lite` | 50 | **1k فقط** | 14 |

---

### Nano Banana 2

**الملف**: `models/image/nano_banana_2.py`

```
Slug:        imagen-nano-banana-2
Display:     Nano Banana 2
Credits:     75-150
Resolutions: 1k, 2k, 4k
Max Refs:    14
```

**الوصف**: نموذج سريع ومتوازن. جيد للاستخدام العام مع جودة عالية. يُعد الخيار الافتراضي في CLI.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "a futuristic city at night with neon lights" \
  -m imagen-nano-banana-2 --ratio 16:9 --res 4k
```

---

### Nano Banana Pro

**الملف**: `models/image/nano_banana_pro.py`

```
Slug:        imagen-nano-banana-pro
Display:     Nano Banana Pro
Credits:     100-200
Resolutions: 1k, 2k, 4k
Max Refs:    14
```

**الوصف**: نسخة محسنة من Nano Banana مع تفاصيل أعلى وجودة أفضل. يستهلك كريديت أكثر.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "a photorealistic portrait of an astronaut" \
  -m imagen-nano-banana-pro --ratio 1:1 --res 4k
```

---

### Google Imagen 4

**الملف**: `models/image/google_imagen_4.py`

```
Slug:        google-imagen-4
Display:     Google Imagen 4
Credits:     75-150
Resolutions: 1k, 2k, 4k
Max Refs:    14
```

**الوصف**: نموذج Google Imagen الرابع. ممتاز في فهم التعليمات المعقدة وتوليد صور واقعية.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "a cute cat wearing a tiny hat, sitting on a bookshelf, soft lighting" \
  -m google-imagen-4 --ratio 4:3 --res 2k
```

---

### GPT 1.5 High

**الملف**: `models/image/gpt_1_5_high.py`

```
Slug:        gpt-1-5-high
Display:     GPT 1.5 High
Credits:     100-200
Resolutions: 1k, 2k, 4k
Max Refs:    14
```

**الوصف**: نموذج عالي الجودة. يستهلك كريديت أكثر لكن يُنتج نتائج متقدمة.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "a mystical forest with bioluminescent mushrooms and fireflies" \
  -m gpt-1-5-high --ratio 1:1 --res 4k
```

---

### Flux 2 Pro

**الملف**: `models/image/flux_2_pro.py`

```
Slug:        flux-2-pro
Display:     Flux 2 Pro
Credits:     50-175
Resolutions: 1k, 2k, 4k
Max Refs:    14
```

**الوصف**: نموذج Flux 2 Pro. ممتاز في الأساليب الفنية والتصميم الإبداعي.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "an oil painting of a Venetian canal at golden hour, impressionist style" \
  -m flux-2-pro --ratio 3:2 --res 2k
```

---

### GPT 2

**الملف**: `models/image/gpt_2.py`

```
Slug:          gpt-2
Display:       GPT 2
Credits:       25-2100
Resolutions:   1k, 2k, 4k
Max Refs:      16
Max Prompt:     10000 حرف
Num Images:     1-8 صور
Quality:       low, medium, high
Smart Prompt:   نعم (افتراضي)
Seed:          مدعوم
Color Palette: مدعوم (max 6 ألوان)
Effects:       مدعوم
Camera:        مدعوم
Character:     مدعوم
```

**الوصف**: أحدث نموذج OpenAI GPT 2 للصور. أرخص نموذج (25 كريديت) مع أعلى حد صور مرجعية (16). يدعم 11 نسبة عرض/ارتفاع، توليد 1-8 صور، مستويات جودة، smart prompt، seed، effects، camera. الأفضل لـ text_layout, infographic, ui_design, diagram, typography.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "a professional infographic about renewable energy, clean layout, charts and icons" \
  -m gpt-2 --ratio 16:9 --res 4k
```

---

### Seedream 5 Lite

**الملف**: `models/image/seedream_5_lite.py`

```
Slug:        seedream-5-lite
Display:     Seedream 5 Lite
Credits:     50
Resolutions: 1k فقط
Max Refs:    14
```

**الوصف**: نموذج خفيف وسريع. أرخص من حيث الكريديت (50 ثابت). لكنه يدعم **الدقة 1k فقط**. مناسب للاستخدام السريع والتجارب.

**مثال:**
```bash
python main.py image --cookies cookies.txt \
  -p "a simple logo design for a coffee shop" \
  -m seedream-5-lite --ratio 1:1 --res 1k
```

---

## نماذج الفيديو (Video Models)

جميع نماذج الفيديو تستخدم endpoint واحد:
- `POST /api/video/generate` — يُرجع creation_id

### ملخص نماذج الفيديو

| النموذج | Slug | العائلة | المدة | Img Refs | Vid Refs | Audio | Multi-shot | صوت | Keyframes |
|---------|------|---------|-------|----------|----------|-------|-----------|-----|-----------|
| Seedance 2.0 Pro | `bytedance-seedance-pro-2.0` | bytedance | 4-15s | 9 | 2 | 2 | 6 | نعم | start, end |
| Seedance 2.0 Fast | `bytedance-seedance-fast-2.0` | bytedance | 4-15s | 9 | 2 | 2 | 6 | نعم | start, end |
| Seedance 1.5 Pro | `bytedance-seedance-pro-1.5` | bytedance | 4-15s | 0 | 0 | 2 | 3 | نعم | start |
| Seedance 1.5 Lite | `bytedance-seedance-lite-1.5` | bytedance | 4-10s | 4 | 0 | 2 | 3 | نعم | start |
| Kling 3.0 | `kling-30` | kling | 3-15s | 12 | 0 | 0 | 6 | نعم | start, end |
| Kling 3.0 MC | `kling-motion-control-30` | kling | 3-15s | 1 | 1 | 0 | 0 | لا | start, video |
| Kling 3.0 Omni | `kling-omni3` | kling | 3-15s | 7 | 1 | 0 | 6 | نعم | start, end |
| Kling O1 | `kling-omni1` | kling | 5-10s | 7 | 1 | 0 | 0 | لا | start, end |
| Google Veo 3.1 | `google-veo3_1` | google | 8s ثابت | 3 | 0 | 0 | 0 | لا | start |
| Runway Act Two | `runway-act-two` | runway | 5-10s | 2 | 0 | 0 | 0 | لا | start |
| Wan 2.7 | `wan-2-7` | wan | 5-10s | 5 | 1 | 0 | 5 | لا | start, end |

---

### Seedance 2.0 Pro

**الملف**: `models/video/seedance_2_pro.py`

```
Slug:          bytedance-seedance-pro-2.0
Display:       Seedance 2.0 Pro
API:           bytedance
Model:         seedance
Mode:          pro-2.0
Family:        bytedance
Duration:      4-15 ثواني
Resolutions:   1080p, 720p, 480p
Image Refs:    9
Video Refs:    2
Audio Refs:    2
Multi-shot:    6 مشاهد
Sound Effects: نعم
Keyframes:     start, end
```

**الوصف**: أقوى نموذج فيديو في المشروع. يدعم كل المميزات: صور مرجعية متعددة، فيديو مرجعي، صوت، multi-shot، keyframes في البداية والنهاية. الخيار الافتراضي في CLI.

**مثال CLI:**
```bash
python main.py video --cookies cookies.txt \
  -p "a golden eagle soaring over snow-capped mountains at sunrise, cinematic aerial shot" \
  -m bytedance-seedance-pro-2.0 --ratio 16:9 --duration 10 --resolution 1080p
```

**مثال API:**
```json
{
  "prompt": "camera zooms into a flower blooming in timelapse",
  "model": "bytedance-seedance-pro-2.0",
  "aspect_ratio": "16:9",
  "duration": 8,
  "keyframes": {
    "start": {"type": "image", "url": "/path/to/wide-shot.jpg"},
    "end": {"type": "image", "url": "/path/to/close-up.jpg"}
  },
  "with_sound": true
}
```

---

### Seedance 2.0 Fast

**الملف**: `models/video/seedance_2_fast.py`

```
Slug:          bytedance-seedance-fast-2.0
Display:       Seedance 2.0 Fast
API:           bytedance
Model:         seedance
Mode:          fast-2.0
Family:        bytedance
Duration:      4-15 ثواني
Resolutions:   1080p, 720p, 480p
Image Refs:    9
Video Refs:    2
Audio Refs:    2
Multi-shot:    6 مشاهد
Sound Effects: نعم
Keyframes:     start, end
```

**الوصف**: نفس قدرات Seedance 2.0 Pro لكن أسرع في التوليد. جودة مماثلة لكن قد تكون أقل دقة في الحركات المعقدة.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "waves crashing on a rocky shore, slow motion" \
  -m bytedance-seedance-fast-2.0 --ratio 16:9 --duration 5
```

---

### Seedance 1.5 Pro

**الملف**: `models/video/seedance_1_5_pro.py`

```
Slug:          bytedance-seedance-pro-1.5
Display:       Seedance 1.5 Pro
API:           bytedance
Model:         seedance
Mode:          pro-1.5
Family:        bytedance
Duration:      4-15 ثواني
Image Refs:    0
Video Refs:    0
Audio Refs:    2
Multi-shot:    3 مشاهد
Sound Effects: نعم
Keyframes:     start فقط
```

**الوصف**: نسخة سابقة من Seedance. يدعم صوت وmulti-shot لكن **لا يدعم صور مرجعية** (image refs = 0). يدعم keyframe في البداية فقط.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a serene Japanese garden with cherry blossoms falling" \
  -m bytedance-seedance-pro-1.5 --duration 8 --sound
```

---

### Seedance 1.5 Lite

**الملف**: `models/video/seedance_1_5_lite.py`

```
Slug:          bytedance-seedance-lite-1.5
Display:       Seedance 1.5 Lite
API:           bytedance
Model:         seedance
Mode:          lite-1.5
Family:        bytedance
Duration:      4-10 ثواني
Image Refs:    4
Video Refs:    0
Audio Refs:    2
Multi-shot:    3 مشاهد
Sound Effects: نعم
Keyframes:     start فقط
```

**الوصف**: نسخة خفيفة من Seedance 1.5. يدعم 4 صور مرجعية (أكثر من Pro 1.5) لكن مدة أقصى 10 ثواني.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a cat walking through a garden" \
  -m bytedance-seedance-lite-1.5 --duration 5
```

---

### Kling 3.0

**الملف**: `models/video/kling_30.py`

```
Slug:          kling-30
Display:       Kling 3.0
API:           kling
Model:         kling
Mode:          30
Family:        kling
Duration:      3-15 ثواني
Resolutions:   720p, 1080p, 4K
Image Refs:    12
Video Refs:    0
Audio Refs:    0
Multi-shot:    6 مشاهد
Sound Effects: نعم
Keyframes:     start, end
FPS:           24
Credits:       210-6000
```

**الوصف**: أحدث نموذج Kling 3.0. يدعم **4K** (أول نموذج Kling يدعمها)، مدة أوسع 3-15 ثانية، 12 صورة مرجعية (start frame + end frame + 3 character + 3 product + 3 advanced)، مؤثرات صوتية، multi-shot 6 مشاهد، و24 حركة كاميرا. نموذج beta/experimental.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a samurai standing in a field of red flowers, wind blowing" \
  -m kling-30 --ratio 16:9 --duration 10 --resolution 4K --sound
```

---

### Kling 3.0 Motion Control

**الملف**: `models/video/kling_motion_control_30.py`

```
Slug:          kling-motion-control-30
Display:       Kling 3.0 Motion Control
API:           kling
Model:         kling
Mode:          motion-control-30
Family:        kling
Duration:      3-15 ثواني
Resolutions:   720p, 1080p
Image Refs:    1 (إلزامي - start frame)
Video Refs:    1 (إلزامي - فيديو مرجعي)
Audio Refs:    0
Multi-shot:    0
Sound Effects: لا
Keyframes:     start, video (لا يدعم end)
FPS:           24
Credits:       330-2250
```

**الوصف**: نموذج خاص لتحكم الحركة. يتطلب **صورة start frame + فيديو مرجعي** (كلاهما إلزامي). يدعم motion control و lipsync. نسبة العرض/الارتفاع تُستنتج تلقائياً من الـ start frame. لا يدعم 4K أو multi-shot أو صوت.

**ملاحظة مهمة**: هذا النموذج يختلف عن بقية النماذج — يجب توفير صورة وإطار فيديو كمُدخلات إلزامية.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "slowly zoom into the character's face" \
  -m kling-motion-control-30 --duration 8
```

---

### Kling 3.0 Omni

**الملف**: `models/video/kling_omni3.py`

```
Slug:          kling-omni3
Display:       Kling 3.0 Omni
API:           kling
Model:         kling
Mode:          omni3
Family:        kling
Duration:      3-15 ثواني
Resolutions:   720p, 1080p, 4K
Image Refs:    7
Video Refs:    1
Audio Refs:    0
Multi-shot:    6 مشاهد
Sound Effects: نعم
Keyframes:     start, end
FPS:           24
Credits:       210-6000
```

**الوصف**: نموذج Kling 3.0 Omni. يدعم 7 صور مرجعية + 1 فيديو مرجعي + multi-shot 6 مشاهد + مؤثرات صوتية + دقة 4K. يدعم أيضاً lipsync. أفضل لـ realistic_videos, character_animation, scene_transitions.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a warrior charging into battle with a sword" \
  -m kling-omni3 --ratio 16:9 --duration 10 --resolution 4K --sound
```

---

### Kling O1

**الملف**: `models/video/kling_o1.py`

```
Slug:          kling-omni1
Display:       Kling O1
API:           kling
Model:         kling
Mode:          omni1
Family:        kling
Duration:      5-10 ثواني
Image Refs:    7
Video Refs:    1
Audio Refs:    0
Multi-shot:    0
Sound Effects: لا
Keyframes:     start, end
```

**الوصف**: نموذج Kling O1. مثل Omni3 لكن بدون multi-shot. يدعم 7 صور مرجعية و1 فيديو مرجعي.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a robot dancing in a neon-lit street" \
  -m kling-omni1 --duration 5
```

---

### Google Veo 3.1

**الملف**: `models/video/google_veo_3_1.py`

```
Slug:          google-veo3_1
Display:       Google Veo 3.1
API:           google
Model:         veo3
Mode:          3_1
Family:        google
Duration:      8 ثواني (ثابت)
Image Refs:    3
Video Refs:    0
Audio Refs:    0
Multi-shot:    0
Sound Effects: لا
Keyframes:     start فقط
```

**الوصف**: نموذج Google Veo 3.1. مدة **ثابتة 8 ثواني** فقط. يدعم 3 صور مرجعية. لا يدعم صوت أو multi-shot.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a time-lapse of a flower blooming" \
  -m google-veo3_1 --ratio 16:9
```

---

### Runway Act Two

**الملف**: `models/video/runway_act_two.py`

```
Slug:          runway-act-two
Display:       Runway Act Two
API:           runway
Model:         runway
Mode:          act-two
Family:        runway
Duration:      5-10 ثواني
Image Refs:    2
Video Refs:    0
Audio Refs:    0
Multi-shot:    0
Sound Effects: لا
Keyframes:     start فقط
```

**الوصف**: نموذج Runway Act Two. يدعم 2 صور مرجعية فقط. أبسط النماذج من حيث القدرات.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "smoke rising from a candle in a dark room" \
  -m runway-act-two --duration 5
```

---

### Wan 2.7

**الملف**: `models/video/wan_2_7.py`

```
Slug:          wan-2-7
Display:       Wan 2.7
API:           wan
Model:         wan
Mode:          2.7
Family:        wan
Duration:      5-10 ثواني
Image Refs:    5
Video Refs:    1
Audio Refs:    0
Multi-shot:    5 مشاهد
Sound Effects: لا
Keyframes:     start, end
```

**الوصف**: نموذج Wan 2.7. يدعم 5 صور مرجعية + 1 فيديو مرجعي + multi-shot 5 مشاهد + keyframes.

**مثال:**
```bash
python main.py video --cookies cookies.txt \
  -p "a dragon flying through storm clouds" \
  -m wan-2-7 --ratio 21:9 --duration 10
```

---

## نسب العرض/الارتفاع المتاحة

جميع النماذج تدعم النسب التالية:

| النسبة | الأبعاد (1k) | الأبعاد (2k) | الأبعاد (4k) |
|--------|-------------|-------------|-------------|
| `1:1` | 1024×1024 | 2048×2048 | 4096×4096 |
| `16:9` | 1344×768 | 2688×1536 | 5376×3072 |
| `9:16` | 768×1344 | 1536×2688 | 3072×5376 |
| `4:3` | 1152×896 | 2304×1792 | 4608×3584 |
| `3:4` | 896×1152 | 1792×2304 | 3584×4608 |
| `3:2` | 1216×832 | 2432×1664 | 4864×3328 |
| `2:3` | 832×1216 | 1664×2432 | 3328×4864 |
| `21:9` | 1536×640 | 3072×1280 | 6144×2560 |

> **ملاحظة**: نماذج الفيديو تدعم 720p, 1080p, 4K (النماذج الجديدة تدعم 4K).

---

## فئات المراجع (Reference Categories)

| الفئة | القيمة | الوصف |
|-------|--------|-------|
| شخصية | `character` | شخصية بشرية أو متحركة |
| منتج | `product` | منتج تجاري |
| صورة | `image` | صورة عامة |
| تكوين | `composition` | تخطيط/تكوين المشهد |
| أسلوب | `style` | أسلوب فني |

---

## كيف تختار النموذج المناسب؟

### للصور:
- **أرخص + مرونة عالية**: `gpt-2` (25-2100 credits, 16 refs, smart prompt)
- **سرعة + اقتصاد**: `seedream-5-lite` (50 credit, 1k فقط)
- **توازن جودة/سعر**: `imagen-nano-banana-2` أو `google-imagen-4` (75-150 credits)
- **أعلى جودة**: `imagen-nano-banana-pro` أو `gpt-1-5-high` (100-200 credits)
- **أساليب فنية**: `flux-2-pro` (50-175 credits)

### للفيديو:
- **أقوى نموذج (كل المميزات)**: `bytedance-seedance-pro-2.0`
- **سرعة + كل المميزات**: `bytedance-seedance-fast-2.0`
- **أحدث Kling (4K + صوت + 12 refs)**: `kling-30`
- **تحكم حركة + lipsync**: `kling-motion-control-30`
- **كثير صور مرجعية + فيديو ref + 4K**: `kling-omni3`
- **صوت مطلوب بدون refs**: `bytedance-seedance-pro-1.5`
- **مدة ثابتة 8s**: `google-veo3_1`
- **بسيط وسريع**: `runway-act-two`
