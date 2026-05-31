# ARCHITECTURE — هيكل التصميم

> وصف تفصيلي لهندسة المشروع، طبقات التصميم (Clean Architecture)، تدفق البيانات، والعلاقات بين المكونات.

---

## فلسفة التصميم

المشروع مبني بتصميم **Clean Architecture** مع مبادئ الفصل التالي:

1. **فصل النماذج عن المنطق الأساسي** — تعريفات النماذج (models/) منفصلة تماماً عن الكود الأساسي (core/). هذا يعني إضافة نموذج جديد لا تتطلب تعديل أي كود في core/.
2. **فصل الإعدادات عن الكود** — جميع المسارات والثوابت في config/ بعيداً عن المنطق.
3. **فصل واجهة المستخدم عن المنطق** — API (api/) و CLI (main.py) هما واجهتان مختلفتان لنفس المنطق الأساسي.
4. **التسجيل التلقائي (Auto-Registry)** — النماذج تسجل نفسها تلقائياً عند استيرادها، بدون أي كود تسجيل يدوي.

---

## الطبقات الأربع (Four Layers)

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation Layer  —  main.py (CLI)  +  api/ (FastAPI)   │
│  ├── main.py: cmd_serve, cmd_image, cmd_video, cmd_models │
│  ├── api/routes/: image.py, video.py, status.py, queue.py │
│  └── api/schemas/: image, video, common, queue_schemas     │
├─────────────────────────────────────────────────────────────┤
│  Model Layer  —  models/                                    │
│  ├── base.py: BaseImageModel, BaseVideoModel, ModelRegistry │
│  ├── image/: 6 ملفات نماذج صور (auto-registered)           │
│  └── video/: 9 ملفات نماذج فيديو (auto-registered)         │
├─────────────────────────────────────────────────────────────┤
│  Core Layer  —  core/                                       │
│  ├── client.py: MagnificClient (HTTP + TLS impersonation)   │
│  ├── auth.py: Authenticator (XSRF + Device)                │
│  ├── uploader.py: Uploader (3 upload strategies)            │
│  ├── poller.py: Poller (status polling + download)          │
│  ├── queue_manager.py: QueueManager (smart queue clearing)  │
│  ├── creation_registry.py: CreationRegistry (track owns)    │
│  └── exceptions.py: Exception hierarchy                     │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure Layer  —  config/ + utils/                   │
│  ├── config/: endpoints, constants, user_agent              │
│  └── utils/: cookie_parser, file_helpers, logger           │
└─────────────────────────────────────────────────────────────┘
```

### 1. Presentation Layer — طبقة العرض

المسؤولة عن التفاعل مع المستخدم (CLI أو HTTP API).

**`main.py`** — نقطة الدخول:
- `cmd_serve()` — تشغيل سيرفر FastAPI عبر Uvicorn
- `cmd_image()` — تدفق توليد صورة كامل من الألف إلى الياء
- `cmd_video()` — تدفق توليد فيديو كامل مع auto-retry
- `cmd_models()` — عرض قائمة النماذج المسجلة

**`api/`** — سيرفر FastAPI:
- `server.py` — App factory مع Lifespan (إنشاء/إغلاق الـ client + إنشاء CreationRegistry و QueueManager)
- `routes/` — 4 routers:
  - `image.py` → POST `/api/image/generate`
  - `video.py` → POST `/api/video/generate`
  - `status.py` → GET `/api/health`, GET `/api/status/{id}`, GET `/api/models`
  - `queue.py` → 5 نقاط نهاية للتحكم الذكي بالطابور (Smart Queue Control)
- `schemas/` — نماذج Pydantic:
  - `image_schemas.py` → ImageRequest, ImageResponse, ImageReferenceInput
  - `video_schemas.py` → VideoRequest, VideoResponse, VideoReferenceInput, KeyframeInput
  - `common_schemas.py` → HealthResponse, StatusResponse, ModelsResponse, ErrorResponse
  - `queue_schemas.py` → QueueClearResponse, QueueStatusResponse, QueueCancelResponse, QueueConfigureRequest, QueueConfigureResponse, RegistryItem, RegistryResponse, QueueItemWithOwnership
- `middleware/`:
  - `rate_limiter.py` — Rate limiting لكل IP (in-memory)
  - `error_handler.py` — تحويل الاستثناءات إلى JSON responses

### 2. Model Layer — طبقة النماذج

المسؤولة عن تعريف نماذج الذكاء الاصطناعي وبناء أجسام الطلبات (Request Bodies).

**`models/base.py`** — الأساس:

| الفئة | الوصف |
|-------|-------|
| `ModelRegistry` | سجل تلقائي (auto-discover) — يستورد جميع الملفات في models/image/ و models/video/ ويُسجل النماذج |
| `BaseImageModel` | dataclass يحتوي على: slug, display_name, credits, resolutions, max_refs + methods: build_start_tti_body(), build_render_body() |
| `BaseVideoModel` | dataclass يحتوي على: slug, display_name, api, model, mode, family, duration_range, aspect_ratios, resolutions, etc. + method: build_video_body() |

**آلية التسجيل التلقائي (Auto-Registration):**

```
1. استدعاء ModelRegistry.discover()
2. → _discover_image_models(): يمر على كل ملف *.py في models/image/
3. → importlib.import_module("models.image.filename")
4. → الملف يُنفذ كود المستوى الأعلى: model = BaseImageModel(...)
5. → __post_init__() يستدعي ModelRegistry.register_image(self)
6. → النموذج يُسجل في _image_models dict
7. نفس الشيء لـ _discover_video_models()
```

**فائدة التصميم**: لإضافة نموذج جديد، أنشئ ملف `.py` واحد فقط. لا تحتاج لتعديل أي ملف آخر.

### 3. Core Layer — الطبقة الأساسية

المسؤولة عن المنطق الداخلي: HTTP، مصادقة، رفع ملفات، polling.

**`core/client.py` — MagnificClient:**
- يستخدم `curl_cffi.requests.Session` مع `impersonate="chrome136"`
- يُعيد محاكاة بصمة TLS (JA3/JA4) الخاصة بـ Chrome 136
- يُرسل Headers كاملة تشمل: User-Agent, Sec-Ch-Ua, Sec-Fetch-*, Origin, Referer
- يدعم: GET, POST (JSON), POST (form-data), POST (raw), Download
- `_handle_response()` يحول HTTP status codes إلى استثناءات محددة
- يدعم Context Manager (`with client:`)

**`core/auth.py` — Authenticator:**
- `refresh_xsrf()` — يحذف XSRF-TOKEN القديم، يطلب GET csrf-cookie، يقرأ الجديد من session cookies، يُفك ترميز URI encoding
- `identify_device()` — يُرسل POST إلى /user/api/devices/identify
- `authenticate()` — يُنفذ refresh_xsrf() ثم identify_device()

**`core/uploader.py` — Uploader:**

| الطريقة | Endpoint | الاستخدام |
|---------|----------|----------|
| `upload_temporal()` | POST /api/temporal-storage | رفع FormData — لـ start-tti-v2 references |
| `upload_frame()` | POST /api/video/generate/upload-frame | رفع Base64 JSON — لـ video keyframes (start, end, frame, sketch) |
| `upload_video_audio()` | POST /api/temporal-storage | رفع فيديو/صوت — يُرجع temporal: path |

**`core/poller.py` — Poller:**
- `poll_creation()` — polling مستمر حتى completed أو failed
- `poll_creation_stream()` — generator يُرسل تحديثات status تدريجياً (لـ SSE/WebSocket مستقبلاً)
- `poll_image_by_family()` — polling بديل عبر /api/creations?family=...
- يُميز بين type="image" (URL في result.url) و type="video" (URL في result.metadata.url)

**`core/creation_registry.py` — CreationRegistry:**
- سجلّ في الذاكرة (in-memory) يتتبع جميع عمليات التوليد التي بدأها المشروع
- يُسجّل `identifier` مع `metadata` (creation_id, tool, model) و `timestamp`
- يُستخدم من قِبل QueueManager لتحديد الملكية عند مسح الطابور
- يوفر طرق: `register()`, `unregister()`, `is_ours()`, `list_all()`, `clear()`, `count()`
- Thread-safe عبر `threading.Lock` للوصول المتزامن
- **فائدة التصميم**: يمنع مسح عمليات توليد بدأت من مصادر خارجية (مثل واجهة الويب)
- **Safe default**: عند إعادة التشغيل، يُفرّغ تلقائياً — تُعامَل جميع العمليات كـ خارجية

**`core/queue_manager.py` — QueueManager:**
- إدارة ذكية لمسح طابور التوليد (queue clearing) مع وعي بالملكية
- يستعلم عن جميع العناصر في الطابور عبر `GET /api/creations?status=queued&per_page=100`
- يُميّز بين عناصر يملكها المشروع (`registry.is_ours()`) وعناصر خارجية
- يوفر الطرق:
  - `clear_external_queue()` — يُلغي العمليات الخارجية فقط، يتخطى عمليات المشروع
  - `cancel_creation(identifier)` — يُلغي عملية واحدة بالمعرّف
  - `get_queue_snapshot()` — لقطة الطابور مع تصنيف الملكية لكل عنصر
  - `configure(enabled)` — تفعيل/تعطيل المسح التلقائي
- يتكامل مع `CreationRegistry` للتحقق من الملكية
- **قاعدة مهمة**: إذا كانت جميع العمليات من المشروع، لا يُلغى شيء (يُحافظ على الترتيب الطبيعي)

**`core/exceptions.py` — التسلسل الهرمي للاستثناءات:**

```
MagnificError (base)
├── AuthenticationError  ← HTTP 401, 419
├── DeviceLimitError    ← HTTP 403 (device)
├── RateLimitError      ← HTTP 429
├── ContentRestrictedError ← HTTP 455, 456
├── ValidationError     ← HTTP 422
├── PollingTimeoutError ← timeout
└── GenerationError     ← failed during processing
```

### 4. Infrastructure Layer — طبقة البنية التحتية

المسؤولة عن الإعدادات والثوابت والأدوات المساعدة.

**`config/endpoints.py` — Endpoints:**
- `BASE_URL` — قابل للتغيير (افتراضي: https://www.magnific.com)
- `API_PREFIX` — يتغير تلقائياً: /app لمagnific.com، /pikaso لfreepik.com
- `_p(path)` — يُضيف البادئة للمسار
- `url(path)` — يبني URL كامل
- يحتوي على جميع المسارات كـ class attributes + class methods

**`config/constants.py` — الثوابت:**
- `AspectRatios.DATA` — خريطة نسب العرض/الارتفاع → أبعاد بكسل (عند 1k)
- `AspectRatios.dimensions(ratio, res)` — يحسب الأبعاد النهائية بالضرب (1k=×1, 2k=×2, 4k=×4)
- `Resolutions.IMAGE` — ["1k", "2k", "4k"]
- `Resolutions.VIDEO` — ["1080p", "720p", "480p"]

**`config/user_agent.py` — UserAgents:**
- `IMPERSONATE = "chrome136"` — يستخدم مع curl_cffi
- `DEFAULT` — User-Agent string كاملة لـ Chrome 136 على Windows

**`utils/cookie_parser.py` — CookieParser:**
- يدعم صيغتين:
  1. **Netscape** — ملف txt مثل Cookie-Editor export (tab-separated)
  2. **JSON** — مصفوفة أو كائن JSON
- يتعامل مع أسطر `#HttpOnly_` — يُزيل البادئة ويقرأ الكوكي كعادي
- يُخطي كوكيز معينة (SKIP_COOKIES): ak_bmsc, _ga, _gid, posthog
- `to_curl_cffi_dict()` — يُرجع dict {name: value} جاهز لـ curl_cffi

