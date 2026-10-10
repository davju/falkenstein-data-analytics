import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

def authenticate_azure_blob(connection_string: str) -> BlobServiceClient:
    default_credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(connection_string, credential=default_credential)
    return blob_service_client

def upload_to_azure_blob(local_tmp_directory:str, blob_service_client, container_name):
    for file in os.listdir(local_tmp_directory):
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=file)
        with open(file=local_tmp_directory+"/"+file, mode="rb") as data:
            blob_client.upload_blob(data, overwrite=True)

