import io
from minio import Minio
from minio.error import S3Error
from config import settings

client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)


def ensure_buckets():
    for bucket in (settings.minio_raw_bucket, settings.minio_markdown_bucket):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def put_raw(doc_id: str, filename: str, data: bytes, content_type: str | None) -> str:
    key = f"{doc_id}/{filename}"
    client.put_object(
        settings.minio_raw_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type or "application/octet-stream",
    )
    return key


def put_markdown(doc_id: str, filename: str, markdown: str) -> str:
    base = filename.rsplit(".", 1)[0] or filename
    key = f"{doc_id}/{base}.md"
    payload = markdown.encode("utf-8")
    client.put_object(
        settings.minio_markdown_bucket,
        key,
        io.BytesIO(payload),
        length=len(payload),
        content_type="text/markdown",
    )
    return key


def get_raw(object_key: str) -> bytes:
    resp = client.get_object(settings.minio_raw_bucket, object_key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def get_markdown(doc_id: str) -> str:
    for obj in client.list_objects(settings.minio_markdown_bucket, prefix=f"{doc_id}/", recursive=True):
        if obj.object_name.endswith(".md"):
            resp = client.get_object(settings.minio_markdown_bucket, obj.object_name)
            try:
                return resp.read().decode("utf-8")
            finally:
                resp.close()
                resp.release_conn()
    raise FileNotFoundError(f"markdown for {doc_id}")


def _delete_prefix(bucket: str, prefix: str):
    try:
        for obj in client.list_objects(bucket, prefix=prefix, recursive=True):
            client.remove_object(bucket, obj.object_name)
    except S3Error:
        pass


def delete_raw(doc_id: str):
    _delete_prefix(settings.minio_raw_bucket, f"{doc_id}/")


def delete_markdown(doc_id: str):
    _delete_prefix(settings.minio_markdown_bucket, f"{doc_id}/")


def delete_doc(doc_id: str):
    delete_raw(doc_id)
    delete_markdown(doc_id)
