import os

from azure.core import exceptions
from dotenv import load_dotenv
from lib.azure import authenticate_by_access_key, upload_to_azure_blob
from lib.file_handling import fetch_content_from_url, extract_io_zip_to_folder

load_dotenv()


def main():
    container_name = os.environ["container_name"]
    account_name = os.environ["account_name"]
    key = os.environ["key"]
    source_url = os.environ["source_url"]
    service_client = authenticate_by_access_key(account_name, key)

    try:
        service_client.create_container(container_name)
        print(f"Created Azure Blob container: {container_name}")
    except exceptions.ResourceExistsError:
        print(f"Using existing Azure Blob container: {container_name}")

    content = fetch_content_from_url(source_url)
    #extract_io_zip_to_folder(content)
    
    #upload_to_azure_blob("extracted_files", service_client, container_name)

if __name__ == "__main__":
    main()
