from models.base import BaseImageModel

gpt_1_5_high = BaseImageModel(
    slug="gpt-1-5-high",
    display_name="GPT 1.5 High",
    credits="100-200",
    resolutions=["1k", "2k", "4k"],
    max_refs=14,
)
