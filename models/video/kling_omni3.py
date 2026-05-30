from models.base import BaseVideoModel

kling_omni3 = BaseVideoModel(
    slug="kling-omni3",
    display_name="Kling 3.0 Omni",
    api="kling",
    model="kling",
    mode="omni3",
    family="kling",
    duration_range=(5, 10),
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["1080p", "720p"],
    max_image_refs=7,
    max_video_refs=1,
    max_audio_refs=0,
    multishot_max=6,
    supports_sound=False,
    supports_keyframes=["start", "end"],
)
