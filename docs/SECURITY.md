# SECURITY — طبقات الحماية وكيفية تخطيها

> وصف تفصيلي لجميع طبقات الحماية التي تستخدمها منصة Magnific/Freepik وكيف يتعامل المشروع مع كل واحدة برمجياً بدون متصفح.

---

## نظرة عامة

منصة Magnific تستخدم عدة طبقات حماية متتالية:

```
طلب HTTP → Cloudflare (TLS + WAF) → Akamai (Bot Management) → Laravel (XSRF CSRF) → API
```

المشروع يتخطى كل طبقة برمجياً عبر تقنيات محددة.

---

## الطبقة الأولى: Cloudflare (TLS Fingerprint + WAF)

### ما هي Cloudflare؟

Cloudflare CDN/WAF تفحص كل طلب HTTP وتحلل:
1. **بصمة TLS (JA3/JA4 Fingerprint)** — تتحقق من TLS handshake هل هو من متصفح حقيقي
2. **User-Agent** — تتحقق من توافق UA مع بصمة TLS
3. **WAF Rules** — تفحص محتوى الطلب (headers, body, URL)

### المشكلة

مكتبة `requests` العادية في Python تبني TLS handshake بشكل مختلف عن المتصفح، فـ Cloudflare تحظرها فوراً وتُرجع **403 Forbidden** أو **Challenge Page**.

### الحل: curl_cffi + Chrome 136 TLS Impersonation

المشروع يستخدم مكتبة **curl_cffi** بدلاً من `requests`. هذه المكتبة تُ模仿 (impersonate) بصمة TLS الخاصة بـ Chrome 136:

```python
# في core/client.py
from curl_cffi.requests import Session

session = Session(impersonate="chrome136")
```

**ما يحدث:**
1. curl_cffi يبني TLS ClientHello بنفس ترتيب cipher suites وextensions مثل Chrome 136
2. شهادة TLS تبدو وكأنها من Chrome حقيقي
3. Cloudflare تُوافق الطلب وتُمرره

**النتيجة:** HTTP 200 بدلاً من 403.

### إعدادات curl_cffi في المشروع

| الإعداد | القيمة | الملف |
|---------|--------|-------|
| `impersonate` | `chrome136` | `config/user_agent.py` |
| `User-Agent` | Chrome 136 on Windows 10 | `config/user_agent.py` |
| `Sec-Ch-Ua` | `"Chromium";v="136", "Not.A/Brand";v="99"` | `core/client.py` |
| `Sec-Ch-Ua-Mobile` | `?0` | `core/client.py` |
| `Sec-Ch-Ua-Platform` | `"Windows"` | `core/client.py` |
| `Sec-Fetch-Dest` | `empty` | `core/client.py` |
| `Sec-Fetch-Mode` | `cors` | `core/client.py` |
| `Sec-Fetch-Site` | `same-origin` | `core/client.py` |
| `Origin` | `https://www.magnific.com` | `core/client.py` |
| `Referer` | `https://www.magnific.com/` | `core/client.py` |

> **ملاحظة**: كل هذه Headers يجب أن تكون متطابقة. إذا تغيّر `impersonate` يجب تغيير `User-Agent` و `Sec-Ch-Ua` ليتطابقوا.

---

## الطبقة الثانية: Akamai Bot Management

### ما هي Akamai؟

Akamai هي خدمة حماية إضافية تعمل كـ WAF ثانوي. تحلل:
- سلوك التصفح (mouse movements, clicks, scroll)
- JavaScript challenges
- Sensor data collection

### الكوكي: `ak_bmsc`

Akamai تضع كوكي `ak_bmsc` (Bot Management Session Cookie) التي تحتوي على بيانات التحقق. هذه الكوكي **session-bound** — لا تعمل إذا استُخدمت من جلسة مختلفة.

### الحل: تخطي الكوكي

المشروع يتخطى كوكي `ak_bmsc` عن طريق عدم تضمينها في الطلب. في `cookie_parser.py`:

