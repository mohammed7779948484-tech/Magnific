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

نقاط نهاية مخصصة لإدارة الطابور الخارجي (outbound queue) والتحكم في العمليات المسجلة. تتيح لك مراقبة حالة الطابور، إلغاء عمليات محددة، تهيئة السلوك التلقائي، وعرض سجل العمليات.

---

### POST /api/queue/clear

مسح جميع العناصر المعلقة في الطابور الخارجي. يُزيل فقط العمليات التي لم تبدأ المعالجة بعد.

#### Request Body

```json
{
  "scope": "all"
}
```

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `scope` | string | `"all"` | لا | نطاق المسح: `all` (الكل) أو `pending` (المعلقة فقط) |

#### Response (QueueClearResponse)

```json
{
  "success": true,
  "cleared_count": 7,
  "scope": "all",
  "message": "تم مسح 7 عمليات من الطابور الخارجي"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح العملية |
| `cleared_count` | int | عدد العمليات التي تم مسحها |
| `scope` | string | النطاق المُستخدم في المسح |
| `message` | string | رسالة تأكيد |

#### مثال curl

```bash
curl -X POST http://localhost:8080/api/queue/clear \
  -H "Content-Type: application/json" \
  -d '{"scope": "all"}'
```

```bash
# مسح المعلقة فقط
curl -X POST http://localhost:8080/api/queue/clear \
  -H "Content-Type: application/json" \
  -d '{"scope": "pending"}'
