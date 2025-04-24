# Sticker Maker App

A minimalistic web application for creating beautiful stickers using OpenAI's image generation capabilities.

## Features

- Clean, aesthetic user interface with Poppins font and modern design
- Generate custom stickers from text descriptions
- Upload reference images to guide the sticker creation process
- Select quality settings (low, medium, high)
- Download stickers as PNG files with transparent backgrounds
- Responsive design for mobile and desktop

## Prerequisites

- Python 3.7 or higher
- OpenAI API key

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd StickerMakerAPP
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your OpenAI API key as an environment variable:
   ```
   # Windows (PowerShell)
   $env:OPENAI_API_KEY = "your-api-key"
   
   # Windows (CMD)
   set OPENAI_API_KEY=your-api-key
   
   # macOS/Linux
   export OPENAI_API_KEY="your-api-key"
   ```

## Usage

1. Start the application:
   ```
   python app/app.py
   ```

2. Open a web browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

3. Choose between Simple Mode and Reference Image Mode:
   - **Simple Mode**: Enter a description for your sticker in the text area
   - **Reference Image Mode**: Upload an image and provide instructions for how to transform it

4. Select quality level (low, medium, high)

5. Click "Generate Sticker" or press Ctrl+Enter

6. Once the sticker is generated, download it by clicking the "Download Sticker" button

## Tips for Better Stickers

- Always include "on a transparent background" in your prompt for best results
- Be specific about colors, styles, and elements you want in the sticker
- Try descriptive style terms like "minimalist", "cartoon", "watercolor", or "flat design"
- When using reference images, clearly explain what you want to keep or change

## Technical Details

- Built with Flask web framework
- Uses OpenAI's `gpt-image-1` model for image generation
- Pillow (PIL) for image processing
- Client-side JavaScript with no external frameworks

## License

MIT 