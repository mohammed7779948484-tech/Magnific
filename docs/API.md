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
| `POST` | `/api/queue/clear` | مسح الطابور الخارجي |
| `GET` | `/api/queue/status` | حالة الطابور مع تصنيف الملكية |
| `POST` | `/api/queue/cancel/{identifier}` | إلغاء عملية محددة |
| `POST` | `/api/queue/configure` | تفعيل/تعطيل المسح التلقائي |
| `GET` | `/api/queue/registry` | عرض العمليات المسجلة |

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

## نقاط التحكم بالطابور (Queue Control)

نظام ذكي يميّز بين العمليات التي أنشأها المشروع والعمليات الخارجية (مستخدمون آخرون على نفس الحساب المشترك). يُلغي فقط العمليات الخارجية ويحافظ على ترتيب عمليات المشروع. المسح التلقائي **مُعطّل افتراضياً** (opt-in).

> **ملاحظة**: إذا كانت جميع العمليات في الطابور من المشروع، لن يُلغى أي شيء — يُحافظ على الترتيب الطبيعي.

---

### POST /api/queue/clear

مسح العمليات الخارجية المعلقة في الطابور ( queued فقط ). العمليات المسجلة كملكية المشروع تُتخطى ولا تُلغى.

#### Request

لا يوجد request body مطلوب.

#### Response