```python
SKIP_COOKIES = {
    "ak_bmsc",  # Akamai bot management — session-bound
    ...
}
```

**السبب:** Akamai تعتمد أساساً على JavaScript challenges و fingerprint. مع curl_cffi و TLS الصحيح، الطلبات تمر بدون الحاجة لـ ak_bmsc.

---

## الطبقة الثالثة: Laravel XSRF/CSRF Protection

### ما هي XSRF؟

منصة Magnific مبنية على Laravel، وتستخدم CSRF protection عبر XSRF-TOKEN. كل طلب POST يجب أن يحتوي على header `X-XSRF-TOKEN` مع القيمة الصحيحة.

### التدفق

```
1. GET /sanctum/csrf-cookie
   ← السيرفر يُرجع XSRF-TOKEN cookie (URI-encoded)

2. قراءة XSRF-TOKEN من session cookies
3. فك ترميز URI encoding
4. إضافته كـ header: X-XSRF-TOKEN: <decoded_value>

5. POST /api/...
   Header: X-XSRF-TOKEN: <decoded_value>
   ← السيرفر يتحقق من تطابق القيمة مع الكوكي
```

### الحل: refresh_xsrf()

في `core/auth.py`:

```python
def refresh_xsrf(self) -> str:
    # 1. حذف القديم
    del self.client.session.cookies["XSRF-TOKEN"]

    # 2. طلب جديد
    self.client.get(Endpoints.csrf_cookie())

    # 3. قراءة من الكوكيز
    raw_xsrf = self.client.session.cookies.get("XSRF-TOKEN")

    # 4. فك ترميز URI
    decoded_xsrf = unquote(raw_xsrf)

    # 5. تخزين في client
    self.client.xsrf_token = decoded_xsrf
    return decoded_xsrf
```

> **مهم:** XSRF-TOKEN مُخزّن كـ Laravel encrypted cookie. لا يمكن تزويره. يجب دائماً تحديثه من السيرفر.

### ماذا يحدث إذا فشل؟

HTTP **419 CSRF Token Mismatch** — الـ client يُرجع `AuthenticationError`.

---

## الطبقة الرابعة: Device Identification

### ما هي؟

منصة Freepik تُسجل الأجهزة التي تتصل بالـ API. كل جهاز يحصل على معرف فريد. الحساب المجاني يسمح بـ **5 أجهزة**، والحساب المدفوع بـ **15 جهاز**.

### الـ Endpoint

```
POST /user/api/devices/identify
Body: {} (فارغ — الجهاز يُعرّف نفسه من خلال الكوكيز)
```

### التدفق

```
1. يحتاج: GR_TOKEN (Firebase JWT) + cookies صالحة
2. POST /user/api/devices/identify
3. Response: {success: true, disabled: false}
```

### الحل: identify_device()

في `core/auth.py`:

```python
def identify_device(self) -> dict:
    result = self.client.post(Endpoints.DEVICE_IDENTIFY, json_data={})
    return result
```

### ماذا يحدث إذا فشل؟

- HTTP **403 Forbidden** مع رسالة "device limit" — يعني وصلت لحد الأجهزة
- `{disabled: true}` — الجهاز مُسجل لكن معطل (قد تحتاج تفعيل)

---

## الطبقة الخامسة: Firebase Authentication (GR_TOKEN)

### ما هي؟

المصادقة الفعلية تتم عبر Firebase. الـ `GR_TOKEN` هو **JWT token** صادر من Firebase Auth.

### بنية GR_TOKEN

