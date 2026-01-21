#!/bin/bash

# SSL Certificate Setup Script
# This script copies and converts SSL certificates for Docker Nginx

set -e  # Exit on error

echo "=== SSL Certificate Setup ==="
echo ""

# Project directory
PROJECT_DIR="/home/user/Traceability/nashik-chatbot-pq"
SSL_DIR="$PROJECT_DIR/ssl"

# Certificate source directory (update if different)
CERT_SOURCE="${1:-/home/maiuser/certificate}"

echo "Project directory: $PROJECT_DIR"
echo "SSL directory: $SSL_DIR"
echo "Certificate source: $CERT_SOURCE"
echo ""

# Check if source directory exists
if [ ! -d "$CERT_SOURCE" ]; then
    echo "ERROR: Certificate source directory not found: $CERT_SOURCE"
    echo ""
    echo "Usage: $0 [certificate_directory]"
    echo "Example: $0 /path/to/certificates"
    echo ""
    echo "Please provide the correct path to your certificate directory."
    exit 1
fi

# Create SSL directory if it doesn't exist
mkdir -p "$SSL_DIR"
chmod 700 "$SSL_DIR"

echo "Step 1: Listing available certificate files..."
echo "---"
ls -lh "$CERT_SOURCE"
echo ""

# Find certificate files
CER_FILE=$(find "$CERT_SOURCE" -name "*.cer" -o -name "*.crt" | head -1)
KEY_FILE=$(find "$CERT_SOURCE" -name "*.key" | head -1)
PFX_FILE=$(find "$CERT_SOURCE" -name "*.pfx" -o -name "*.p12" | head -1)
CA_FILE=$(find "$CERT_SOURCE" -name "*CA*.cer" -o -name "*CA*.crt" | head -1)

echo "Step 2: Detecting certificate files..."
echo "Certificate file: ${CER_FILE:-Not found}"
echo "Private key file: ${KEY_FILE:-Not found}"
echo "PFX file: ${PFX_FILE:-Not found}"
echo "CA file: ${CA_FILE:-Not found}"
echo ""

# Check if we have at least certificate and key
if [ -z "$CER_FILE" ] && [ -z "$PFX_FILE" ]; then
    echo "ERROR: No certificate file (.cer, .crt, or .pfx) found!"
    exit 1
fi

echo "Step 3: Processing certificate..."

# If we have a PFX file, extract certificate and key from it
if [ -n "$PFX_FILE" ]; then
    echo "Found PFX file: $PFX_FILE"
    echo "Extracting certificate and private key from PFX..."

    # Extract certificate
    openssl pkcs12 -in "$PFX_FILE" -clcerts -nokeys -out "$SSL_DIR/cert.pem" -passin pass: 2>/dev/null || \
    openssl pkcs12 -in "$PFX_FILE" -clcerts -nokeys -out "$SSL_DIR/cert.pem"

    # Extract private key
    openssl pkcs12 -in "$PFX_FILE" -nocerts -nodes -out "$SSL_DIR/key.pem" -passin pass: 2>/dev/null || \
    openssl pkcs12 -in "$PFX_FILE" -nocerts -nodes -out "$SSL_DIR/key.pem"

    echo "✓ Certificate and key extracted from PFX"

elif [ -n "$CER_FILE" ]; then
    echo "Found certificate file: $CER_FILE"

    # Check if certificate is in PEM format
    if openssl x509 -in "$CER_FILE" -text -noout >/dev/null 2>&1; then
        echo "Certificate is in PEM format"
        cp "$CER_FILE" "$SSL_DIR/cert.pem"
    else
        echo "Certificate is in DER format, converting to PEM..."
        openssl x509 -inform DER -in "$CER_FILE" -out "$SSL_DIR/cert.pem"
    fi
    echo "✓ Certificate copied/converted"

    # Copy private key if found
    if [ -n "$KEY_FILE" ]; then
        echo "Found private key: $KEY_FILE"
        cp "$KEY_FILE" "$SSL_DIR/key.pem"
        echo "✓ Private key copied"
    else
        echo "WARNING: Private key not found! You'll need to provide it manually."
    fi
fi

# Add CA certificate to chain if found
if [ -n "$CA_FILE" ] && [ -f "$SSL_DIR/cert.pem" ]; then
    echo ""
    echo "Step 4: Adding CA certificate to chain..."

    # Check if CA is in PEM format
    if openssl x509 -in "$CA_FILE" -text -noout >/dev/null 2>&1; then
        cat "$CA_FILE" >> "$SSL_DIR/cert.pem"
    else
        openssl x509 -inform DER -in "$CA_FILE" >> "$SSL_DIR/cert.pem"
    fi
    echo "✓ CA certificate added to chain"
fi

echo ""
echo "Step 5: Setting permissions..."
if [ -f "$SSL_DIR/key.pem" ]; then
    chmod 600 "$SSL_DIR/key.pem"
    echo "✓ Private key: 600 (owner read/write only)"
fi

if [ -f "$SSL_DIR/cert.pem" ]; then
    chmod 644 "$SSL_DIR/cert.pem"
    echo "✓ Certificate: 644 (owner read/write, others read)"
fi

echo ""
echo "Step 6: Verifying certificate..."
if [ -f "$SSL_DIR/cert.pem" ]; then
    echo "---"
    openssl x509 -in "$SSL_DIR/cert.pem" -noout -subject -issuer -dates
    echo "---"
fi

echo ""
echo "Step 7: Verifying certificate and key match..."
if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
    CERT_MD5=$(openssl x509 -noout -modulus -in "$SSL_DIR/cert.pem" | openssl md5)
    KEY_MD5=$(openssl rsa -noout -modulus -in "$SSL_DIR/key.pem" 2>/dev/null | openssl md5)

    if [ "$CERT_MD5" = "$KEY_MD5" ]; then
        echo "✓ Certificate and private key match!"
    else
        echo "✗ WARNING: Certificate and private key DO NOT match!"
        echo "  This will cause SSL errors!"
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "SSL files created in: $SSL_DIR"
ls -lh "$SSL_DIR"
echo ""
echo "Next steps:"
echo "1. Review the certificate details above"
echo "2. Restart Docker containers: sudo docker compose down && sudo docker compose up -d"
echo "3. Test HTTPS: curl https://localhost --insecure"
echo "4. Check nginx logs: sudo docker compose logs nginx"
echo ""
