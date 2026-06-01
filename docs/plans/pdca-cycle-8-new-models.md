# PDCA Cycle 8 — إضافة نماذج Kling 3.0 و Kling 3.0 Omni و GPT Image 2

> **التاريخ**: 2026-06-02
> **الفرع**: `feature/multi-account-smart-routing` → سيتم العمل على `main`
> **الأهداف**: إضافة 3 نماذج جديدة + تحديث نموذج موجود + تحديث التوثيق والاختبارات

---

## 1. PLAN: التحليل والتخطيط

### 1a. تحليل المشكلة (Analysis)

**الهدف العام**: إضافة النماذج الجديدة Kling 3.0 و Kling 3.0 Omni (تحديث) و GPT Image 2 إلى المشروع مع جميع الباراميترز الخاصة بكل نموذج.

**Architecture Pattern Discovery (خطوة إلزامية):**

- ✅ **SEARCH 1**: أُجري البحث عن نماذج مشابهة — تم فحص كل ملفات `models/image/` و `models/video/`
- ✅ **SEARCH 2**: تم فحص `ModelRegistry.discover()` وآلية التسجيل التلقائي
- ✅ **SEARCH 3**: تم فحص `tests/test_models.py` لفهم أنماط الاختبار

**النتائج — أنماط معمارية موجودة:**

1. **إضافة نموذج فيديو جديد** = إنشاء ملف واحد في `models/video/` مع `BaseVideoModel` dataclass
2. **إضافة نموذج صور جديد** = إنشاء ملف واحد في `models/image/` مع `BaseImageModel` dataclass
3. **التسجيل التلقائي** عبر `__post_init__` → لا حاجة لتعديل أي ملف آخر
4. **الاختبارات** = إضافة اختبارات في `tests/test_models.py` مع `autouse` fixture لإعادة تعيين الـ registry

**المصدر الأساسي**: بيانات API الحقيقية من `downloads/api_explore/image_ai_models.json`

---

### 1b. النتائج من استكشاف API

#### النموذج 1: Kling 3.0 (جديد بالكامل)

| الحقل | القيمة |
|-------|--------|
| **Slug** | `kling-30` |
| **API** | `kling` |
| **Model** | `kling` |
| **Mode** | `30` |
| **Duration** | 3-15 ثواني (أوسع من النماذج الحالية!) |
| **Resolutions** | `720p`, `1080p`, `4K` (أول نموذج Kling يدعم 4K!) |
| **Aspect Ratios** | `16:9`, `9:16`, `1:1` |
| **Sound Effects** | ✅ نعم |
| **Multishot** | 6 مشاهد |
| **Keyframes** | `start`, `end` |
| **Image Refs** | start frame + end frame + 3 character + 3 product + 3 advanced = **12** |
| **Video Refs** | 0 |
| **Audio Refs** | 0 |
| **Negative Prompt** | ✅ نعم |
| **Camera Motion** | 24 حركة |
| **FPS** | 24 |
| **Credits** | 210-6000 |
| **Beta** | نعم |
| **Best For** | realistic_videos, illustration_animation, fast_movements |

#### النموذج 2: Kling 3.0 Omni (تحديث نموذج موجود!)

| الحقل | القيمة الحالية | القيمة الصحيحة من API |
|-------|---------------|----------------------|
| **Duration** | (5, 10) | **(3, 15)** |
| **Resolutions** | ["1080p", "720p"] | **["720p", "1080p", "4K"]** |
| **Sound Effects** | ❌ False | **✅ True** |
| **Multishot** | 6 | 6 ✅ (صحيح) |
| **Image Refs** | 7 | 7 ✅ (7 بدون فيديو، 4 مع فيديو) |
| **Video Refs** | 1 | 1 ✅ |
| **Keyframes** | start, end | start, end ✅ |
| **Lipsync** | غير موجود | **✅ يدعم lipsync** |
| **Credits** | غير موجود | 210-6000 |
| **Camera Motion** | غير موجود | 24 حركة |
| **FPS** | غير موجود | 24 |

