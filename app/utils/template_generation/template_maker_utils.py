from sticker_maker_utils import StickerMaker
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF
from stickers_config import stickers

base_template_path = "plantilla-imagenes.png"
base_silhouette_path = "plantilla-siluetas.png"
save_template_path = "templates/01-sticker_template.png"
save_silhouette_path = "templates/02-silhouette_tempalte.pdf"
save_template_preview_path = "templates/03-template_preview.pdf"
save_tempalte_with_cells_path = "templates/04-template_with_cells.png"

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

    def _generate_grid_positions(self):
        """
        Common function to calculate grid positions based on security margins.
        Returns a dictionary with grid parameters.
        """
        # Calculate bounding box from security margin
        min_x = self.printing_sheet_security_margin['min_x']
        max_x = self.printing_sheet_security_margin['max_x']
        min_y = self.printing_sheet_security_margin['min_y']
        max_y = self.printing_sheet_security_margin['max_y']

        grid_width = max_x - min_x
        grid_height = max_y - min_y

        cell_width = grid_width // self.columns
        cell_height = grid_height // self.rows

        return {
            'min_x': min_x,
            'max_x': max_x,
            'min_y': min_y,
            'max_y': max_y,
            'grid_width': grid_width,
            'grid_height': grid_height,
            'cell_width': cell_width,
            'cell_height': cell_height
        }

    def make_sticker_template(self, base_template_path=None, save_template_path=None):

        base_template = Image.open(base_template_path).convert("RGBA")

        # Get grid parameters
        grid = self._generate_grid_positions()
        min_x = grid['min_x']
        min_y = grid['min_y']
        cell_width = grid['cell_width']
        cell_height = grid['cell_height']

        current_cell = 0

        for sticker_key in self.stickers:
            sticker_maker = StickerMaker(
                crop=False,
                alpha_threshold=120,
                border_size=20,
                shadow_blur_strength=0,
                bg_transparent=True,
                padding=20,
                silhouette_color=(255, 0, 0, 255),
                silhouette_blur_strength=0.4,
                silhouette_border_distance=10,
                silhouette_border_size=2
            )
            

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

        if save_template_path:
            base_template.save(save_template_path, optimize=False, compress_level=1)
        return base_template

    def make_silhouette_template(self, base_template_path=None, save_template_path=None):

        # Dimensions for the final PDF (we will use the pixel dimensions directly
        # as PDF points for simplicity)
        sheet_width, sheet_height = self.printing_sheet_size

        # 1. Create a PDF canvas 
        c = canvas.Canvas(save_template_path, pagesize=(sheet_width, sheet_height))

        if base_template_path:
            # Draw the base template (grid or background) as a raster image
            # so the operator has visual reference while keeping silhouettes vector.
            c.drawImage(base_template_path, 0, 0, width=sheet_width, height=sheet_height)

        # Get grid parameters
        grid = self._generate_grid_positions()
        min_x = grid['min_x']
        min_y = grid['min_y']
        cell_width = grid['cell_width']
        cell_height = grid['cell_height']

        current_cell = 0

        for sticker_key in self.stickers:
            sticker_maker = StickerMaker(
                crop=False,
                alpha_threshold=120,
                border_size=20,
                shadow_blur_strength=0,
                bg_transparent=True,
                padding=20,
                silhouette_color=(255, 0, 0, 255),
                silhouette_blur_strength=0.4,
                silhouette_border_distance=10,
                silhouette_border_size=2
            )

            # Generate the vector silhouette (Drawing object)
            drawing = sticker_maker.make_vector_silhouette(
                input_image_path=self.stickers[sticker_key]["path"], 
                border=self.stickers[sticker_key]["border"],
                output_pdf_path=None
            )


            if drawing is None:
                # Skip any sticker that failed vectorisation
                continue

            # Scale the silhouette once to fit inside a cell
            d_width, d_height = drawing.width, drawing.height
            scale_factor = min(cell_width / d_width, cell_height / d_height)

            for _ in range(self.stickers[sticker_key]["quantity"]):
                col = current_cell % self.columns
                row = current_cell // self.columns
                if row >= self.rows:
                    break  # No more space on the sheet

                # Compute position so silhouette is centred inside the cell
                scaled_w = d_width * scale_factor
                scaled_h = d_height * scale_factor

                # Calculate position exactly as in make_template
                x = min_x + col * cell_width + (cell_width - scaled_w) // 2
                # Adjust y-coordinate for PDF (origin is bottom-left in PDF)
                y = sheet_height - (min_y + row * cell_height + (cell_height - scaled_h) // 2 + scaled_h)

                # Draw the vector silhouette on the PDF canvas
                c.saveState()
                c.translate(x, y)
                c.scale(scale_factor, scale_factor)
                renderPDF.draw(drawing, c, 0, 0)
                c.restoreState()

                current_cell += 1

        # Finalise the PDF
        if save_template_path:
            c.save()
        return c


    def preview_cells_in_template(self, base_template_path=None, save_template_path=None):
        base_template = Image.open(base_template_path).convert("RGBA")

        # Get grid parameters
        grid = self._generate_grid_positions()
        min_x = grid['min_x']
        min_y = grid['min_y']
        cell_width = grid['cell_width']
        cell_height = grid['cell_height']

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


    # Make sticker template
    template_maker.make_sticker_template(
        base_template_path=base_template_path, 
        save_template_path=save_template_path
    )

    # Make silhouette template
    template_maker.make_silhouette_template(
        base_template_path=base_silhouette_path, 
        save_template_path=save_silhouette_path
    )

    # Make Preview of the template
    template_maker.make_silhouette_template(
        base_template_path=save_template_path,
        save_template_path=save_template_preview_path,
    )

    # Make Preview of the template with cells
    template_maker.preview_cells_in_template(
        base_template_path=base_template_path,
        save_template_path=save_tempalte_with_cells_path
    )

