from models.base import BaseVideoModel

kling_motion_control_30 = BaseVideoModel(
    slug="kling-motion-control-30",
    display_name="Kling 3.0 Motion Control",
    api="kling",
    model="kling",
    mode="motion-control-30",
    family="kling",
    duration_range=(3, 15),
    aspect_ratios=[],
    resolutions=["720p", "1080p"],
    max_image_refs=1,
    max_video_refs=1,
    max_audio_refs=0,
    multishot_max=0,
    supports_sound=False,
    supports_keyframes=["start", "video"],
)
