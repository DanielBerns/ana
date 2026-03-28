#!/bin/bash

echo "=========================================="
echo "      ANA SYSTEM TEST SCRIPT"
echo "=========================================="
echo ""

# 1. Test the Configurator (The source of truth)
echo "1. Fetching global config from Configurator (Port 8005)..."
curl -s http://localhost:8005/config/interface
echo -e "\n\n"

# 2. Test the Interface Inspector
echo "2. Pinging Interface Inspector (Port 8000)..."
curl -s http://localhost:8000/inspector
echo -e "\n\n"

# 3. Simulate a Chat Webhook Payload
echo "3. Sending a User Prompt to the Chat Webhook (Port 8000)..."
curl -s -X POST http://localhost:8000/webhook/chat \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "test_user_001",
           "message": "Hello Ana, please process this request."
         }'
echo -e "\n\n"

# 4. Test the Store Component (Blob & Metadata Storage)
echo "4. Testing the Store Component (Port 8001)..."
# Create a quick dummy file to upload
echo "This is a test timeseries payload for the Ana system." > test_payload.txt

echo "   -> Uploading test_payload.txt to /files..."
curl -s -X POST http://localhost:8001/files \
     -F "file=@test_payload.txt" \
     -F "collection_id=bash_test_collection" \
     -F "retention_policy=ephemeral"
echo -e "\n"

echo "   -> Querying /collections/bash_test_collection..."
curl -s http://localhost:8001/collections/bash_test_collection
echo -e "\n\n"

# Clean up the local dummy file
rm test_payload.txt

# 5. Check the Inspector Dashboard
echo "5. Fetching the Inspector Dashboard (Port 8006) as Admin..."
# Using the default admin:admin credentials defined in the Inspector component
curl -s -u admin:admin http://localhost:8006/dashboard | grep "<h1>"
echo -e "\n\n"

echo "=========================================="
echo "Test complete! Check your component logs to see the events flowing."