**الخلاصة**: ملف `models/video/kling_omni3.py` يحتاج تحديث significative — مدة أطول، دقة أعلى (4K)، دعم صوت.

#### النموذج 3: GPT Image 2 / GPT 2 (جديد بالكامل)

| الحقل | القيمة |
|-------|--------|
| **Slug** | `gpt-2` |
| **Display** | GPT 2 |
| **Credits** | 25-2100 |
| **Resolutions** | `1k`, `2k`, `4k` |
| **Aspect Ratios** | `auto`, `1:1`, `2:1`, `3:1`, `2:3`, `3:2`, `3:4`, `4:3`, `16:9`, `9:16`, `21:9` (11 نسبة!) |
| **Max Refs** | 16 (الأعلى بين كل النماذج!) |
| **Quality** | `low`, `medium`, `high` |
| **Seed** | ✅ مدعوم |
| **Num Images** | 1-8 صور في الطلب الواحد |
| **Smart Prompt** | ✅ مدعوم (افتراضي: نعم) |
| **Color Palette** | ✅ مدعوم (max 6 ألوان) |
| **Effects** | ✅ مدعوم |
| **Camera** | ✅ مدعوم |
| **Character Generator** | ✅ نعم |
| **Max Prompt Length** | 10000 (الأطول!) |
| **Reference Types** | style (1), character (1), product (1), image (16) |
| **Type** | text-to-image |
| **Best For** | text_layout, infographic, ui_design, diagram, typography, non_photorealistic_design |

#### نموذج إضافي مكتشف: Kling 3.0 Motion Control

| الحقل | القيمة |
|-------|--------|
| **Slug** | `kling-motion-control-30` |
| **API** | `kling` |
| **Mode** | `motion-control-30` |
| **Duration** | 3-15 ثواني |
| **Resolutions** | `720p`, `1080p` (لا يدعم 4K) |
| **Sound** | ❌ لا |
| **Multishot** | ❌ لا |
| **Motion Control** | ✅ نعم |
| **Lipsync** | ✅ نعم |
| **Start Frame** | إلزامي (مطلوب) |
| **Video Upload** | إلزامي (مطلوب) — 1 فيديو مرجعي |
| **Image Upload** | إلزامي (مطلوب) — 1 صورة start frame |
| **Credits** | 330-2250 |
| **Best For** | realistic_videos, motion_control, lipsync |

> **ملاحظة**: هذا النموذج يحتوي على قيود خاصة (start frame إلزامي، video ref إلزامي) — سيتم وضعه في `models/extra/` كنموذج خاص.

---

### 1c. مقارنة النماذج

| الميزة | Kling 3.0 | Kling 3.0 Omni | Kling 3.0 MC | GPT Image 2 |
|--------|-----------|---------------|--------------|-------------|
| **النوع** | فيديو | فيديو | فيديو | صور |
| **المدة** | 3-15s | 3-15s | 3-15s | N/A |
| **4K** | ✅ | ✅ | ❌ | ✅ |
| **Sound** | ✅ | ✅ | ❌ | N/A |
| **Multishot** | 6 | 6 | ❌ | N/A |
| **Lipsync** | ❌ | ✅ | ✅ | N/A |
| **Motion Control** | ❌ | ❌ | ✅ | N/A |
| **Video Ref** | ❌ | ✅ | ✅ (إلزامي) | N/A |
| **Max Prompt** | 2500 | 2500 | 2500 | **10000** |
| **Credits Min** | 210 | 210 | 330 | **25** |
| **Credits Max** | 6000 | 6000 | 2250 | 2100 |
| **Beta** | نعم | لا | نعم | لا |
| **New** | نعم | نعم | نعم | نعم |
| **Featured** | نعم | نعم | لا | نعم |

---

### 1d. التخطيط التفصيلي (Planning)

