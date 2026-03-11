#!/bin/bash

# Set file names
KEY_FILE="localhost-key.pem"
CERT_FILE="localhost.pem"

# Generate private key and self-signed certificate for localhost
openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
  -keyout "$KEY_FILE" -out "$CERT_FILE" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost"

echo "Self-signed certificate and key have been generated:"
echo "  Key : $KEY_FILE"
echo "  Cert: $CERT_FILE"