```
Header:  {"alg": "RS256", "kid": "..."}
Payload: {
  "name": "Vijay Alagar",
  "picture": "https://avatar.cdnpk.net/default_06.png",
  "accounts_user_id": 56415455,
  "scopes": "freepik/images freepik/videos flaticon/png freepik/images/premium ...",
  "iss": "https://securetoken.google.com/fc-profile-pro-rev1",
  "auth_time": 1763396025,
  "user_id": "0d7edf47...",
  "email": "vijay@pinakindesign.in",
  "email_verified": true,
  "firebase": {
    "identities": {"google.com": ["1117618487..."]},
    "sign_in_provider": "custom"
  },
  "iat": 1780152463,
  "exp": 1780156063  ← صالح لمدة ساعة فقط!
}
```

### الكوكي

```
#HttpOnly_.magnific.com TRUE / TRUE 1780156063 GR_TOKEN eyJhbGci...
```

### مشكلة: الصلاحية ساعة واحدة فقط!

GR_TOKEN صالح لمدة **ساعة واحدة** فقط. لكن مع `GR_REFRESH` token، يمكن تجديده تلقائياً.

### الحل الحالي

المشروع يعتمد على الكوكيز المُصدرة من المتصفح. إذا انتهت صلاحية GR_TOKEN:
1. أعد تصدير الكوكيز من المتصفح (الذي يُجدد تلقائياً)
2. مرر ملف الكوكيز الجديد لـ CLI أو السيرفر

### تطوير مستقبلي: تجديد تلقائي

يمكن إضافة منطق تجديد GR_TOKEN باستخدام GR_REFRESH:
```
POST /user/api/auth/refresh
Cookie: GR_REFRESH=<token>
→ يُرجع GR_TOKEN جديد
```

---

## الطبقة السادسة: Rate Limiting

### أنواع Rate Limits

| النوع | الرمز | الوصف |
|-------|-------|-------|
| Concurrent Creations | 429 | عدد التوليدات المتزامنة (عادة 1-2) |
| API Rate Limit | 429 | عدد الطلبات في الدقيقة |
| Device Limit | 403 | عدد الأجهزة المسجلة |

### الحل: Auto-Retry

في `main.py` (أمر video):

```python
max_retries = 5
retry_delay = 15
for attempt in range(max_retries):
    try:
        result = client.post("/api/video/generate?return_creations=true", ...)
        break
    except RateLimitError:
        wait = retry_delay * (attempt + 1)  # 15, 30, 45, 60, 75
        time.sleep(wait)
```

### Rate Limit المحلي

السيرفر المحلي يُطبق أيضاً rate limiting:
- الافتراضي: 20 طلب/دقيقة لكل IP
- قابل للتعديل عبر `--rate-limit` flag
- المسارات المستثناة: `/api/health`, `/docs`

---

## الطبقة السابعة: Content Safety Filters

### ما هي؟

Magnific تُطبق فلاتر محتوى على الـ prompts والنتائج.

### رموز الحجب

| الرمز | الوصف |
|-------|-------|
| HTTP **455** | محتوى مقيد (content restricted) |
| HTTP **456** | محتوى محظور (content blocked) |

### الحل: تعديل الـ Prompt

فلاتر المحتوى تُحظر:
- العنف Explicit
- المحتوى الجنسي
- الكراهية والتمييز
- الأنشطة غير القانونية

عند استلام 455/456، عدّل الـ prompt وأزل المحتوى الحساس.

---

## ملخص أمني

| الطبقة | الهدف | آلية التخطي | الملف |
|--------|-------|-------------|-------|
| Cloudflare TLS | منع البوتات | curl_cffi chrome136 impersonation | `core/client.py` |
| Akamai Bot Mgmt | تحليل السلوك | تخطي ak_bmsc cookie | `utils/cookie_parser.py` |
| XSRF/CSRF | حماية الطلبات | refresh_xsrf() + header | `core/auth.py` |
| Device ID | تسجيل الأجهزة | identify_device() | `core/auth.py` |
| Firebase Auth | المصادقة | GR_TOKEN من الكوكيز | ملف الكوكيز |
| Rate Limit | تحديد الطلبات | Auto-retry with backoff | `main.py` |
| Content Safety | فلاتر المحتوى | تعديل prompt | يدوي |