**Integration Strategy:**
- الخريطة: نموذج جديد = ملف `.py` واحد → `ModelRegistry.discover()` يكتشفه تلقائياً
- لا يوجد ملفات أخرى تحتاج تعديل (لا routes، لا schemas، لا config)
- الاختبارات تُضاف في `tests/test_models.py`
- التوثيق يُحدث في `docs/MODELS.md`

**Testing Strategy (TDD):**
1. اختبار تسجيل النموذج الجديد (auto-register)
2. اختبار بناء video body مع الباراميترز الصحيحة
3. اختبار to_dict serialization
4. اختبار تحديث Kling Omni3 (القيم الجديدة)
5. اختبار اكتشاف الكل عبر `ModelRegistry.discover()`

**Preparatory Refactoring:**
- ❌ لا حاجة — البنية جاهزة

---

## 2. DO: خطوات التنفيذ

### الخطوة 1: تحديث نموذج Kling 3.0 Omni الموجود

**الملف**: `models/video/kling_omni3.py`
**النوع**: تحديث باراميترز
**التغييرات:**

```python
# BEFORE (الحالي):
kling_omni3 = BaseVideoModel(
    slug="kling-omni3",
    display_name="Kling 3.0 Omni",
    api="kling",
    model="kling",
    mode="omni3",
    family="kling",
    duration_range=(5, 10),           # ← خاطئ: API يدعم 3-15
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["1080p", "720p"],     # ← ناقص: API يدعم 4K
    max_image_refs=7,
    max_video_refs=1,
    max_audio_refs=0,
    multishot_max=6,
    supports_sound=False,               # ← خاطئ: API يدعم sound effects
    supports_keyframes=["start", "end"],
)

# AFTER (الصحيح من API):
kling_omni3 = BaseVideoModel(
    slug="kling-omni3",
    display_name="Kling 3.0 Omni",
    api="kling",
    model="kling",
    mode="omni3",
    family="kling",
    duration_range=(3, 15),            # ✅ مدة أطول: 3-15 ثواني
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["720p", "1080p", "4K"], # ✅ إضافة دقة 4K
    max_image_refs=7,
    max_video_refs=1,
    max_audio_refs=0,
    multishot_max=6,
    supports_sound=True,                # ✅ دعم مؤثرات صوتية
    supports_keyframes=["start", "end"],
)
```

**Acceptance Criteria:**
- ✅ `duration_range` = (3, 15)
- ✅ `resolutions` تحتوي "4K"
- ✅ `supports_sound` = True
- ✅ كل الاختبارات الحالية تمر (163+)

---

### الخطوة 2: إنشاء نموذج Kling 3.0 فيديو جديد

**الملف**: `models/video/kling_30.py` (جديد)
**النوع**: إنشاء ملف جديد

```python
from models.base import BaseVideoModel

kling_30 = BaseVideoModel(
    slug="kling-30",
    display_name="Kling 3.0",
    api="kling",
    model="kling",
    mode="30",
    family="kling",
    duration_range=(3, 15),
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["720p", "1080p", "4K"],
    max_image_refs=12,
    max_video_refs=0,
    max_audio_refs=0,
    multishot_max=6,
    supports_sound=True,
    supports_keyframes=["start", "end"],
)
```

**مبررات الباراميترز:**
- `max_image_refs=12`: start frame + end frame + 3 character + 3 product + 3 advanced references = 12 صور مرجعية قصوى
- `max_video_refs=0`: API لا يدعم رفع فيديو مرجعي (فقط Motion Control يفعل ذلك)
- `supports_sound=True`: API يدعم `soundEffects.allowed: true`
- `resolutions` تشمل `4K`: أول نموذج Kling يدعم 4K
- `duration_range=(3, 15)`: يدعم 3-15 ثانية (أوسع من النماذج الأقدم)

**Acceptance Criteria:**
- ✅ الملف موجود في `models/video/kling_30.py`
- ✅ `ModelRegistry.discover()` يسجله تلقائياً
- ✅ `ModelRegistry.get_video("kling-30")` يعمل بدون خطأ