```json
{
  "success": true,
  "enabled": true,
  "cleared": 3,
  "errors": 0,
  "skipped_ours": 2,
  "total_queued": 5,
  "reason": "cleared",
  "details": {
    "cancelled_identifiers": ["abc123", "def456", "ghi789"],
    "skipped_identifiers": ["ours_001", "ours_002"]
  },
  "timestamp": "2026-05-31T03:30:00Z"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح العملية |
| `enabled` | bool | هل المسح التلقائي مفعّل |
| `cleared` | int | عدد العمليات التي تم إلغاؤها |
| `errors` | int | عدد الأخطاء أثناء الإلغاء |
| `skipped_ours` | int | عدد عمليات المشروع التي تم تخطيها |
| `total_queued` | int | إجمالي العمليات في الطابور |
| `reason` | string\|null | سبب النتيجة: `cleared`، `all_ours`، `disabled`، `no_external` |
| `details.cancelled_identifiers` | array | قائمة معرّفات العمليات المُلغاة |
| `details.skipped_identifiers` | array | قائمة معرّفات العمليات المُتخطاة |
| `timestamp` | string | وقت تنفيذ العملية (ISO 8601) |

#### قيم `reason`

| القيمة | الوصف |
|--------|-------|
| `"disabled"` | المسح التلقائي مُعطّل |
| `"all_ours"` | جميع العمليات في الطابور تخص المشروع — لم يُلغى شيء |
| `"cleared"` | تم إلغاء عمليات خارجية |
| `"no_external"` | لا توجد عمليات خارجية للإلغاء |

#### مثال curl

```bash
curl -X POST http://localhost:8080/api/queue/clear
```

---

### GET /api/queue/status

حالة الطابور الحالية مع تصنيف الملكية لكل عنصر (هل هو من المشروع أم خارجي).

#### Response

```json
{
  "total_queued": 5,
  "ours": 2,
  "external": 3,
  "items": [
    {
      "id": 123,
      "identifier": "ours_001",
      "tool": "text-to-image",
      "model": "imagen-nano-banana-2",
      "is_ours": true,
      "created_at": "2026-05-31T03:25:00Z"
    },
    {
      "id": 456,
      "identifier": "ext_abc",
      "tool": "video-generator",
      "model": "bytedance-seedance-pro-2.0",
      "is_ours": false,
      "created_at": "2026-05-31T03:26:00Z"
    }
  ],
  "processing_count": 0,
  "auto_clear_enabled": false,
  "checked_at": "2026-05-31T03:30:00Z"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `total_queued` | int | إجمالي العمليات في الطابور |
| `ours` | int | عدد عمليات المشروع |
| `external` | int | عدد العمليات الخارجية |
| `items` | array | قائمة التفاصيل مع `is_ours` لكل عنصر |
| `items[].id` | int\|null | رقم العملية |
| `items[].identifier` | string\|null | معرّف العملية (يُستخدم للإلغاء) |
| `items[].tool` | string\|null | نوع الأداة (text-to-image، video-generator) |
| `items[].model` | string\|null | النموذج المُستخدم |
| `items[].is_ours` | bool | هل العملية من المشروع |
| `items[].created_at` | string\|null | تاريخ الإنشاء |
| `processing_count` | int | عدد العمليات قيد المعالجة حالياً |
| `auto_clear_enabled` | bool | هل المسح التلقائي مفعّل |
| `checked_at` | string\|null | وقت الفحص (ISO 8601) |

#### مثال curl

```bash
curl http://localhost:8080/api/queue/status
```

---

### POST /api/queue/cancel/{identifier}

إلغاء عملية محددة من الطابور باستخدام معرّفها. يُلغي فقط العمليات ذات الحالة `queued` أو `delayed_processing`. العمليات `processing` لا يمكن إلغاؤها.

#### Path Parameters

| الحقل | النوع | مطلوب؟ | الوصف |
|-------|-------|--------|-------|
| `identifier` | string | نعم | معرّف العملية المراد إلغاؤها |

#### Request

لا يوجد request body مطلوب.

#### Response

```json
{
  "success": true,
  "identifier": "l7mHl6sgv9",
  "message": "Cancel request sent"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح العملية |
| `identifier` | string | معرّف العملية |
| `message` | string\|null | رسالة تأكيد أو خطأ |

#### مثال curl

```bash
curl -X POST http://localhost:8080/api/queue/cancel/l7mHl6sgv9
```

---

### POST /api/queue/configure

تفعيل أو تعطيل المسح التلقائي للعمليات الخارجية قبل كل عملية توليد جديدة. مُعطّل افتراضياً (off).

#### Request Body (QueueConfigureRequest)

```json
{
  "auto_clear": true
}
```

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `auto_clear` | bool | `false` | لا | تفعيل المسح التلقائي للعمليات الخارجية قبل التوليد |

#### Response

```json
{
  "auto_clear": true,
  "message": "Automatic queue clearing enabled. Non-project queued creations will be cancelled before each generation."
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `auto_clear` | bool | الحالة الجديدة |
| `message` | string | رسالة تأكيد |

#### مثال curl

```bash
# تفعيل المسح التلقائي
curl -X POST http://localhost:8080/api/queue/configure \
  -H "Content-Type: application/json" \
  -d '{"auto_clear": true}'
```

```bash
# تعطيل المسح التلقائي
curl -X POST http://localhost:8080/api/queue/configure \
  -H "Content-Type: application/json" \
  -d '{"auto_clear": false}'
```

---

### GET /api/queue/registry

عرض جميع العمليات المسجلة في سجلّ المشروع (التي بدأها المشروع عبر API). يُعرض فقط العمليات النشطة حالياً في الذاكرة.

#### Response

```json
{
  "count": 3,
  "creations": [
    {
      "identifier": "l7mHl6sgv9",
      "metadata": {
        "creation_id": 3071049939,
        "tool": "text-to-image",
        "model": "imagen-nano-banana-2"
      },
      "registered_at": "2026-05-31T03:25:00Z"
    },
    {
      "identifier": "kP9xQm2nR4",
      "metadata": {
        "creation_id": 3071049940,
        "tool": "video-generator",
        "model": "bytedance-seedance-pro-2.0"
      },
      "registered_at": "2026-05-31T03:26:00Z"
    }
  ]
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `count` | int | عدد العمليات المسجلة حالياً |
| `creations` | array | قائمة العمليات المسجلة |
| `creations[].identifier` | string | معرّف العملية |
| `creations[].metadata` | object | بيانات إضافية (creation_id، tool، model) |
| `creations[].registered_at` | string | وقت التسجيل (ISO 8601) |

> **ملاحظة**: السجلّ في الذاكرة فقط (in-memory). عند إعادة تشغيل السيرفر، يُفرّغ تلقائياً وتُعامَل جميع العمليات كـ خارجية (safe default).

#### مثال curl

```bash
curl http://localhost:8080/api/queue/registry
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
