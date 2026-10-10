import requests
import io
from datetime import datetime
from pathlib import Path
import shutil
import zipfile

def rename_with_current_timestamp(original_name: str) -> str:
    # Example: prefix files or strip existing subdirectories

    now = datetime.now()
    current_time_str = now.strftime("%Y-%m-%d_%H-%M-%S")
    filename = Path(original_name).name
    return f"{current_time_str}_{filename}"

def fetch_content_from_url(url:str) -> io.BytesIO:
    response = requests.get(url)
    response.raise_for_status()
    return io.BytesIO(response.content)

def extract_io_zip_to_folder(
    content: io.BytesIO, output_dir: str = "./extracted_files"
) -> None:
    dest = Path(output_dir)
    with zipfile.ZipFile(content) as z:
        if len(z.namelist()) > 1:
            raise ValueError("Zip archive includes more then one file")
        for member in z.infolist():
            # Skip directory entries
            if member.is_dir():
                continue

            new_filename = rename_with_current_timestamp(member.filename)
            target_path = dest / new_filename
 
            # Ensure parent directories exist
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with z.open(member) as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)