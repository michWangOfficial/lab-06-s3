#!/bin/bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <book_url> <bucket_name> <expiration_seconds>"
    exit 1
fi

BOOK_URL="$1"
BUCKET="$2"
EXPIRATION="$3"
FILENAME=$(basename "$BOOK_URL")

# Download the book.
mkdir -p books
curl -fL "$BOOK_URL" -o "books/$FILENAME"

# Create a private bucket if needed.
if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book.
aws s3 cp "books/$FILENAME" "s3://$BUCKET/$FILENAME" --content-type "text/plain; charset=utf-8"

# Print a presigned URL.
aws s3 presign "s3://$BUCKET/$FILENAME" --expires-in "$EXPIRATION"
