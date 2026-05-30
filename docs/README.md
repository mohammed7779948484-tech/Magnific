# Magnific API Client

> عميل برمجي احترافي لتوليد الصور والفيديوهات عبر API الداخلي الخاص بمنصة Magnific/Pikaso (Freepik) — بدون الحاجة لفتح أي متصفح.

---

## نظرة عامة

هذا المشروع يتيح لك التفاعل مع API الداخلي الخاص بمنصة Magnific بشكل برمجي مباشر (programmatic) لتوليد الصور والفيديوهات باستخدام أحدث نماذج الذكاء الاصطناعي. المشروع مبني بتصميم **Clean Architecture** مع فصل كامل بين الطبقات (Layers)، ويوفر واجهتين للاستخدام:

1. **CLI** — أوامر سطر الأوامر لتوليد الصور والفيديو مباشرة
2. **Local API Server** — سيرفر FastAPI محلي يمكن ربط أي واجهة frontend به

### المميزات الرئيسية

- **تخطي Cloudflare و Akamai** — باستخدام `curl_cffi` مع تقليد بصمة TLS الخاصة بـ Chrome 136
- **6 نماذج صور + 9 نماذج فيديو** — مع نظام تسجيل تلقائي (Auto-Registry) لإضافة نماذج جديدة
- **3 طرق رفع ملفات** — FormData (temporal-storage)، Base64 JSON (upload-frame)، CDN URLs
- **تخطي كامل لطبقات الحماية** — XSRF CSRF، Device Fingerprint، GR_TOKEN JWT
- **سيرفر API محلي** — FastAPI مع Swagger UI، Rate Limiting، CORS، Error Handling
- **Polling تلقائي** — مع إعادة المحاولة عند Rate Limit (Auto-retry with backoff)

---

## هيكل المشروع

```
magnific/
├── main.py                    # نقطة الدخول الرئيسية (CLI)
├── requirements.txt           # الحزم المطلوبة
├── .env.example               # ملف متغيرات البيئة (نموذج)
├── docs/                      # مجلد التوثيق
│
├── core/                      # الطبقة الأساسية — المنطق الداخلي
│   ├── client.py              # عميل HTTP مع TLS impersonation
│   ├── auth.py                # المصادقة (XSRF + Device)
│   ├── uploader.py            # رفع الملفات (3 طرق)
│   ├── poller.py              # فحص حالة التوليد
│   └── exceptions.py          # التسلسل الهرمي للاستثناءات
│
├── models/                    # تعريف النماذج (منفصل عن core)
│   ├── base.py                # BaseImageModel + BaseVideoModel + ModelRegistry
│   ├── image/                 # نماذج توليد الصور (6 نماذج)
│   ├── video/                 # نماذج توليد الفيديو (9 نماذج)
│   └── extra/                 # نماذج إضافية (upscale, background remover)
│
├── config/                    # الإعدادات والثوابت
│   ├── endpoints.py           # جميع مسارات API
│   ├── constants.py          # نسب العرض/الارتفاع، الدقات
│   └── user_agent.py          # User-Agent strings
│
├── utils/                     # الأدوات المساعدة
│   ├── cookie_parser.py       # محلل ملفات الكوكيز
│   ├── file_helpers.py       # عمليات الملفات (Base64, حفظ)
│   └── logger.py              # نظام السجلات
│
└── api/                       # سيرفر API المحلي
    ├── server.py              # إنشاء تطبيق FastAPI
    ├── routes/                # المسارات (image, video, status)
    ├── schemas/               # نماذج Pydantic للطلب والاستجابة
    └── middleware/            # الوسائط (Rate Limiter, Error Handler)
```

---

## التثبيت والتشغيل

### المتطلبات

```bash
pip install -r requirements.txt
```

| الحزمة | الغرض |
|--------|-------|
| `curl_cffi>=0.7.0` | عميل HTTP مع تقليد بصمة TLS (تخطي Cloudflare) |
| `fastapi>=0.110.0` | إطار عمل السيرفر المحلي |
| `uvicorn>=0.30.0` | خادم ASGI لتشغيل FastAPI |
| `pydantic>=2.0.0` | التحقق من البيانات والـ Schemas |
| `python-dotenv>=1.0.0` | تحميل متغيرات البيئة |

### ملف الكوكيز

يجب توفير ملف كوكيز بصيغة Netscape (مثل الذي يتم تصديره من إضافة Cookie-Editor). الملف يجب أن يحتوي على الكوكيز التالية كحد أدنى:

| الكوكي | الغرض | ضروري؟ |
|--------|-------|--------|
| `GR_TOKEN` | JWT token للمصادقة (HttpOnly) | نعم |
| `XSRF-TOKEN` | CSRF protection token | نعم (يتم تحديثه تلقائياً) |
| `GR_REFRESH` | Refresh token (HttpOnly) | نعم |
| `magnific_session` | Session cookie | نعم |
| `GRID` | معرف المستخدم | نعم |
| `UID` | معرف المستخدم | نعم |

> **ملاحظة مهمة**: الكوكيز التي تبدأ بـ `#HttpOnly_` في ملف Netscape يتم قراءتها تلقائياً من قبل `CookieParser`. لا تحذف هذه الأسطر.

### توليد صورة (CLI)

```bash
python main.py image \
  --cookies /path/to/pinj_magnific.txt \
  --prompt "a majestic golden dragon flying over mountains" \
  --model imagen-nano-banana-2 \
  --ratio 1:1 \
  --res 4k \
  -o output.png
```

### توليد فيديو (CLI)

