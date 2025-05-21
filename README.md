# 🖼️ TheStcikerHouse

**TheStcikerHouse** es una aplicación que convierte descripciones de texto o imágenes en stickers listos para imprimir. Ya sea que el usuario describa lo que quiere o suba una imagen, la app genera automáticamente una plantilla de sticker que se puede personalizar, descargar e imprimir.

![image](https://github.com/user-attachments/assets/05d7886c-6d9e-477d-9bda-563bf0715be8)


## ✨ Características

- 🧠 Generación de stickers basada en texto (prompts)
- 🖼️ Soporte para imágenes de entrada
- 🎨 Plantillas automáticas optimizadas para impresión
- 📥 Exportación en formatos listos para imprimir (PNG, PDF)
- 🛠️ Interfaz intuitiva para previsualizar y ajustar el diseño
- ☁️ Almacenamiento en AWS S3 para guardar imágenes y plantillas
- 📧 Envío de enlaces de descarga por correo electrónico

## 🚀 ¿Cómo funciona?

1. **Ingresa un prompt**: Describe el sticker que deseas (ej. "un gato astronauta kawaii").
2. **Sube una imagen** *(opcional)*: Puedes usar una imagen como base.
3. **Generación automática**: La app crea un diseño basado en la descripción o imagen.
4. **Ajusta y descarga**: Visualiza la plantilla, realiza ajustes y descarga tu sticker.

## 🔧 Configuración de AWS S3

Para utilizar el almacenamiento en AWS S3:

1. Crea un bucket de S3 en tu cuenta de AWS
2. Configura las siguientes variables de entorno:
   - `AWS_ACCESS_KEY_ID`: Tu clave de acceso de AWS
   - `AWS_SECRET_ACCESS_KEY`: Tu clave secreta de AWS
   - `AWS_REGION`: La región del bucket (por defecto: us-east-1)
   - `AWS_S3_BUCKET_NAME`: Nombre de tu bucket de S3
   - `USE_S3`: Establece en "True" para habilitar S3 o "False" para usar sólo almacenamiento local

## 📩 Envío de Correos Electrónicos

La aplicación ahora envía enlaces de descarga a través de correo electrónico en lugar de adjuntar los archivos directamente, lo que reduce el tamaño del correo y mejora la experiencia del usuario.

Configura las siguientes variables para el servidor SMTP:
- `SMTP_SERVER`: Servidor SMTP para envío de correos
- `SMTP_PORT`: Puerto del servidor SMTP
- `SMTP_USER`: Usuario del servidor SMTP
- `SMTP_PASSWORD`: Contraseña del servidor SMTP
