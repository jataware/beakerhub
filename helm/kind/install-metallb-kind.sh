#!/bin/bash
# Install MetalLB for kind cluster to enable LoadBalancer services

set -e

echo "🔧 Installing MetalLB for kind cluster"
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

echo "Step 1: Installing MetalLB..."
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/manifests/metallb-native.yaml
kubectl wait --for jsonpath='{.status.phase}=Active' namespace/metallb-system --timeout=5s

echo ""
echo "Step 2: Waiting for MetalLB to be ready..."
kubectl wait --namespace metallb-system \
    --for=create pod \
    --selector=app=metallb \
    --timeout=90s
kubectl wait --namespace metallb-system \
    --for=condition=ready pod \
    --selector=app=metallb \
    --timeout=90s

echo ""
echo "Step 3: Configuring IP address pool..."

# Get the kind network CIDR (IPv4 only)
KIND_NET_CIDR=$(docker network inspect kind -f '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}' | grep -v ':' | head -n1)
echo "  Kind network CIDR: $KIND_NET_CIDR"

# Calculate a usable IP range (last 50 IPs of the subnet)
BASE_IP=$(echo $KIND_NET_CIDR | cut -d'.' -f1-3)
echo "  Using IP range: ${BASE_IP}.200-${BASE_IP}.250"

# Create MetalLB configuration
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: kind-pool
  namespace: metallb-system
spec:
  addresses:
  - ${BASE_IP}.200-${BASE_IP}.250
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: kind-l2
  namespace: metallb-system
spec:
  ipAddressPools:
  - kind-pool
EOF

echo ""
echo "✅ MetalLB installation complete!"
echo ""
echo "Your LoadBalancer services should now receive external IPs."
echo ""
echo "Check your service:"
echo "  kubectl get svc beakerhub-proxy -n beakerhub"
echo ""
echo "It may take 10-30 seconds for the IP to be assigned."
