import asyncio
from urllib.parse import urlparse
import boto3 
import functools
import io
import json
import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

client = boto3.client('bedrock-runtime', region_name='us-east-1')
rekognition = boto3.client('rekognition', region_name='us-east-1')

def check_frames_safety(frames):
    """
    Check if the frame is safe for processing.
    """
    logger.info("Checking frames safety...")
    for i, frame in enumerate(frames):
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        frame_bytes = buf.getvalue()
        response = rekognition.detect_moderation_labels(
            Image={"Bytes": frame_bytes}
        )
        labels = response.get("ModerationLabels", [])
        if labels:
            unsafe_labels = [label["Name"] for label in labels]
            logger.warning(f"Frame {i} contains unsafe content: {unsafe_labels}")
            return False, unsafe_labels, i
    logger.info("All frames are safe.")
    return True, [], -1

def get_embedding(body):
    """Get embedding from Bedrock
    Args:
        body (str): The JSON body to send to Bedrock.
    Returns:    
        list: The embedding vector.
    """
    response = client.invoke_model(
        body=body,
        modelId="amazon.titan-embed-image-v1",
        accept="application/json",
        contentType="application/json",
    )
    embedding = json.loads(response["body"].read())["embedding"]
    return embedding

def extract_frames(gif_bytes, every_n=10, max_frames=5):
    """Extract frames from a GIF image.
    Args:
        gif_bytes (bytes): The bytes of the GIF image.
        every_n (int): Extract every n-th frame.
        max_frames (int): Maximum number of frames to extract.
    Returns:
        list: A list of PIL Image frames.
    """
    logger.info("Extracting frames from GIF...")
    frames = []
    im = Image.open(io.BytesIO(gif_bytes))
    idx = 0
    try:
        while True:
            if idx % every_n == 0:
                frames.append(im.convert("RGB"))
                if len(frames) >= max_frames:
                    break
            idx += 1
            im.seek(im.tell() + 1)
    except EOFError:
        logger.info("Reached end of GIF frames.")
    return frames

def get_file_name(request):
    """Get file name from request.
    Args:
        request (Request): The Scrapy Request object.
    Returns:
        str: The file name.
    """
    slug = request.meta.get("slug", "default")
    ext = os.path.splitext(request.url)[-1]
    file_name = f"{slug}{ext}"
    return file_name

def sync(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def get_s3_obj(file_path: str) -> bytes:
    """Get file bytes from S3 using boto3."""
    
    s3 = boto3.client("s3")
    print(f"Fetching S3 object for path: {file_path}")
    # file_path is relative, so join with prefix
    obj = s3.get_object(Bucket="gifs-memes", Key=file_path)
    # head = s3.head_object(Bucket=bucket, Key=file_path)
    print(f"Fetched S3 object metadata: {obj['Metadata']}")
    return obj

def update_s3_metadata(file_path: str, metadata: dict) -> None:
    """Update S3 object metadata to include safety status."""
    s3 = boto3.client("s3")
    copy_source = {"Bucket": "gifs-memes", "Key": file_path}
    s3.copy_object(
        Bucket="gifs-memes",
        Key=file_path,
        CopySource=copy_source,
        Metadata=metadata,
        MetadataDirective="REPLACE"
    )