from pymongo import MongoClient
import gridfs

def get_mongo_client(storage_url: str) -> MongoClient:
    client = MongoClient(storage_url)
    return client

def get_gridfs(db_name: str, storage_url: str):
    client = get_mongo_client(storage_url)
    db = client[db_name]
    fs = gridfs.GridFS(db)
    return fs
