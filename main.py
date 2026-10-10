import os

from azure.core import exceptions
from dotenv import load_dotenv
from lib.azure import authenticate_azure_blob, upload_to_azure_blob
from lib.file_handling import fetch_content_from_url, extract_io_zip_to_folder

load_dotenv()


def main():
    blob_name = os.environ["blob_name"]
    container_name = os.environ["container_name"]
    service_client = authenticate_azure_blob(f"https://{blob_name}.blob.core.windows.net")

    try:
        service_client.create_container(container_name)
        print(f"Created Azure Blob container: {container_name}")
    except exceptions.ResourceExistsError:
        print(f"Using existing Azure Blob container: {container_name}")

    content = fetch_content_from_url("https://drive.google.com/uc?id=1yyL20BNKv3PxJRJVjJ_2Q-HidvIUis45&export=download")
    extract_io_zip_to_folder(content)

    upload_to_azure_blob("extracted_files", service_client, container_name)

if __name__ == "__main__":
    main()
