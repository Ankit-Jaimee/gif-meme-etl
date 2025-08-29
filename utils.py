import boto3 
import io
import json
import logging
from PIL import Image

logger = logging.getLogger(__name__)

client = boto3.client('bedrock-runtime', region_name='us-east-1')

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