```

---

### GET /api/queue/status

حالة الطابور الحالية مع تصنيف الملكية. يعرض عدد العمليات حسب نوعها وحالتها ومالكها.

#### Response (QueueStatusResponse)

```json
{
  "success": true,
  "total": 12,
  "by_status": {
    "queued": 8,
    "processing": 3,
    "completed": 1
  },
  "by_type": {
    "image": 7,
    "video": 5
  },
  "by_owner": {
    "system": 5,
    "user:alice": 4,
    "user:bob": 3
  },
  "oldest_queued": "2025-01-15T10:30:00Z",
  "newest_queued": "2025-01-15T10:35:22Z"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح الاستعلام |
| `total` | int | إجمالي العمليات في الطابور |
| `by_status` | object | تصنيف حسب الحالة (queued/processing/completed) |
| `by_type` | object | تصنيف حسب النوع (image/video) |
| `by_owner` | object | تصنيف حسب المالك |
| `oldest_queued` | string/null | تاريخ أقدم عملية في الانتظار |
| `newest_queued` | string/null | تاريخ أحدث عملية في الانتظار |

#### مثال curl

```bash
curl http://localhost:8080/api/queue/status
```

---

### POST /api/queue/cancel/{identifier}

إلغاء عملية محددة من الطابور باستخدام معرفها. يدعم المعرف الرقمي (`creation_id`) أو معرف العملية (`creation_id`). يمكن إلغاء العمليات المعلقة أو قيد المعالجة.

#### Path Parameters

| الحقل | النوع | مطلوب؟ | الوصف |
|-------|-------|--------|-------|
| `identifier` | string/int | نعم | معرف العملية المراد إلغاؤها |

#### Request Body (اختياري)

```json
{
  "reason": "لم تعد مطلوبة"
}
```

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `reason` | string | null | لا | سبب الإلغاء (يُسجّل في السجل) |

#### Response (QueueCancelResponse)

```json
{
  "success": true,
  "identifier": 3070624230,
  "cancelled": true,
  "status_before": "queued",
  "message": "تم إلغاء العملية 3070624230 بنجاح"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح الإلغاء |
| `identifier` | string/int | معرف العملية |
| `cancelled` | bool | هل تم الإلغاء فعلاً |
| `status_before` | string | حالة العملية قبل الإلغاء |
| `message` | string | رسالة تأكيد |

#### الاستجابة عند الفشل

```json
{
  "success": false,
  "identifier": 3070624230,
  "cancelled": false,
  "error": "العملية غير موجودة في الطابور"
}
```

#### أمثلة curl

```bash
# إلغاء عملية برقمها
curl -X POST http://localhost:8080/api/queue/cancel/3070624230 \
  -H "Content-Type: application/json" \
  -d '{"reason": "لم تعد مطلوبة"}'
```

```bash
# إلغاء بدون سبب
curl -X POST http://localhost:8080/api/queue/cancel/3070624230
```

---

### POST /api/queue/configure

تهيئة سلوك الطابور، بما في ذلك تفعيل أو تعطيل المسح التلقائي للعمليات المكتملة. يُستخدم للتحكم في دورة حياة الطابور تلقائيًا.

#### Request Body (QueueConfigureRequest)

```json
{
  "auto_clear": true,
  "auto_clear_delay": 300,
  "max_queue_size": 50
}
```

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `auto_clear` | bool | `true` | لا | تفعيل المسح التلقائي للعمليات المكتملة |
| `auto_clear_delay` | int | `300` | لا | مدة الانتظار قبل المسح التلقائي (بالثواني) |
| `max_queue_size` | int | `50` | لا | الحد الأقصى لحجم الطابور |

#### Response (QueueConfigureResponse)

```json
{
  "success": true,
  "configuration": {
    "auto_clear": true,
    "auto_clear_delay": 300,
    "max_queue_size": 50
  },
  "message": "تم تحديث تهيئة الطابور بنجاح"
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح التحديث |
| `configuration` | object | التهيئة المُطبّقة فعلاً |
| `message` | string | رسالة تأكيد |

#### أمثلة curl

```bash
# تفعيل المسح التلقائي مع تأخير 5 دقائق
curl -X POST http://localhost:8080/api/queue/configure \
  -H "Content-Type: application/json" \
  -d '{"auto_clear": true, "auto_clear_delay": 300}'
```

```bash
# تعطيل المسح التلقائي
curl -X POST http://localhost:8080/api/queue/configure \
  -H "Content-Type: application/json" \
  -d '{"auto_clear": false}'
```

---

### GET /api/queue/registry

عرض جميع العمليات المسجلة في الطابور مع تفاصيلها الكاملة. يُستخدم لتفتيش حالة كل عملية ومراقبتها.

#### Query Parameters

| الحقل | النوع | افتراضي | مطلوب؟ | الوصف |
|-------|-------|---------|--------|-------|
| `status` | string | null | لا | تصفية حسب الحالة: queued, processing, completed, failed |
| `type` | string | null | لا | تصفية حسب النوع: image, video |
| `limit` | int | `50` | لا | الحد الأقصى للنتائج |
| `offset` | int | `0` | لا | بداية الصفحة (Pagination) |

#### Response (QueueRegistryResponse)

```json
{
  "success": true,
  "total": 12,
  "limit": 50,
  "offset": 0,
  "operations": [
    {
      "creation_id": 3070624230,
      "type": "image",
      "status": "completed",
      "owner": "system",
      "prompt": "a golden dragon flying over mountains",
      "model": "imagen-nano-banana-2",
      "queued_at": "2025-01-15T10:30:00Z",
      "started_at": "2025-01-15T10:30:05Z",
      "completed_at": "2025-01-15T10:31:02Z",
      "elapsed": 57.2
    },
    {
      "creation_id": 3070643635,
      "type": "video",
      "status": "processing",
      "owner": "user:alice",
      "prompt": "eagle soaring over mountains at sunrise",
      "model": "bytedance-seedance-pro-2.0",
      "queued_at": "2025-01-15T10:32:00Z",
      "started_at": "2025-01-15T10:32:03Z",
      "completed_at": null,
      "elapsed": 120.5
    }
  ]
}
```

| الحقل | النوع | الوصف |
|-------|-------|-------|
| `success` | bool | نجاح الاستعلام |
| `total` | int | إجمالي العمليات المطابقة |
| `limit` | int | حد النتائج المُطبّق |
| `offset` | int | إزاحة الصفحة |
| `operations` | array | قائمة العمليات |
| `operations[].creation_id` | int | معرف العملية |
| `operations[].type` | string | نوع العملية (image/video) |
| `operations[].status` | string | الحالة الحالية |
| `operations[].owner` | string | مالك العملية |
| `operations[].prompt` | string | النص المُستخدم |
| `operations[].model` | string | النموذج المُستخدم |
| `operations[].queued_at` | string | تاريخ الإضافة للطابور |
| `operations[].started_at` | string\|null | تاريخ بدء المعالجة |
| `operations[].completed_at` | string\|null | تاريخ الاكتمال |
| `operations[].elapsed` | float\|null | الوقت المستغرق بالثواني |

#### أمثلة curl

```bash
# عرض جميع العمليات
curl http://localhost:8080/api/queue/registry
```

```bash
# تصفية العمليات المعلقة فقط
curl "http://localhost:8080/api/queue/registry?status=queued"
```

```bash
# عرض فيديوهات قيد المعالجة مع pagination
curl "http://localhost:8080/api/queue/registry?type=video&status=processing&limit=10&offset=0"
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
