from models.base import BaseImageModel

google_imagen_4 = BaseImageModel(
    slug="google-imagen-4",
    display_name="Google Imagen 4",
    credits="75-150",
    resolutions=["1k", "2k", "4k"],
    max_refs=14,
)