**`utils/file_helpers.py` — FileHelpers:**
- `file_to_base64(path)` — يقرأ ملف ويرجع data URI (data:image/jpeg;base64,...)
- `base64_to_bytes(uri)` — يحول data URI إلى bytes
- `save_bytes(data, path)` — يحفظ bytes مع إنشاء المجلدات تلقائياً
- `parse_reference_input("file.jpg|label")` — يُحلل مُدخل مرجع
- `is_url(s)` / `is_base64_data_uri(s)` — فحص نوع المُدخل

---

## تدفق البيانات — توليد صورة

```
┌──────────┐     ┌──────────────┐     ┌───────────────┐
│ CLI/API  │────▶│  MagnificClient │────▶│ Magnific API  │
│ Request  │     │  (curl_cffi)    │     │  (Cloudflare) │
└──────────┘     └──────────────┘     └───────────────┘
      │                  │                     │
      │ 1. CookieParser │                     │
      │    to_curl_cffi │                     │
      │──────────────────▶│                    │
      │                  │ GET csrf-cookie    │
      │                  │────────────────────▶│
      │                  │◀────────────────────│
      │                  │ XSRF-TOKEN cookie   │
      │                  │                    │
      │                  │ POST devices/id    │
      │                  │────────────────────▶│
      │                  │◀────────────────────│
      │                  │ {success: true}     │
      │                  │                    │
      │ 2. Model        │                    │
      │    build_start  │ POST start-tti-v2   │
      │    _tti_body()  │────────────────────▶│
      │                  │◀────────────────────│
      │                  │ family, request_tok │
      │                  │                    │
      │ 3. Model        │ POST render/v4      │
      │    build_render │────────────────────▶│
      │    _body()      │◀────────────────────│
      │                  │ creation_id         │
      │                  │                    │
      │ 4. Poller       │ GET creation/{id}   │
      │    poll(loop)   │────────────────────▶│
      │                  │◀────────────────────│
      │                  │ status: processing  │
      │                  │        ...          │
      │                  │◀────────────────────│
      │                  │ status: completed   │
      │                  │ url: cdn://...     │
      │                  │                    │
      │ 5. Download     │ GET cdn://...       │
      │                  │────────────────────▶│
      │                  │◀────────────────────│
      │◀─────────────────│ image bytes         │
      │ save to disk    │                    │
```

