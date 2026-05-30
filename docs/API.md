# API — توثيق سيرفر API المحلي

> توثيق كامل لجميع endpoints الخاصة بسيرفر FastAPI المحلي، بما في ذلك الطلبات والاستجابات والأمثلة.

---

## تشغيل السيرفر

```bash
python main.py serve \
  --cookies /path/to/pinj_magnific.txt \
  --port 8080 \
  --host 0.0.0.0 \
  --rate-limit 20 \
  --poll-interval 5 \
  --poll-timeout 180
```

بعد التشغيل:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc
- **OpenAPI JSON**: http://localhost:8080/openapi.json

---

## نظرة عامة على الـ Endpoints

| الطريقة | المسار | الوصف |
|--------|--------|-------|
| `POST` | `/api/image/generate` | توليد صورة |
| `POST` | `/api/video/generate` | توليد فيديو |
| `GET` | `/api/health` | فحص حالة السيرفر |
| `GET` | `/api/status/{creation_id}` | فحص حالة توليد |
| `GET` | `/api/models` | قائمة النماذج المتاحة |

---

## POST /api/image/generate

توليد صورة باستخدام أحد نماذج الصور المتاحة.

### Request Body (ImageRequest)

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `prompt` | string | — | نعم | نص وصف الصورة |
| `model` | string | `imagen-nano-banana-2` | لا | slug النموذج |
| `aspect_ratio` | string | `1:1` | لا | نسبة العرض/الارتفاع |
| `resolution` | string | `4k` | لا | الدقة: `1k`, `2k`, `4k` |
| `negative_prompt` | string\|null | null | لا | وصف ما لا تريده |
| `references` | array | [] | لا | صور مرجعية |
| `num_images` | int | 1 | لا | عدد الصور |
| `seed` | int\|null | null | لا | بذرة عشوائية (للتكرار) |
| `wait` | bool | true | لا | انتظر حتى الاكتمال |
| `download` | bool | false | لا | أعد الصورة كـ base64 |

### Reference Object (ImageReferenceInput)

| الحقل | النوع | افتراضي | الوصف |
|-------|-------|---------|-------|
| `image_base64` | string\|null | null | صورة base64 data URI |
| `image_path` | string\|null | null | مسار ملف محلي |
| `label` | string | — | اسم المرجع (يصبح @label في prompt) |
| `type` | string | `reference` | نوع المرجع: reference أو style |
| `category` | string | `product` | فئة: character, product, image, composition, style |

### Response (ImageResponse)

```json
{
  "success": true,
  "creation_id": 3070624230,
  "family": "a1e7fe0e-01a3-4c3e-9173-cfc43fc4382a",
  "status": "completed",
  "image_url": "https://pikaso.cdnpk.net/...",
  "image_base64": null,
  "message": null,
  "elapsed": 53.2
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح العملية |
| `creation_id` | int\|null | معرف التوليد |
| `family` | string\|null | معرف عائلة النموذج |
| `status` | string | processing / completed / error |
| `image_url` | string\|null | رابط تحميل الصورة |
| `image_base64` | string\|null | الصورة base64 (فقط إذا download=true) |
| `message` | string\|null | رسالة حالة أو خطأ |
| `elapsed` | float\|null | الوقت المستغرق بالثواني |

### أمثلة

**توليد صورة بسيطة:**
```bash
curl -X POST http://localhost:8080/api/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a golden dragon flying over mountains",
    "model": "imagen-nano-banana-2",
    "aspect_ratio": "1:1",
    "resolution": "2k"
  }'
```

**توليد بدون انتظار (async):**
```bash
curl -X POST http://localhost:8080/api/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a sunset over the ocean",
    "wait": false
  }'
# Response: {"success": true, "status": "processing", "creation_id": 12345}
# ثم: GET /api/status/12345?type=image
```

**توليد مع صورة مرجعية:**
```bash
curl -X POST http://localhost:8080/api/image/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "@hero holding a glowing sword",
    "model": "google-imagen-4",
    "references": [{
      "image_path": "/path/to/hero.jpg",
      "label": "hero",
      "type": "reference",
      "category": "character"
    }]
  }'
