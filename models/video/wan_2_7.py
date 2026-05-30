from models.base import BaseVideoModel

wan_2_7 = BaseVideoModel(
    slug="wan-2-7",
    display_name="Wan 2.7",
    api="wan",
    model="wan",
    mode="2.7",
    family="wan",
    duration_range=(5, 10),
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["1080p", "720p"],
    max_image_refs=5,
    max_video_refs=1,
    max_audio_refs=0,
    multishot_max=5,
    supports_sound=False,
    supports_keyframes=["start", "end"],
)
