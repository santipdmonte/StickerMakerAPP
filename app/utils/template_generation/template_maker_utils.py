from sticker_maker_utils import StickerMaker
from PIL import Image, ImageDraw

stickers = {
    "sticker_8": {
        "path": "to-print/thestickerhouse-logo-textura.png",
        "quantity": 10,
        "border": False
    },
    "sticker_9": {
        "path": "to-print/thestickerhouse-logo.png",
        "quantity": 9,
        "border": False
    },
    "sticker_3": {
        "path": "to-print/lala-iguazu.png",
        "quantity": 2,
        "border": True
    },
    "sticker_11": {
        "path": "to-print/lala-franco.png",
        "quantity": 2,
        "border": True
    },
    "sticker_5": {
        "path": "to-print/mila-ghibli.png",
        "quantity": 2,
        "border": False
    },
    "sticker_6": {
        "path": "to-print/mila-jardin.png",
        "quantity": 2,
        "border": True
    },
    "sticker_7": {
        "path": "to-print/mila-parche-hilo.png",
        "quantity": 2,
        "border": False
    },
    "sticker_10": {
        "path": "to-print/tucalab-logo.png",
        "quantity": 2,
        "border": False
    },
    "sticker_4": {
        "path": "to-print/mila-emoji.png",
        "quantity": 2,
        "border": False
    },
    "sticker_1": {
        "path": "to-print/perros-ghibli.png",
        "quantity": 2,
        "border": False
    }
}

base_template_path = "plantilla-imagenes.png"
base_siluette_path = "plantilla-silutesa-de-corte.png"
save_template_path = "templates-to-print/01-sticker_template.png"
save_siluette_path = "templates-to-print/02-siluette_tempalte.png"
save_template_preview_path = "templates-to-print/03-template_preview.png"
save_tempalte_with_cells_path = "04-template_with_cells.png"

class TemplateMaker:
    def __init__(self, 
        stickers,
        printing_sheet_size = (2828 , 4000), # A3 300 DPI
        columns = 5,
        rows = 7,
        printing_sheet_security_margin = {
            'min_x': 230,
            'max_x': 2650,
            'min_y': 560,
            'max_y': 3800
        }


    ):
        """
        Initializes the TemplateMaker with parameters for border and shadow. \n
        * `sticker`: The sticker image.
        * `printing_sheet_size`: The size of the printing sheet.
        * `columns`: The number of columns in the template.
        * `rows`: The number of rows in the template.
        * `printing_sheet_security_margin`: The security margin of the printing sheet.
        """

        self.stickers = stickers
        self.printing_sheet_size = printing_sheet_size
        self.columns = columns
        self.rows = rows
        self.printing_sheet_security_margin = printing_sheet_security_margin


    def make_template(self, base_template_path=None, save_template_path=None,siluette=False):

        base_template = Image.open(base_template_path).convert("RGBA")

        base_template_width, base_template_height = base_template.size

        # Calculate bounding box from security margin
        min_x = self.printing_sheet_security_margin['min_x']
        max_x = self.printing_sheet_security_margin['max_x']
        min_y = self.printing_sheet_security_margin['min_y']
        max_y = self.printing_sheet_security_margin['max_y']

        grid_width = max_x - min_x
        grid_height = max_y - min_y

        cell_width = grid_width // self.columns
        cell_height = grid_height // self.rows

        current_cell = 0

        for sticker_key in self.stickers:
            sticker_maker = StickerMaker(
                crop=False,
                alpha_threshold=120,
                border_size=20,
                shadow_blur_strength=0,
                bg_transparent=True,
                padding=20,
                siluette_color=(255, 0, 0, 255),
                siluette_blur_strength=0.4,
                siluette_border_distance=10,
                siluette_border_size=2
            )
            
            if siluette:
                sticker_img = sticker_maker.make_siluette(self.stickers[sticker_key]["path"], self.stickers[sticker_key]["border"]).convert("RGBA")
            else:
                if self.stickers[sticker_key]["border"]:
                    sticker_img = sticker_maker.make_sticker(self.stickers[sticker_key]["path"]).convert("RGBA")
                else:
                    # Orginal image
                    sticker_img = Image.open(self.stickers[sticker_key]["path"]).convert("RGBA")
                    sticker_img = sticker_maker._center_on_square(sticker_img, sticker_maker.final_size)

            # Resize sticker to fit inside the new cell size
            sticker_img.thumbnail((int(cell_width), int(cell_height)), Image.LANCZOS)

            for i in range(self.stickers[sticker_key]["quantity"]):
                col = current_cell % self.columns
                row = current_cell // self.columns
                if row >= self.rows:
                    break  # No more space

                x = min_x + col * cell_width + (cell_width - sticker_img.width) // 2
                y = min_y + row * cell_height + (cell_height - sticker_img.height) // 2

                base_template.paste(sticker_img, (x, y), sticker_img)
                current_cell += 1

        base_template.save(save_template_path, optimize=False, compress_level=1)


    def preview_cells_in_template(self, base_template_path=None, save_template_path=None):
        base_template = Image.open(base_template_path).convert("RGBA")
        base_template_width, base_template_height = base_template.size

        # Calculate bounding box from security margin
        margin_xs = [pt[0] for pt in self.printing_sheet_security_margin]
        margin_ys = [pt[1] for pt in self.printing_sheet_security_margin]
        min_x, max_x = min(margin_xs), max(margin_xs)
        min_y, max_y = min(margin_ys), max(margin_ys)

        grid_width = max_x - min_x
        grid_height = max_y - min_y

        cell_width = grid_width // self.columns
        cell_height = grid_height // self.rows

        draw = ImageDraw.Draw(base_template)
        for row in range(self.rows):
            for col in range(self.columns):
                x0 = min_x + col * cell_width
                y0 = min_y + row * cell_height
                x1 = x0 + cell_width
                y1 = y0 + cell_height
                draw.rectangle([x0, y0, x1, y1], outline=(0, 0, 0, 255), width=3)

        base_template.save(save_template_path)

if __name__ == "__main__":

    template_maker = TemplateMaker(
        stickers=stickers
    )
    
    template_maker.make_template(
        base_template_path=base_template_path, 
        save_template_path=save_template_path,
        siluette=False
    )
    
    template_maker.make_template(
        base_template_path=base_siluette_path, 
        save_template_path=save_siluette_path, 
        siluette=True
    )

    template_maker.make_template(
        base_template_path=save_template_path, 
        save_template_path=save_template_preview_path, 
        siluette=True
    )

    # template_maker.preview_cells_in_template(
    #     base_template_path=base_template_path,
    #     save_template_path=save_tempalte_with_cells_path
    # )

