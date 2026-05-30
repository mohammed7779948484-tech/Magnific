from models.base import BaseVideoModel

runway_act_two = BaseVideoModel(
    slug="runway-act-two",
    display_name="Runway Act Two",
    api="runway",
    model="act",
    mode="two",
    family="runway",
    duration_range=(5, 10),
    aspect_ratios=["16:9", "9:16", "1:1"],
    resolutions=["1080p", "720p"],
    max_image_refs=2,
    max_video_refs=0,
    max_audio_refs=0,
    multishot_max=0,
    supports_sound=False,
    supports_keyframes=["start"],
)