```

---

## POST /api/video/generate

توليد فيديو باستخدام أحد نماذج الفيديو المتاحة.

### Request Body (VideoRequest)

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `prompt` | string | — | نعم | نص وصف الفيديو |
| `model` | string | `bytedance-seedance-pro-2.0` | لا | slug النموذج |
| `aspect_ratio` | string | `16:9` | لا | نسبة العرض/الارتفاع |
| `duration` | int | 5 | لا | المدة بالثواني |
| `resolution` | string | `1080p` | لا | الدقة: `1080p`, `720p`, `480p` |
| `negative_prompt` | string | `""` | لا | وصف ما لا تريده |
| `references` | array | [] | لا | مراجع (صور/فيديو/صوت) |
| `keyframes` | object\|null | null | لا | إطارات رئيسية (start/end) |
| `audio_url` | string\|null | null | لا | رابط صوت خلفي |
| `with_sound` | bool | false | لا | إضافة مؤثرات صوتية AI |
| `prompt_type` | string | `basic` | لا | basic أو multishot |
| `seed` | int\|null | null | لا | بذرة عشوائية |
| `wait` | bool | true | لا | انتظر حتى الاكتمال |
| `download` | bool | false | لا | أعد الفيديو كـ base64 |

### Reference Object (VideoReferenceInput)

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `type` | string | نوع المرجع: image, video, audio |
| `url` | string | رابط CDN أو مسار ملف محلي |
| `name` | string | اسم المرجع |

### Keyframe Object (KeyframeInput)

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `type` | string | نوع الإطار: image, video, sketch |
| `url` | string | رابط أو مسار صورة الإطار |

### Response (VideoResponse)

```json
{
  "success": true,
  "creation_id": 3070643635,
  "status": "completed",
  "video_url": "https://pikaso.cdnpk.net/...",
  "video_base64": null,
  "message": null,
  "elapsed": 120.5
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح العملية |
| `creation_id` | int\|null | معرف التوليد |
| `status` | string | processing / completed / error |
| `video_url` | string\|null | رابط تحميل الفيديو |
| `video_base64` | string\|null | الفيديو base64 (فقط إذا download=true) |
| `message` | string\|null | رسالة حالة أو خطأ |
| `elapsed` | float\|null | الوقت المستغرق بالثواني |

### أمثلة

**توليد فيديو بسيط:**
```bash
curl -X POST http://localhost:8080/api/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "eagle soaring over mountains at sunrise",
    "model": "bytedance-seedance-pro-2.0",
    "aspect_ratio": "16:9",
    "duration": 5,
    "resolution": "1080p"
  }'
```

**توليد مع صورة مرجعية (start keyframe):**
```bash
curl -X POST http://localhost:8080/api/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "camera slowly zooms out revealing a landscape",
    "model": "bytedance-seedance-fast-2.0",
    "keyframes": {
      "start": {
        "type": "image",
        "url": "https://example.com/start-frame.jpg"
      }
    }
  }'
```

**توليد مع مؤثرات صوتية:**
```bash
curl -X POST http://localhost:8080/api/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "thunderstorm over the ocean",
    "model": "bytedance-seedance-pro-2.0",
    "duration": 10,
    "with_sound": true
  }'
```

**توليد بدون انتظار:**
```bash
curl -X POST http://localhost:8080/api/video/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "rainy city street at night",
    "wait": false
  }'
# Response: {"success": true, "status": "processing", "creation_id": 12345}
# ثم: GET /api/status/12345?type=video
```

---

## GET /api/health

فحص حالة السيرفر والمصادقة.

### Response (HealthResponse)

```json
{
  "status": "ok",
  "authenticated": true,
  "version": "1.0.0"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `status` | string | "ok" أو "error" |
| `authenticated` | bool | هل تمت المصادقة بنجاح |
| `version` | string | إصدار السيرفر |

---

## GET /api/status/{creation_id}

فحص حالة توليد معين (صورة أو فيديو).

### Query Parameters

| الحقل | النوع | افتراضي | الوصف |
|-------|-------|---------|-------|
| `type` | string | `image` | نوع التوليد: image أو video |

### Response (StatusResponse)

```json
{
  "success": true,
  "creation_id": 3070624230,
  "status": "completed",
  "url": "https://pikaso.cdnpk.net/...",
  "download_url": "https://pikaso.cdnpk.net/...",
  "elapsed": 0.05
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح الاستعلام |
| `creation_id` | string\|int | معرف التوليد |
| `status` | string | queued, processing, completed, failed |
| `url` | string\|null | رابط CDN |
| `download_url` | string\|null | رابط التحميل المباشر |
| `elapsed` | float | وقت الاستعلام بالثواني |

### حالة التوليد (status)

| الحالة | الوصف |
|--------|-------|
| `queued` | في قائمة الانتظار |
| `processing` | جاري التوليد |
| `completed` | اكتمل بنجاح |
| `failed` | فشل التوليد |

---

## GET /api/models

قائمة جميع النماذج المسجلة (صور + فيديو).

### Response (ModelsResponse)

```json
{
  "success": true,
  "image": [
    {
      "slug": "imagen-nano-banana-2",
      "display_name": "Nano Banana 2",
      "credits": "75-150",
      "resolutions": ["1k", "2k", "4k"],
      "max_refs": 14
    }
  ],
  "video": [
    {
      "slug": "bytedance-seedance-pro-2.0",
      "display_name": "Seedance 2.0 Pro",
      "api": "bytedance",
      "model": "seedance",
      "mode": "pro-2.0",
      "family": "bytedance",
      "duration_range": [4, 15],
      "aspect_ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
      "resolutions": ["1080p", "720p", "480p"],
      "max_image_refs": 9,
      "max_video_refs": 2,
      "max_audio_refs": 2,
      "multishot_max": 6,
      "supports_sound": true,
      "supports_keyframes": ["start", "end"]
    }
  ]
}
```

---

## Error Response

جميع الأخطاء تُرجع نفس الشكل:

```json
{
  "success": false,
  "error": "Rate limited: You have reached the maximum number of concurrent creations.",
  "detail": { ... },
  "status_code": 429
}
```

### رموز الأخطاء

| HTTP Status | نوع الخطأ | الوصف |
|-------------|----------|-------|
| 400 | ValueError | معاملات غير صالحة |
| 401 | AuthenticationError | فشل المصادقة (GR_TOKEN منتهي) |
| 403 | DeviceLimitError | حد الأجهزة |
| 422 | ValidationError | خطأ في التحقق |
| 429 | RateLimitError | تجاوز حد الطلبات (concurrent أو rate limit) |
| 455 | ContentRestrictedError | محتوى مقيد |
| 500 | MagnificError | خطأ داخلي |
| 504 | PollingTimeoutError | انتهاء مهلة التوليد |

---

## Rate Limiting

السيرفر يُطبق rate limiting لكل IP:

| الإعداد | الافتراضي | الوصف |
|---------|----------|-------|
| `max_requests` | 20 | أقصى عدد طلبات |
| `window` | 60 ثانية | نافذة الزمن |

المسارات المستثناة: `/api/health`, `/docs`, `/openapi.json`, `/redoc`

> **ملاحظة**: هذا Rate Limit محلي (على السيرفر). يُضاف إلى Rate Limit الخاص بمنصة Magnific نفسها.
