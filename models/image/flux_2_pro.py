from models.base import BaseImageModel

flux_2_pro = BaseImageModel(
    slug="flux-2-pro",
    display_name="Flux.2 Pro",
    credits="50-175",
    resolutions=["1k", "2k", "4k"],
    max_refs=14,
)
