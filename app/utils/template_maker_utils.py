from sticker_maker_utils import StickerMaker
from PIL import Image, ImageDraw

stickers = {
    "sticker_1": {
        "path": "image1.png",
        "quantity": 10
    },
    "sticker_2": {
        "path": "image5.png",
        "quantity": 5
    },
    "sticker_3": {
        "path": "PedeSimon_Caricatura.png",
        "quantity": 20
    },
}

base_template_path = "plantilla-imagenes-1.png"
base_siluette_path = "plantilla-silutesa-de-corte-1.png"
save_template_path = "sticker_template.png"
save_siluette_path = "siluette_tempalte.png"
save_tempalte_with_cells_path = "template_with_cells.png"
save_template_preview_path = "template_preview.png"

class TemplateMaker:
    def __init__(self, 
        # base_template_path,
        # base_siluette_path,
        # save_template_path,
        # save_siluette_path,
        stickers,
        printing_sheet_size = 1448  * 2048 , # 17400088
        columns = 5,
        rows = 7,
        printing_sheet_security_margin = [
            (1550, 310),  # top-right
            (130, 310),  # top-left
            (130, 2220),  # bottom-left
            (1550, 2220)  # bottom-right
        ]


    ):
        """
        Initializes the TemplateMaker with parameters for border and shadow. \n
        * `base_template_path`: The path to the base template image.
        * `base_siluette_path`: The path to the base siluette image.
        * `save_template_path`: The path to save the template image.
        * `save_siluette_path`: The path to save the siluette image.
        * `sticker`: The sticker image.
        * `printing_sheet_size`: The size of the printing sheet.
        * `columns`: The number of columns in the template.
        * `rows`: The number of rows in the template.
        * `printing_sheet_security_margin`: The security margin of the printing sheet.
        """

        # self.base_template_path = base_template_path
        # self.base_siluette_path = base_siluette_path
        # self.save_template_path = save_template_path
        # self.save_siluette_path = save_siluette_path
        self.stickers = stickers
        self.printing_sheet_size = printing_sheet_size
        self.columns = columns
        self.rows = rows
        self.printing_sheet_security_margin = printing_sheet_security_margin


    def make_template(self, base_template_path=None, save_template_path=None,siluette=False):

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

        current_cell = 0

        for sticker_key in self.stickers:
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
            
            if siluette:
                sticker_img = sticker_maker.make_siluette_with_border(self.stickers[sticker_key]["path"]).convert("RGBA")
            else:
                sticker_img = sticker_maker.make_sticker(self.stickers[sticker_key]["path"]).convert("RGBA")

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

        base_template.save(save_template_path)


    def preview_cells_in_template(self):
        base_template = Image.open(self.base_template_path).convert("RGBA")
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

        base_template.save("template_with_cells.png")

if __name__ == "__main__":

    template_maker = TemplateMaker(
        stickers=stickers
    )
    
    # template_maker.make_template(
    #     base_template_path=base_template_path, 
    #     save_template_path=save_template_path,
    #     siluette=False
    # )
    
    # template_maker.make_template(
    #     base_template_path=base_siluette_path, 
    #     save_template_path=save_siluette_path, 
    #     siluette=True
    # )

    template_maker.make_template(
        base_template_path=save_template_path, 
        save_template_path=save_template_preview_path, 
        siluette=True
    )

    # template_maker.print_cells_in_template()

