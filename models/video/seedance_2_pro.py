from models.base import BaseVideoModel

seedance_2_pro = BaseVideoModel(
    slug="bytedance-seedance-pro-2.0",
    display_name="Seedance 2.0 Pro",
    api="bytedance",
    model="seedance",
    mode="pro-2.0",
    family="bytedance",
    duration_range=(4, 15),
    aspect_ratios=["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"],
    resolutions=["1080p", "720p", "480p"],
    max_image_refs=9,
    max_video_refs=2,
    max_audio_refs=2,
    multishot_max=6,
    supports_sound=True,
    supports_keyframes=["start", "end"],
)
