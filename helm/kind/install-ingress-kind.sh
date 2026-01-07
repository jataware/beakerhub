#!/bin/bash
# Install Nginx Ingress Controller for kind cluster
set -e

echo "🔧 Installing Nginx Ingress Controller"
echo "======================================="
echo ""

# Check if running on kind
if ! kubectl get nodes | grep -q "control-plane"; then
    echo "⚠️  Warning: This doesn't look like a kind cluster"
    read -p "Continue anyway? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        exit 0
    fi
fi

echo "Step 1: Installing Nginx Ingress Controller..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

echo ""
echo "Step 2: Waiting for Ingress Controller to be ready..."
kubectl wait --namespace ingress-nginx \
    --for=condition=ready pod \
    --selector=app.kubernetes.io/component=controller \
    --timeout=90s
# Sleep to allow time for service to finish loading the configuration
sleep 1

echo ""
echo "✅ Nginx Ingress Controller installation complete!"
echo ""
