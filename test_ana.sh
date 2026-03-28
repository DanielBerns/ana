#!/bin/bash

echo "=========================================="
echo "      ANA SYSTEM TEST SCRIPT"
echo "=========================================="
echo ""

# 1. Test the Configurator (The source of truth)
echo "1. Fetching global config from Configurator (Port 8005)..."
curl -s http://localhost:8005/config/interface
echo -e "\n\n"

# 2. Test the Interface Diagnostic
echo "2. Pinging Interface Diagnostic (Port 8000)..."
curl -s http://localhost:8000/diagnostic
echo -e "\n\n"

# 3. Simulate a Chat Webhook Payload
echo "3. Sending a User Prompt to the Chat Webhook..."
curl -s -X POST http://localhost:8000/webhook/chat \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "test_user_001",
           "message": "Hello Ana, please process this request."
         }'
echo -e "\n\n"

# 4. Check the Inspector Dashboard (Requires HTTP Basic Auth)
echo "4. Fetching the Inspector Dashboard (Port 8006) as Admin..."
# Using the default admin:admin credentials defined in the Inspector component
curl -s -u admin:admin http://localhost:8006/dashboard | grep "<h1>"
echo -e "\n\n"

echo "=========================================="
echo "Test complete! Check your component logs to see the events flowing."
