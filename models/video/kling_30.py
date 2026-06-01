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