---

## تدفق البيانات — توليد فيديو

```
┌──────────┐     ┌──────────────┐     ┌───────────────┐
│ CLI/API  │────▶│  MagnificClient │────▶│ Magnific API  │
│ Request  │     │  (curl_cffi)    │     │  (Cloudflare) │
└──────────┘     └──────────────┘     └───────────────┘
      │                  │                     │
      │ 1. Auth          │ (same as image)     │
      │                  │                     │
      │ 2. (Optional)    │                     │
      │    Upload refs   │ POST upload-frame   │
      │    or temporal   │────────────────────▶│
      │                  │◀────────────────────│
      │                  │ frameUrl            │
      │                  │                     │
      │ 3. Model         │ POST video/generate │
      │    build_video   │────────────────────▶│
      │    _body()       │◀────────────────────│
      │                  │ creation_id         │
      │                  │                     │
      │ 4. Auto-retry    │ (on 429: wait      │
      │    loop          │  and retry)         │
      │                  │                     │
      │ 5. Poller        │ GET creation/{id}   │
      │    poll(loop)    │────────────────────▶│
      │                  │ queued→processing→  │
      │                  │ completed            │
      │                  │◀────────────────────│
      │                  │ metadata.url        │
      │                  │                     │
      │ 6. Download     │ GET cdn://...       │
      │                  │────────────────────▶│
      │◀─────────────────│ video bytes         │
      │ save to disk    │                     │
```

