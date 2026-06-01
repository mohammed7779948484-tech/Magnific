from models.base import BaseImageModel

gpt_2 = BaseImageModel(
    slug="gpt-2",
    display_name="GPT 2",
    credits="25-2100",
    resolutions=["1k", "2k", "4k"],
    max_refs=16,
)