---

### الخطوة 3: إنشاء نموذج Kling 3.0 Motion Control

**الملف**: `models/extra/kling_motion_control_30.py` (جديد في extra/)
**النوع**: إنشاء ملف جديد — نموذج خاص يحتاج start frame + video ref إلزاميين

```python
from models.base import BaseVideoModel

kling_motion_control_30 = BaseVideoModel(
    slug="kling-motion-control-30",
    display_name="Kling 3.0 Motion Control",
    api="kling",
    model="kling",
    mode="motion-control-30",
    family="kling",
    duration_range=(3, 15),
    aspect_ratios=[],          # فارغ — النسبة تُستنتج من start frame
    resolutions=["720p", "1080p"],
    max_image_refs=1,          # start frame إلزامي
    max_video_refs=1,          # video ref إلزامي
    max_audio_refs=0,
    multishot_max=0,
    supports_sound=False,
    supports_keyframes=["start", "video"],
)
```

**ملاحظة**: هذا النموذج لا يدعم `end` keyframe — يدعم `start` و `video` فقط.
أيضاً `aspect_ratios` فارغ لأن النسبة تُستنتج تلقائياً من الصورة/الفيديو المرفوع.

> **تنبيه**: يجب التأكد أن `ModelRegistry.discover()` لا يفحص `models/extra/` حالياً.
> إذا كان لا يفحصها، نحتاج إما:
> (أ) إضافة `_discover_extra_models()` إلى `ModelRegistry`
> (ب) أو وضعه في `models/video/` مباشرة

**Acceptance Criteria:**
- ✅ الملف موجود ويُسجل بشكل صحيح
- ✅ أو يُضاف في `models/video/` إذا `extra/` غير مدعوم

---

### الخطوة 4: إنشاء نموذج GPT Image 2

**الملف**: `models/image/gpt_2.py` (جديد)
**النوع**: إنشاء ملف جديد

```python
from models.base import BaseImageModel

gpt_2 = BaseImageModel(
    slug="gpt-2",
    display_name="GPT 2",
    credits="25-2100",
    resolutions=["1k", "2k", "4k"],
    max_refs=16,
)
```

**مبررات الباراميترز:**
- `slug="gpt-2"`: مطابق لـ `id` في API
- `credits="25-2100"`: من `credits.min=25`, `credits.max=2100`
- `max_refs=16`: أعلى حد صور مرجعية (style 1 + character 1 + product 1 + image 16 = 16)
- يدعم 11 نسبة عرض/ارتفاع (الأوسع بين كل النماذج)
- يدعم seed، quality levels، smart prompt، color palette، effects، camera

**Acceptance Criteria:**
- ✅ الملف موجود في `models/image/gpt_2.py`
- ✅ `ModelRegistry.discover()` يسجله تلقائياً
- ✅ `ModelRegistry.get_image("gpt-2")` يعمل بدون خطأ
- ✅ `to_dict()` يُرجع القيم الصحيحة

---

### الخطوة 5: إضافة اختبارات TDD

**الملف**: `tests/test_models.py`
**النوع**: إضافة اختبارات جديدة

**قائمة الاختبارات المطلوبة:**

| # | اسم الاختبار | السلوك المُختبر | الفئة |
|---|-------------|----------------|-------|
| T1 | `test_kling_30_auto_registers` | إنشاء kling_30 يُسجل في video registry | فيديو جديد |
| T2 | `test_kling_30_video_body` | build_video_body يُرجع slug=ًkling-30 و api=kling | فيديو جديد |
| T3 | `test_kling_30_to_dict` | to_dict يشمل duration=(3,15), 4K, sound=True | فيديو جديد |
| T4 | `test_gpt_2_auto_registers` | إنشاء gpt_2 يُسجل في image registry | صور جديد |
| T5 | `test_gpt_2_to_dict` | to_dict يشمل credits="25-2100", max_refs=16 | صور جديد |
| T6 | `test_kling_omni3_updated_params` | القيم المُحدّثة: duration(3,15), 4K, sound=True | تحديث |
| T7 | `test_kling_30_sound_in_video_body` | with_sound=True يُرسل withSoundEffects=true في body | فيديو |
| T8 | `test_discover_includes_new_models` | discover() يُحمّل 7 صور + 10 فيديو (الأرقام الجديدة) | registry |