---

## تصميم سيرفر API

### Lifespan (دورة حياة التطبيق)

```
Startup:
  1. ModelRegistry.discover() → تسجيل جميع النماذج
  2. CookieParser → تحميل الكوكيز
  3. MagnificClient → إنشاء العميل
  4. Authenticator.authenticate() → XSRF + Device
  5. CreationRegistry() → إنشاء سجلّ تتبع التوليدات
  6. QueueManager(client, creation_registry) → إنشاء مدير الطابور الذكي
  7. Inject deps → تمرير client/poller/uploader/creation_registry/queue_manager للـ routes

Shutdown:
  1. client.close() → إغلاق جلسة curl_cffi
```

### Middleware Pipeline

```
Request → CORS Middleware → Rate Limit Middleware → Route Handler → Response
                                                              ↓ (error)
                                                     Error Handler → JSON Error
```

### Dependency Injection

الـ routes لا تُنشئ العميل مباشرة. بدلاً من ذلك، تُمرر الـ dependencies عبر `set_deps()`:

```python
# في server.py (lifespan):
image_set_deps(_client, _poller, _uploader, _creation_registry)
video_set_deps(_client, _poller, _uploader, _creation_registry)
status_set_deps(_client, _poller)
queue_set_deps(_queue_manager, _creation_registry)

# في route (module-level):
_client: MagnificClient | None = None
def set_deps(client, poller, uploader, creation_registry):
    global _client, _poller, _uploader, _creation_registry
    _client = client
    ...
```

