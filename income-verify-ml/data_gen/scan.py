"""Turn a clean PDF into what applicants really upload: a crooked, noisy scan, or a phone photo of page 1."""
import io
import random
import pymupdf
from PIL import Image, ImageEnhance, ImageFilter

def page_images(pdf: bytes, dpi: int) -> list:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return [Image.open(io.BytesIO(page.get_pixmap(dpi=dpi).tobytes("png"))).convert("RGB") for page in doc]

def roughen(img: Image.Image, rng: random.Random) -> Image.Image:
    """Slight rotation, blur, grain and contrast loss."""
    img = img.rotate(rng.uniform(-1.5, 1.5), resample=Image.BICUBIC, expand=False, fillcolor=(255, 255, 255))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.8)))
    noise = Image.effect_noise(img.size, rng.uniform(12, 25)).convert("RGB")
    img = Image.blend(img, noise, 0.06)
    return ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 1.0))

def jpeg(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()

def to_scan(pdf: bytes, rng: random.Random) -> bytes:
    """Every page re-made as a rough JPEG inside a PDF — no text layer left, like a photocopier scan."""
    out = pymupdf.open()
    for img in page_images(pdf, 140):
        data = jpeg(roughen(img, rng), rng.randint(45, 70))
        page = out.new_page(width=595, height=842)
        page.insert_image(page.rect, stream=data)
    return out.tobytes(garbage=3, deflate=True)

def to_photo(pdf: bytes, rng: random.Random) -> bytes:
    """Page 1 as a phone photo: on a darker background, slightly skewed and warm, saved as JPEG."""
    img = roughen(page_images(pdf, 120)[0], rng)
    w, h = img.size
    canvas = Image.new("RGB", (int(w * 1.12), int(h * 1.08)), (rng.randint(90, 140), rng.randint(80, 120), rng.randint(60, 100)))
    canvas.paste(img, (int(w * 0.06), int(h * 0.04)))
    canvas = canvas.rotate(rng.uniform(-3, 3), resample=Image.BICUBIC, fillcolor=(70, 60, 50))
    r, g, b = canvas.split()
    canvas = Image.merge("RGB", (r.point(lambda v: min(255, v + 8)), g, b.point(lambda v: max(0, v - 8))))
    return jpeg(canvas, rng.randint(55, 75))
