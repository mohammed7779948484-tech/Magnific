from models.base import BaseImageModel

google_imagen_4 = BaseImageModel(
    slug="imagen4",
    display_name="Imagen 4",
    credits="100-100",
    resolutions=["1k", "2k", "4k"],
    max_refs=14,
)