> هذا التصميم يسمح بتغيير الـ client أو إضافة عملاء متعددين مستقبلاً بدون تعديل الـ routes.
> كذلك يسمح بتمرير `CreationRegistry` لعمليات التوليد لتسجيل الملكية تلقائياً.

---

## نظام التحكم الذكي بالطابور (Smart Queue Control)

أُضيف في **Cycle 6** — نظام متكامل لإدارة طابور التوليد (queue) مع وعي بالملكية.

### المكونات الأساسية

| المكون | الملف | الوصف |
|--------|-------|-------|
| **CreationRegistry** | `core/creation_registry.py` | سجلّ في الذاكرة يتتبع عمليات التوليد التي بدأها المشروع. يُخزّن `creation_id` مع نوع المالك (image/video) والوقت. |
| **QueueManager** | `core/queue_manager.py` | مدير الطابور الذكي — يستعلم عن عناصر الطابور ويميّز بين ما يملكه المشروع وما هو خارجي، ثم يُنفّذ عمليات المسح المناسبة. |

### نقاط النهاية (5 Endpoints)

| الطريقة | المسار | الوصف |
|---------|--------|-------|
| `POST` | `/api/queue/clear` | مسح العمليات الخارجية فقط ( queued ) — عمليات المشروع تُتخطى |
| `GET` | `/api/queue/status` | لقطة الطابور مع تصنيف الملكية لكل عنصر (`is_ours`) |
| `POST` | `/api/queue/cancel/{identifier}` | إلغاء عملية محددة بالمعرّف |
| `POST` | `/api/queue/configure` | تفعيل/تعطيل المسح التلقائي (`{"auto_clear": true/false}`) |
| `GET` | `/api/queue/registry` | عرض العمليات المسجلة في سجلّ المشروع |

### خطافات التكامل (Integration Hooks)

يتم تسجيل الملكية تلقائياً عند بدء أي عملية توليد:

```
عملية توليد صورة:
  POST /api/image/generate
    → QueueManager.clear_external_queue() (إذا مفعّل)
    → start-tti-v2 → family, request_token
    → render/v4 → creation_id + identifier
    → CreationRegistry.register(identifier, metadata={creation_id, tool, model})
    → Poller.poll_creation()
    → upon completion/failure → CreationRegistry.unregister(identifier)

عملية توليد فيديو:
  POST /api/video/generate
    → QueueManager.clear_external_queue() (إذا مفعّل)
    → video/generate → creations[] → creation_id + identifier
    → CreationRegistry.register(identifier, metadata={creation_id, tool, model})
    → Poller.poll_creation()
    → upon completion/failure → CreationRegistry.unregister(identifier)
```

> جميع الخطافات ملفوفة في `try/except` مع `logger.warning` — فشل المسح أو التسجيل لا يُعطّل عملية التوليد.

### فائدة التصميم

- **الوعي بالملكية**: يمنع حذف عمليات توليد بدأت من واجهة الويب أو مصادر أخرى عن طريق الخطأ
- **الحفاظ على ترتيب المشروع**: إذا كانت جميع العمليات من المشروع، لا يُلغى شيء
- **opt-in**: المسح التلقائي مُعطّل افتراضياً، يجب تفعيله صراحة
- **عدم التأثير على core/ موجود**: النظام مُضاف كطبقة فوقية لا تُعدّل أي كود أساسي

---

## قرارات التصميم الرئيسية

| القرار | السبب |
|--------|-------|
| `curl_cffi` بدلاً من `requests` | requests لا يدعم TLS fingerprint impersonation، Cloudflare يحظره |
| `chrome136` impersonation | أحدث إصدار مدعوم، يوفر 15 فتحة جهاز |
| Dataclasses بدلاً من Pydantic للنماذج | النماذج الداخلية لا تحتاج validation، dataclasses أخف |
| Pydantic فقط في api/schemas/ | التحقق مطلوب فقط عند حدود API، ليس في المنطق الداخلي |
| Auto-Registry بدلاً من explicit registration | يُقلل الكود Boilerplate، إضافة نموذج = ملف واحد |
| In-memory rate limiter | يكفي للاستخدام المحلي، يمكن استبداله بـ Redis مستقبلاً |
| Cookie file بدلاً من env variables | الكوكيز كثيرة ومعقدة، ملف أنظف وأسهل للتصدير من المتصفح |
