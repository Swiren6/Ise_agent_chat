import os

project_path = "./"  # à adapter si tu n'es pas à la racine
output_file = "backendd"

# Extensions à inclure
extensions = [".py", ".json"]

# Fichiers à ignorer
ignored_files = ["__init__.py", output_file]

with open(output_file, "w", encoding="utf-8") as outfile:
    for root, dirs, files in os.walk(project_path):
        for file in files:
            if file in ignored_files:
                continue
            if any(file.endswith(ext) for ext in extensions):
                full_path = os.path.join(root, file)
                outfile.write(f"\n\n# ===== {file} =====\n\n")
                with open(full_path, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read())
