from models.base import BaseVideoModel

seedance_1_5_lite = BaseVideoModel(
    slug="bytedance-seedance-lite-1.5",
    display_name="Seedance 1.5 Lite",
    api="bytedance",
    model="seedance",
    mode="lite-1.5",
    family="bytedance",
    duration_range=(4, 10),
    aspect_ratios=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
    resolutions=["1080p", "720p", "480p"],
    max_image_refs=4,
    max_video_refs=0,
    max_audio_refs=2,
    multishot_max=3,
    supports_sound=True,
    supports_keyframes=["start"],
)
