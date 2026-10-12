import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

def authenticate_azure_blob_by_default_credential(connection_string: str) -> BlobServiceClient:
    default_credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(connection_string, credential=default_credential)
    return blob_service_client

def authenticate_by_access_key(account_name: str, access_key: str) -> BlobServiceClient:
    """
    Initializes a client using the storage account name and access key.
    """
    account_url = f"https://{account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=access_key)

def upload_to_azure_blob(local_tmp_directory:str, blob_service_client, container_name):
    for file in os.listdir(local_tmp_directory):
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=file)
        with open(file=local_tmp_directory+"/"+file, mode="rb") as data:
            blob_client.upload_blob(data, overwrite=True)

