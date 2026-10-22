#!/usr/bin/env python3
"""Stage books in a public S3 bucket."""

import sys
import os
import time
import json
import logging
import boto3
import requests
from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")

def parse_args():
    """Read command line arguments."""
    if len(sys.argv) < 4:
        log.error("Usage: uv run python src/s3_lab/stage_books.py <list_file> <index_path> <bucket>")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]

def download_books(list_file, dest_dir="books"):
    """Download books to dest_dir."""
    log.info("Downloading books to %s", dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    paths = []
    try:
        with open(list_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except IOError as e:
        log.error(f"Error reading {list_file}: {e}")
        return []

    for url in urls:
        filename = url.split("/")[-1]
        path = os.path.join(dest_dir, filename)
        if os.path.exists(path):
            paths.append(path)
            continue
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(response.content)
            paths.append(path)
            time.sleep(1)
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")
    return paths

def create_bucket(bucket):
    """Create S3 bucket if not exists."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info("Bucket %s already exists", bucket)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            try:
                s3.create_bucket(Bucket=bucket)
                log.info("Created bucket %s", bucket)
                return True
            except ClientError as e:
                log.error(f"Error creating bucket: {e}")
                return False
        log.error("Error checking bucket %s: %s", bucket, e)
        return False

def make_public(bucket):
    """Make bucket publicly readable."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*"
            }]
        }
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info("Made bucket %s public", bucket)
        return True
    except ClientError as e:
        log.error(f"Error making public: {e}")
        return False

def upload_files(bucket, file_paths):
    """Upload books to bucket."""
    log.info("Uploading %s books", len(file_paths))
    count = 0
    for path in file_paths:
        try:
            s3.upload_file(path, bucket, os.path.basename(path), 
                           ExtraArgs={"ContentType": "text/plain; charset=utf-8"})
            count += 1
        except (ClientError, S3UploadFailedError) as e:
            log.error(f"Error uploading {path}: {e}")
    return count

def upload_index(bucket, index_path):
    """Upload index.html to bucket."""
    try:
        s3.upload_file(index_path, bucket, "index.html", 
                       ExtraArgs={"ContentType": "text/html"})
        log.info("Uploaded index.html")
        return True
    except (ClientError, S3UploadFailedError, FileNotFoundError) as e:
        log.error(f"Error uploading index: {e}")
        return False

def main():
    list_file, index_path, bucket = parse_args()
    books = download_books(list_file)
    if not books:
        log.error("No books downloaded")
        sys.exit(1)
    if not create_bucket(bucket) or not make_public(bucket):
        sys.exit(1)
    uploaded = upload_files(bucket, books)
    if uploaded != len(books):
        log.error("Failed to upload all books")
        sys.exit(1)
    if not upload_index(bucket, index_path):
        log.error("Failed to upload index.html")
        sys.exit(1)
    log.info(f"Success. URL: https://{bucket}.s3.amazonaws.com/index.html")

if __name__ == "__main__":
    main()
