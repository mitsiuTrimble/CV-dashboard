import os
from pathlib import Path
from pdf2image import convert_from_path

# Paths
pdf_dir = Path("plots")
output_dir = Path("plots_previews")
output_dir.mkdir(exist_ok=True)

# Convert each PDF
for pdf_file in pdf_dir.glob("*.pdf"):
    try:
        images = convert_from_path(str(pdf_file), dpi=150, first_page=1, last_page=1)
        if images:
            output_path = output_dir / (pdf_file.name + ".png")
            images[0].save(output_path, "PNG")
            print(f"Converted: {pdf_file.name} → {output_path.name}")
        else:
            print(f"⚠️ No images extracted from {pdf_file.name}")
    except Exception as e:
        print(f"❌ Failed to convert {pdf_file.name}: {e}")