**Acceptance Criteria:**
- ✅ كل اختبار جديد يمر
- ✅ كل 163 اختبار قديم يمر بدون تغيير
- ✅ لا استخدام `unittest.mock` (AST guard سيمنع ذلك)
- ✅ إجمالي الاختبارات ≥ 171

---

### الخطوة 6: تحديث التوثيق

**الملف**: `docs/MODELS.md`
**التغييرات:**
- تحديث العداد: **7 نماذج صور** (كان 6) و **10 نماذج فيديو** (كان 9) + 1 نموذج خاص
- إضافة قسم Kling 3.0 مع كل التفاصيل
- تحديث قسم Kling Omni3 بالقيم الجديدة (مدة 3-15، 4K، صوت)
- إضافة قسم GPT Image 2 مع كل التفاصيل
- إضافة قسم Kling 3.0 Motion Control
- تحديث جدول المقارنة في النهاية

---

## 3. CHECK: قائمة التحقق

### Completeness Check

- [ ] كل 3 نماذج جديدة مُنشأة (Kling 3.0, Kling 3.0 MC, GPT 2)
- [ ] Kling Omni3 مُحدّث بالقيم الصحيحة من API
- [ ] كل الاختبارات تمر (قديمة + جديدة)
- [ ] `ModelRegistry.discover()` يُكتشف كل النماذج
- [ ] التوثيق مُحدث
- [ ] لا يوجد regressions

### Process Audit

- [ ] TDD discipline: اختبار أحمر → أخضر → refactor
- [ ] Called Shot قبل كل اختبار
- [ ] لا استخدام mock
- [ ] BaseImageModel و BaseVideoModel يُستخدمان (لا abstractions جديدة)
- [ ] ملف واحد لكل نموذج (نمط موجود)

### Structural Review

- [ ] هل نحتاج تعديل `ModelRegistry` ليدعم `models/extra/`؟
- [ ] هل `aspect_ratios=[]` للمسار الحركي يعمل مع video route؟
- [ ] هل `supports_keyframes=["start", "video"]` نوع غير موجود مسبقاً؟

---

## 4. ACT: ملخص المتابعة

**سير العمل:**

1. فحص إذا كان `models/extra/` مدعوم في `ModelRegistry.discover()` → القرار: وضعه في `models/video/` مباشرة
2. إنشاء ملفات النماذج الجديدة (3 ملفات)
3. تحديث ملف Kling Omni3
4. إضافة اختبارات TDD (8 اختبارات)
5. تشغيل كل الاختبارات
6. تحديث التوثيق
7. Commit

**ملخص التنفيذ:**

| الخطوة | الملف | الإجراء | النوع |
|--------|-------|---------|-------|
| 1 | `models/video/kling_omni3.py` | تحديث باراميترز | تحديث |
| 2 | `models/video/kling_30.py` | إنشاء جديد | feat |
| 3 | `models/video/kling_motion_control_30.py` | إنشاء جديد | feat |
| 4 | `models/image/gpt_2.py` | إنشاء جديد | feat |
| 5 | `tests/test_models.py` | إضافة 8 اختبارات | test |
| 6 | `docs/MODELS.md` | تحديث التوثيق | docs |

**التوقعات:**
- 3 ملفات نماذج جديدة + 1 تحديث
- 8 اختبارات جديدة (171+ إجمالي)
- 163 اختبار قديم يمر بدون تغيير
- لا تغيير في routes أو schemas أو config
