from models.base import BaseVideoModel

google_veo_3_1 = BaseVideoModel(
    slug="google-veo3_1",
    display_name="Google Veo 3.1",
    api="google",
    model="veo",
    mode="3_1",
    family="google",
    duration_range=(8, 8),
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["1080p", "720p"],
    max_image_refs=3,
    max_video_refs=0,
    max_audio_refs=0,
    multishot_max=0,
    supports_sound=False,
    supports_keyframes=["start"],
)
