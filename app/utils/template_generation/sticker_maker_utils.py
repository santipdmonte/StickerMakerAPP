from PIL import Image, ImageFilter, ImageChops
from pathlib import Path
import cv2
import numpy as np
import os
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Path
from reportlab.lib.colors import red

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
        silhouette_color=(255, 0, 0, 255),
        silhouette_blur_strength=1.5,
        silhouette_border_size=3,
        silhouette_border_distance=3,
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
        * `silhouette_color`: The color of the silhouette.
        * `silhouette_blur_strength`: The strength of the blur applied to the silhouette.
        * `silhouette_border_size`: The size of the border around the silhouette.
        * `silhouette_border_distance`: The distance between the border and the silhouette.
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
        self.silhouette_color = silhouette_color
        self.silhouette_blur_strength = silhouette_blur_strength
        self.silhouette_border_size = silhouette_border_size
        self.silhouette_border_distance = silhouette_border_distance
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
            background = Image.new("RGBA", (final_size + 20, final_size + 20), (0, 0, 0, 0))
        else:
            background = Image.new("RGBA", (final_size + 20, final_size + 20), self.bg_color)
        # Calculate top-left position to paste the image centered
        x = (final_size - img.width) // 2
        y = (final_size - img.height) // 2
        background.paste(img, (x, y), img)
        return background


    def make_sticker(self, input_image_path, output_image_path=None):
        """
        Creates a sticker from the image at `image_path` by adding a border and shadow.\n
        Returns the final image.
        """

        img = Image.open(input_image_path).convert("RGBA")

        if self.crop:
            img = self.crop_transparent(img)

        img = self._center_on_square(img, self.final_size)

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

            if output_image_path:
                black_bg.save(output_image_path, format="PNG", optimize=False, compress_level=0)

            return black_bg

        if output_image_path:
            final.save(output_image_path, format="PNG", optimize=False, compress_level=0)

        return final

    def make_silhouette(self, input_image_path, border = True, output_image_path=None):
        """
        Creates a sticker silhouette to cut the sticker.
        Returns the final image.
        """

        img = Image.open(input_image_path).convert("RGBA")

        if self.crop:
            img = self.crop_transparent(img)

        img = self._center_on_square(img, self.final_size)

        if border:

            alpha = img.getchannel("A")
            mask = alpha.point(lambda p: 255 if p > self.alpha_threshold else 0)

            dilated = mask.filter(ImageFilter.MaxFilter(self.silhouette_border_distance * 2 + 1))
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

        dilated = mask.filter(ImageFilter.MaxFilter(self.silhouette_border_size * 2 + 1))
        border_mask = ImageChops.subtract(dilated, mask)
        border_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=self.silhouette_blur_strength))

        red_silhouette = Image.new("RGBA", img.size, self.silhouette_color) 
        red_silhouette.putalpha(border_mask)

        if output_image_path:
            red_silhouette.save(output_image_path, format="PNG", optimize=False, compress_level=0)

        return red_silhouette
    
    def make_vector_silhouette(self, input_image_path, border = True, output_pdf_path=None):
        """
        Creates a vector silhouette from the image at `image_path`.
        Returns the final image.
        """
        epsilon = 0.0005
        
        print(f"🚀 Vectorizing silhouette from {input_image_path}...")
        
        # PASO 1: Centrar la imagen y Cargar imagen original
        img = Image.open(input_image_path).convert("RGBA")

        if self.crop:
            img = self.crop_transparent(img)

        img = self._center_on_square(img, self.final_size)

        if border:

            alpha = img.getchannel("A")
            mask = alpha.point(lambda p: 255 if p > self.alpha_threshold else 0)

            dilated = mask.filter(ImageFilter.MaxFilter(self.silhouette_border_distance * 2 + 1))
            border_mask = ImageChops.subtract(dilated, mask)
            border_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

            # White border layer
            white_border_layer = Image.new("RGBA", img.size, (255, 255, 255, 255))  # White
            white_border_layer.putalpha(border_mask)

            # Combine the layers: First white border, then shadow, then image
            img = Image.alpha_composite(white_border_layer, img)

        img.save("temp_image.png", format="PNG", optimize=False, compress_level=0)

        image = cv2.imread("temp_image.png", cv2.IMREAD_UNCHANGED)

        
        # PASO 2: Convertir a escala de grises
        if len(image.shape) == 3:
            if image.shape[2] == 4:  # RGBA
                # Usar canal alpha
                gray = image[:, :, 3]
            else:  # RGB
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        
        # PASO 3: Aplicar filtro gaussiano para suavizar
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # PASO 4: Binarizar con threshold
        _, thresh = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY)
        
        # PASO 5: Aplicar operaciones morfológicas para limpiar
        kernel = np.ones((3,3), np.uint8)
        
        # Cerrar huecos pequeños
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Eliminar ruido pequeño
        cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
        
        # PASO 6: Encontrar contornos
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        
        # Visualizar todos los contornos
        contour_img = np.zeros_like(cleaned)
        contour_img = cv2.cvtColor(contour_img, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)  # Verde
        
        # PASO 7: Filtrar y obtener solo el contorno principal
        if not contours:
            print("❌ No se encontraron contornos")
            return
        
        # Obtener el contorno más grande (silueta principal)
        main_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(main_contour)
        
        # Visualizar solo el contorno principal
        main_contour_img = np.zeros_like(cleaned)
        main_contour_img = cv2.cvtColor(main_contour_img, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(main_contour_img, [main_contour], -1, (255, 0, 0), 2)  # Azul
        
        # PASO 8: Suavizar el contorno principal (ÓPTIMO)
        # Usar epsilon 0.0001 - balance perfecto entre detalle y eficiencia
        epsilon_optimal = epsilon * cv2.arcLength(main_contour, True)  # Valor óptimo elegido
        smoothed_contour = cv2.approxPolyDP(main_contour, epsilon_optimal, True)
        
        # Crear imagen comparativa - original vs suavizado
        comparison_img = np.zeros_like(cleaned)
        comparison_img = cv2.cvtColor(comparison_img, cv2.COLOR_GRAY2BGR)
        
        # Dibujar contorno original en azul (más transparente)
        cv2.drawContours(comparison_img, [main_contour], -1, (255, 100, 100), 1)  # Azul claro
        
        # Dibujar contorno suavizado en rojo (más prominente)
        cv2.drawContours(comparison_img, [smoothed_contour], -1, (0, 0, 255), 2)  # Rojo
        
        # Agregar puntos para visualizar los vértices del suavizado
        for point in smoothed_contour:
            cv2.circle(comparison_img, tuple(point[0]), 3, (255, 255, 0), -1)  # Círculos amarillos
        
        
        # PASO 8C: Probar también una versión SIN suavizado (contorno completo)
        no_smooth_img = np.zeros_like(cleaned)
        no_smooth_img = cv2.cvtColor(no_smooth_img, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(no_smooth_img, [main_contour], -1, (0, 255, 0), 1)  # Verde para diferenciarlo
        
        # Solo marcar cada 20º punto para no saturar la imagen
        for i in range(0, len(main_contour), 20):
            point = main_contour[i][0]
            cv2.circle(no_smooth_img, tuple(point), 1, (255, 255, 0), -1)
            
        # PASO 9: Crear PDF vectorial
        height, width = cleaned.shape
        d = Drawing(width, height)
        
        # Crear path vectorial con curvas Bézier suaves
        if len(smoothed_contour) >= 3:
            points = smoothed_contour.reshape(-1, 2)
            
            vector_path = Path(
                fillColor=None,          # Sin relleno, solo contorno
                strokeColor=red,
                strokeWidth=3
            )
            
            # Mover al primer punto
            start_point = points[0]
            vector_path.moveTo(start_point[0], height - start_point[1])
            
            # Crear curvas suaves usando curvas Bézier cúbicas
            for i in range(1, len(points)):
                curr_point = points[i]
                prev_point = points[i-1]
                
                if i < len(points) - 1:
                    next_point = points[i+1]
                    
                    # Calcular puntos de control para curva suave
                    # Control point 1: en dirección del punto anterior
                    cp1_x = prev_point[0] + 0.25 * (curr_point[0] - prev_point[0])
                    cp1_y = prev_point[1] + 0.25 * (curr_point[1] - prev_point[1])
                    
                    # Control point 2: en dirección del punto siguiente  
                    cp2_x = curr_point[0] - 0.25 * (next_point[0] - curr_point[0])
                    cp2_y = curr_point[1] - 0.25 * (next_point[1] - curr_point[1])
                    
                    # Curva cúbica Bézier
                    vector_path.curveTo(
                        cp1_x, height - cp1_y,     # Control point 1
                        cp2_x, height - cp2_y,     # Control point 2  
                        curr_point[0], height - curr_point[1]  # End point
                    )
                else:
                    # Conectar con el punto inicial para cerrar
                    vector_path.lineTo(curr_point[0], height - curr_point[1])
            
            # Cerrar el path conectando con el primer punto
            vector_path.closePath()
            d.add(vector_path)
        
            # PASO 10: Guardar PDF final
            if output_pdf_path:
                renderPDF.drawToFile(d, output_pdf_path)
            return d

    def make_vector_silhouette_test(self, input_image_path, border=True, output_folder=None):
        """
        Creates a vector silhouette from the image at `image_path`.
        Returns the final image.
        """
        epsilon = 0.0005
        
        print(f"🚀 Vectorizing silhouette from {input_image_path}...")
        # Prepare output folder
        if output_folder is None:
            output_folder = os.path.join(os.path.dirname(input_image_path), "vector_debug")
        os.makedirs(output_folder, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(input_image_path))[0]
        
        # PASO 1: Centrar la imagen y Cargar imagen original
        img = Image.open(input_image_path).convert("RGBA")

        if self.crop:
            img = self.crop_transparent(img)

        img = self._center_on_square(img, self.final_size)

        if border:

            alpha = img.getchannel("A")
            mask = alpha.point(lambda p: 255 if p > self.alpha_threshold else 0)

            dilated = mask.filter(ImageFilter.MaxFilter(self.silhouette_border_distance * 2 + 1))
            border_mask = ImageChops.subtract(dilated, mask)
            border_mask = border_mask.filter(ImageFilter.GaussianBlur(radius=1.5))

            # White border layer
            white_border_layer = Image.new("RGBA", img.size, (255, 255, 255, 255))  # White
            white_border_layer.putalpha(border_mask)

            # Combine the layers: First white border, then shadow, then image
            img = Image.alpha_composite(white_border_layer, img)

        # Save step 0: RGBA
        step0_path = os.path.join(output_folder, f"{base_name}_step0_rgba.png")
        img.save(step0_path, format="PNG", optimize=False, compress_level=0)

        image = cv2.imread(step0_path, cv2.IMREAD_UNCHANGED)

        
        # PASO 2: Convertir a escala de grises
        if len(image.shape) == 3:
            if image.shape[2] == 4:  # RGBA
                # Usar canal alpha
                gray = image[:, :, 3]
            else:  # RGB
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        
        # PASO 3: Aplicar filtro gaussiano para suavizar
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Save step 1: Blurred
        step1_path = os.path.join(output_folder, f"{base_name}_step1_blur.png")
        cv2.imwrite(step1_path, blurred)
        
        # PASO 4: Binarizar con threshold
        _, thresh = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY)
        
        # Save step 2: Threshold
        step2_path = os.path.join(output_folder, f"{base_name}_step2_thresh.png")
        cv2.imwrite(step2_path, thresh)
        
        # PASO 5: Aplicar operaciones morfológicas para limpiar
        kernel = np.ones((3,3), np.uint8)
        
        # Cerrar huecos pequeños
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # Save step 3: Closed
        step3_path = os.path.join(output_folder, f"{base_name}_step3_closed.png")
        cv2.imwrite(step3_path, closed)
        
        # Eliminar ruido pequeño
        cleaned = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
        
        # Save step 4: Cleaned
        step4_path = os.path.join(output_folder, f"{base_name}_step4_cleaned.png")
        cv2.imwrite(step4_path, cleaned)
        
        # PASO 6: Encontrar contornos
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        
        # Visualizar todos los contornos
        contour_img = np.zeros_like(cleaned)
        contour_img = cv2.cvtColor(contour_img, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(contour_img, contours, -1, (0, 255, 0), 2)  # Verde
        
        # Save step 5: All contours
        step5_path = os.path.join(output_folder, f"{base_name}_step5_all_contours.png")
        cv2.imwrite(step5_path, contour_img)
        
        # PASO 7: Filtrar y obtener solo el contorno principal
        if not contours:
            print("❌ No se encontraron contornos")
            return
        
        # Obtener el contorno más grande (silueta principal)
        main_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(main_contour)
        
        # Visualizar solo el contorno principal
        main_contour_img = np.zeros_like(cleaned)
        main_contour_img = cv2.cvtColor(main_contour_img, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(main_contour_img, [main_contour], -1, (255, 0, 0), 2)  # Azul
        
        # Save step 6: Main contour
        step6_path = os.path.join(output_folder, f"{base_name}_step6_main_contour.png")
        cv2.imwrite(step6_path, main_contour_img)
        
        # PASO 8: Suavizar el contorno principal (ÓPTIMO)
        # Usar epsilon 0.0001 - balance perfecto entre detalle y eficiencia
        epsilon_optimal = epsilon * cv2.arcLength(main_contour, True)  # Valor óptimo elegido
        smoothed_contour = cv2.approxPolyDP(main_contour, epsilon_optimal, True)
        
        # Crear imagen comparativa - original vs suavizado
        comparison_img = np.zeros_like(cleaned)
        comparison_img = cv2.cvtColor(comparison_img, cv2.COLOR_GRAY2BGR)
        
        # Dibujar contorno original en azul (más transparente)
        cv2.drawContours(comparison_img, [main_contour], -1, (255, 100, 100), 1)  # Azul claro
        
        # Dibujar contorno suavizado en rojo (más prominente)
        cv2.drawContours(comparison_img, [smoothed_contour], -1, (0, 0, 255), 2)  # Rojo
        
        # Save step 7: Comparison
        step7_path = os.path.join(output_folder, f"{base_name}_step7_compare.png")
        cv2.imwrite(step7_path, comparison_img)
        
        # PASO 8C: Probar también una versión SIN suavizado (contorno completo)
        no_smooth_img = np.zeros_like(cleaned)
        no_smooth_img = cv2.cvtColor(no_smooth_img, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(no_smooth_img, [main_contour], -1, (0, 255, 0), 1)  # Verde para diferenciarlo
        
        # Save step 8: Full contour
        step8_path = os.path.join(output_folder, f"{base_name}_step8_full_contour.png")
        cv2.imwrite(step8_path, no_smooth_img)
        
        # PASO 9: Crear PDF vectorial
        height, width = cleaned.shape
        d = Drawing(width, height)
        
        # Crear path vectorial con curvas Bézier suaves
        if len(smoothed_contour) >= 3:
            points = smoothed_contour.reshape(-1, 2)
            
            vector_path = Path(
                fillColor=None,          # Sin relleno, solo contorno
                strokeColor=red,
                strokeWidth=3
            )
            # Move to first point
            start = beziers[0][0]
            vector_path.moveTo(start[0], height - start[1])
            # Draw all Bézier segments
            for bp0, bp1, bp2, bp3 in beziers:
                vector_path.curveTo(
                    bp1[0], height - bp1[1],
                    bp2[0], height - bp2[1],
                    bp3[0], height - bp3[1]
                )
            vector_path.closePath()
            d.add(vector_path)
        
            # PASO 10: Guardar PDF final
            if output_folder:
                pdf_path = os.path.join(output_folder, f"{base_name}_vector.pdf")
                renderPDF.drawToFile(d, pdf_path)
                print(f"  • Saved final vector PDF → {pdf_path}")
            return d    

    def composite_silhouette_on_sticker(self, input_sticker_path, input_silhouette_path, output_image_path=None):
        """
        Composites the red silhouette on top of the sticker.
        Returns the final composited image.
        """
        sticker = Image.open(input_sticker_path).convert("RGBA")

        silhouette = Image.open(input_silhouette_path).convert("RGBA")

        # Ensure both images are the same size
        if sticker.size != silhouette.size:
            sticker = sticker.resize(silhouette.size)

        composited = Image.alpha_composite(sticker, silhouette)

        if output_image_path:
            composited.save(output_image_path, format="PNG", optimize=False, compress_level=0)

        return composited

if __name__ == "__main__":
    
    sticker_maker = StickerMaker(
        crop=True,
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

    # sticker_maker.make_vector_silhouette(
    #     input_image_path="base_images/lala-franco.png",
    #     border=True,
    #     output_pdf_path="borders_stickers/test.pdf"
    # )


    # sticker_maker.make_sticker(
    #     input_image_path="base_images/image1.png",
    #     output_image_path="borders_stickers/image1.1_borde.png"
    # )

    # sticker_maker.process_silhouette_with_border(
    #     input_path="base_images/lala-franco.png",
    #     output_path="borders_stickers/lala-franco_silhouette.png"
    # )

    # sticker_maker.process_composite(
    #     input_path="to-print/sticker_con_borde.png",
    #     output_path="border_stickers/lala-franco_silhouette_y_borde.png"
    # )