```bash
python main.py video \
  --cookies /path/to/pinj_magnific.txt \
  --prompt "eagle soaring over mountains at sunrise" \
  --model bytedance-seedance-pro-2.0 \
  --ratio 16:9 \
  --duration 5 \
  --resolution 1080p \
  -o output.mp4
```

### تشغيل سيرفر API المحلي

```bash
python main.py serve \
  --cookies /path/to/pinj_magnific.txt \
  --port 8080
```

بعد التشغيل:
- **Swagger UI**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/api/health
- **قائمة النماذج**: http://localhost:8080/api/models

### عرض النماذج المتاحة

```bash
python main.py models
```

---

## تدفق العمل (Workflow)

### توليد الصور (Image Generation Flow)

```
1. تحميل الكوكيز ← CookieParser
2. إنشاء عميل HTTP ← MagnificClient (curl_cffi + Chrome 136 TLS)
3. تحديث XSRF-TOKEN ← GET /sanctum/csrf-cookie
4. تسجيل الجهاز ← POST /user/api/devices/identify
5. طلب توليد ← POST /api/start-tti-v2 (يُرجع family + request_token)
6. بدء التوليد ← POST /api/render/v4 (يُرجع creation_id)
7. فحص الحالة ← GET /api/creation/{id} (polling حتى completed)
8. تحميل الصورة ← GET {download_url}
```

### توليد الفيديو (Video Generation Flow)

```
1. تحميل الكوكيز ← CookieParser
2. إنشاء عميل HTTP ← MagnificClient
3. تحديث XSRF-TOKEN + تسجيل الجهاز
4. (اختياري) رفع صور مرجعية ← upload-frame / temporal-storage
5. طلب توليد ← POST /api/video/generate (يُرجع creation_id)
6. فحص الحالة ← GET /api/creation/{id} (polling حتى completed)
7. تحميل الفيديو ← GET {download_url}
```

> **ملاحظة**: عند تلقي HTTP 429 (Rate Limit - concurrent creations)، يقوم الكود بإعادة المحاولة تلقائياً حتى 5 مرات مع زيادة تدريجية في الانتظار (15s, 30s, 45s, 60s, 75s).

---

## إضافة نموذج جديد

إضافة نموذج جديد = إنشاء ملف Python واحد فقط. النظام يكتشفه تلقائياً.

### إضافة نموذج صورة

أنشئ ملفاً جديداً في `models/image/`:

```python
# models/image/my_new_model.py
from models.base import BaseImageModel

my_new_model = BaseImageModel(
    slug="my-new-model",           # معرف النموذج في API
    display_name="My New Model",    # الاسم المعروض
    credits="50-100",               # تكلفة الكريديت
    resolutions=["1k", "2k", "4k"], # الدقات المتاحة
    max_refs=14,                     # أقصى عدد مراجع
)
```

### إضافة نموذج فيديو

أنشئ ملفاً جديداً في `models/video/`:

```python
# models/video/my_video_model.py
from models.base import BaseVideoModel

my_video_model = BaseVideoModel(
    slug="my-video-model",
    display_name="My Video Model",
    api="myapi",
    model="mymodel",
    mode="default",
    family="myfamily",
    duration_range=(4, 10),
    aspect_ratios=["16:9", "1:1"],
    resolutions=["1080p", "720p"],
    max_image_refs=5,
    max_video_refs=1,
    supports_sound=True,
    supports_keyframes=["start", "end"],
)
```

عند تشغيل `main.py` أو `serve`، سيتم اكتشاف النموذج الجديد تلقائياً وتسجيله في الـ `ModelRegistry`.

---

## حل المشاكل الشائعة

| المشكلة | السبب | الحل |
|---------|-------|------|
| HTTP 429 — Rate Limited | وصول لحد التوليد المتزامن | الكود يعيد المحاولة تلقائياً. انتظر حتى تكتمل التوليدات السابقة |
| HTTP 401 — Unauthorized | انتهاء صلاحية GR_TOKEN | صدّر ملف كوكيز جديد من المتصفح مع GR_TOKEN (HttpOnly) |
| HTTP 419 — CSRF Token Mismatch | انتهاء صلاحية XSRF-TOKEN | يتم تحديثه تلقائياً. إذا استمرت المشكلة أعد تصدير الكوكيز |
| HTTP 403 — Device Limit | تسجيل عدد كبير من الأجهزة | أزل بعض الأجهزة من إعدادات الحساب |
| HTTP 455/456 — Content Restricted | محتوى مخالف لسياسات الأمان | عدّل الـ prompt وأزل المحتوى الحساس |
| Polling Timeout | التوليد يستغرق وقتاً أطول من المهلة | زِد `--poll-timeout` في CLI أو `poll_timeout` في السيرفر |

---

## التوثيق

| الملف | المحتوى |
|-------|---------|
| [README.md](README.md) | نظرة عامة، التثبيت، التشغيل، حل المشاكل |
| [ARCHITECTURE.md](ARCHITECTURE.md) | هيكل التصميم، طبقات المشروع، تدفق البيانات |
| [API.md](API.md) | توثيق كامل لسيرفر API المحلي |
| [MODELS.md](MODELS.md) | توثيق جميع النماذج بالتفصيل |
| [CLI.md](CLI.md) | جميع أوامر سطر الأوامر مع الأمثلة |
| [CONFIG.md](CONFIG.md) | الإعدادات، متغيرات البيئة، التكوين |
| [SECURITY.md](SECURITY.md) | طبقات الحماية وكيفية تخطيها |
