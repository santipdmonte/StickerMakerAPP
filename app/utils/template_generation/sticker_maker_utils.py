from PIL import Image, ImageFilter, ImageChops
from pathlib import Path

class StickerMaker:
    def __init__(
        self,
        alpha_threshold=10,
        border_size=10,
        border_color=(255, 255, 255, 255),
        shadow_size=0,
        shadow_color=(0, 0, 0),
        shadow_transparency=100,
        shadow_blur_strength=6,
        padding=20,
        bg_color=(255, 255, 255, 255),
        bg_transparent=True,
        crop=True,
        siluette_color=(255, 0, 0, 255),
        siluette_blur_strength=1.5,
        siluette_border_size=3,
        siluette_border_distance=3,
        final_size=1024
    ):
        """
        Initializes the StickerMaker with parameters for border and shadow. \n
        * `alpha_threshold`: The alpha threshold for transparency detection.
        * `border_size`: The size of the border around the sticker.
        * `border_color`: The color of the border.
        * `shadow_size`: The size of the shadow around the sticker.
        * `shadow_color`: The color of the shadow.
        * `shadow_transparency`: The transparency of the shadow.
        * `shadow_blur_strength`: The strength of the blur applied to the shadow.
        * `padding`: The padding around the cropped image.
        * `siluette_color`: The color of the siluette.
        * `siluette_blur_strength`: The strength of the blur applied to the siluette.
        * `siluette_border_size`: The size of the border around the siluette.
        * `siluette_border_distance`: The distance between the border and the siluette.
        * `final_size`: The size of the final image.
        """

        self.alpha_threshold = alpha_threshold
        self.border_size = border_size
        self.border_color = border_color
        self.shadow_size = shadow_size
        self.shadow_color = shadow_color
        self.shadow_transparency = shadow_transparency
        self.shadow_blur_strength = shadow_blur_strength
        self.padding = padding
        self.bg_color = bg_color
        self.bg_transparent = bg_transparent
        self.crop = crop
        self.siluette_color = siluette_color
        self.siluette_blur_strength = siluette_blur_strength
        self.siluette_border_size = siluette_border_size
        self.siluette_border_distance = siluette_border_distance
        self.final_size = final_size

    def crop_transparent(self, image: Image.Image) -> Image.Image:
        """
        Crops the image to the smallest rectangle that contains all non-transparent pixels,
        and adds padding around it.
        """

        if image.mode != "RGBA":
            raise ValueError("Image must be in RGBA mode for transparency detection.")
        
        bbox = image.getbbox()

        if bbox:
            left, upper, right, lower = bbox
            left = max(0, left - self.padding)
            upper = max(0, upper - self.padding)
            right = min(image.width, right + self.padding)
            lower = min(image.height, lower + self.padding)
            return image.crop((left, upper, right, lower))
        else:
            print("Image is fully transparent.")
            return image
        

    def _center_on_square(self, img, final_size):

        # Asegurarse de que esté en modo RGBA (para transparencia)
        img = img.convert("RGBA")

        # Redimensionar proporcionalmente la imagen para que encaje dentro del cuadrado
        img.thumbnail((final_size, final_size), Image.LANCZOS)  # LANCZOS = alta calidad

        # Create a new blank image (transparent or with bg_color)
        if self.bg_transparent:
            background = Image.new("RGBA", (final_size, final_size), (0, 0, 0, 0))
        else:
            background = Image.new("RGBA", (final_size, final_size), self.bg_color)
        # Calculate top-left position to paste the image centered
        x = (final_size - img.width) // 2
        y = (final_size - img.height) // 2
        background.paste(img, (x, y), img)
        return background


    def make_sticker(self, image_path):
        """
        Creates a sticker from the image at `image_path` by adding a border and shadow.\n
        Returns the final image.
        """

        img = Image.open(image_path).convert("RGBA")
        img = self._center_on_square(img, self.final_size)

        if self.crop:
            img = self.crop_transparent(img)

        alpha = img.getchannel("A")
        mask = alpha.point(lambda p: 255 if p > self.alpha_threshold else 0)

        dilated = mask.filter(ImageFilter.MaxFilter(self.border_size * 2 + 1))
        border_mask = ImageChops.subtract(dilated, mask)
        border_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

       # White border layer
        white_border_layer = Image.new("RGBA", img.size, (255, 255, 255, 255))  # White
        white_border_layer.putalpha(border_mask)

        # Black shadow layer
        shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 255))  # Black
        shadow_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=self.shadow_blur_strength))
        shadow_layer.putalpha(shadow_mask)

        # Combine the layers: First white border, then shadow, then image
        final = Image.alpha_composite(white_border_layer, img)
        final = Image.alpha_composite(shadow_layer, final)

        if not self.bg_transparent:
            black_bg = Image.new("RGBA", img.size, self.bg_color)
            black_bg.paste(final, (0, 0), final)

            return black_bg

        return final
    
    def make_siluette(self, image_path, border = True):
        """
        Creates a sticker siluette to cut the sticker.
        Returns the final image.
        """

        img = Image.open(image_path).convert("RGBA")
        img = self._center_on_square(img, self.final_size)

        if self.crop:
            img = self.crop_transparent(img)

        if border:

            alpha = img.getchannel("A")
            mask = alpha.point(lambda p: 255 if p > self.alpha_threshold else 0)

            dilated = mask.filter(ImageFilter.MaxFilter(self.siluette_border_distance * 2 + 1))
            border_mask = ImageChops.subtract(dilated, mask)
            border_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

            # White border layer
            white_border_layer = Image.new("RGBA", img.size, (255, 255, 255, 255))  # White
            white_border_layer.putalpha(border_mask)

            # Combine the layers: First white border, then shadow, then image
            img = Image.alpha_composite(white_border_layer, img)

        # ===  =====

        alpha = img.getchannel("A")
        mask = alpha.point(lambda p: 255 if p > self.alpha_threshold else 0)

        dilated = mask.filter(ImageFilter.MaxFilter(self.siluette_border_size * 2 + 1))
        border_mask = ImageChops.subtract(dilated, mask)
        border_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=self.siluette_blur_strength))

        red_siluette = Image.new("RGBA", img.size, self.siluette_color) 
        red_siluette.putalpha(border_mask)

        return red_siluette

    
    def process(self, input_path, output_path):
        """Processes the image at input_path and saves the final sticker to output_path."""

        final_img = self.make_sticker(input_path)
        final_img.save(output_path, format="PNG", optimize=False, compress_level=0)

    def process_siluette(self, input_path, output_path):
        """Processes the image at input_path and saves the final sticker to output_path."""

        final_img = self.make_siluette(input_path)
        final_img.save(output_path, format="PNG", optimize=False, compress_level=0)

    def composite_siluette_on_sticker(self, sticker_path, siluette_path):
        """
        Composites the red silhouette on top of the sticker.
        Returns the final composited image.
        """
        sticker = Image.open(sticker_path).convert("RGBA")
        # sticker = self.crop_transparent(sticker)

        siluette = Image.open(siluette_path).convert("RGBA")
        # siluette = self.crop_transparent(siluette)

        # # Ensure both images are the same size
        # if sticker.size != siluette.size:
        #     siluette = siluette.resize(sticker.size)

        # Ensure both images are the same size
        if sticker.size != siluette.size:
            sticker = sticker.resize(siluette.size)

        composited = Image.alpha_composite(sticker, siluette)

        return composited

    def process_composite(self, input_path, output_path):
        """
        Processes the image at input_path, composites the red silhouette on the sticker,
        and saves the result to output_path.
        """
        final_img = self.composite_siluette_on_sticker(input_path)
        final_img.save(output_path, format="PNG", optimize=False, compress_level=0)

def process_sticker(image_path: Path):
    """
    Process the uploaded image and convert it to a sticker format
    Args:
        image_path: Path to the uploaded image
    Returns:
        Path to the processed sticker
    """
    with Image.open(image_path) as img:
        # Add your sticker processing logic here
        # For example: resize, add effects, etc.
        processed = img.copy()
        return image_path


if __name__ == "__main__":
    
    sticker_maker = StickerMaker(
        crop=False,
        alpha_threshold=150,
        border_size=20,
        shadow_blur_strength=0,
        bg_transparent=True,
        padding=20,
        siluette_color=(255, 0, 0, 255),
        siluette_blur_strength=0.4,
        siluette_border_distance=10,
        siluette_border_size=2
    )

    sticker_maker.process(
        input_path="PedeSimon_Caricatura.png",
        output_path="sticker_con_borde.png"
    )
    sticker_maker.process_siluette_with_border(
        input_path="PedeSimon_Caricatura.png",
        output_path="sticker_con_siluette.png"
    )

    sticker_maker.process_composite(
        input_path="PedeSimon_Caricatura.png",
        output_path="sticker_con_siluette_y_borde.png"
    )