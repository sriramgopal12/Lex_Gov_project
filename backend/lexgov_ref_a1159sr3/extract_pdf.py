import fitz

pdf_path = "data/raw/it_act_2000.pdf"
output_path = "data/processed/it_act_raw.txt"

print("Starting extraction...")
print("Opening:", pdf_path)

doc = fitz.open(pdf_path)
print("Total pages found:", len(doc))

full_text = ""

for page in doc:
    full_text += page.get_text()

print("Writing to:", output_path)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(full_text)

print("Extraction complete.")