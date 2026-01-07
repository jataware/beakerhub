#!/bin/bash
# Update local DNS and routing for BeakerHub development
set -e

NAMESPACE=${NAMESPACE:-beakerhub}
REGISTRY_URL=${REGISTRY_URL:-registry.beakerhub.internal}
DNSMASQ_CONTAINER_NAME=${DNSMASQ_CONTAINER_NAME:-beaker-local-dns}
DNSMASQ_PORT=${DNSMASQ_PORT:-55353}
INGRESS_IP=""
REGISTRY_IP=""

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos" ;;
        Linux*)  echo "linux" ;;
        *)       echo "unknown" ;;
    esac
}

OS=$(detect_os)

# Try to get Ingress Controller IP
INGRESS_IP=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")

if [ -z "$INGRESS_IP" ]; then
    echo "❌ Ingress Controller not found or no LoadBalancer IP assigned"
    echo ""
    echo "Make sure Nginx Ingress is installed:"
    echo "  make install-ingress"
    exit 1
fi

echo "Found Ingress IP: $INGRESS_IP"


# Try to get Registry IP
REGISTRY_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{break}}{{end}}' beaker-local-registry)
if [ ! -z "$REGISTRY_IP" ]; then
    echo "Found Registry IP: $REGISTRY_IP"
fi


# ============================================================================
# Dnsmasq Configuration
# ============================================================================

update_dnsmasq() {
    echo ""
    echo "🔧 Configuring dnsmasq for wildcard DNS..."

    if ! docker container inspect "$DNSMASQ_CONTAINER_NAME" >/dev/null 2>&1; then
        echo "⚠️  dnsmasq container ($DNSMASQ_CONTAINER_NAME) not running."
        echo "   Run 'make dev-dns' first."
        return 1
    fi

    docker exec "$DNSMASQ_CONTAINER_NAME" sh -c "> /etc/dnsmasq.d/beakerhub.conf"
    # Write config to the container
    if [ ! -z "$REGISTRY_IP" ]; then
        docker exec "$DNSMASQ_CONTAINER_NAME" sh -c "echo 'address=/$REGISTRY_URL/$REGISTRY_IP' >> /etc/dnsmasq.d/beakerhub.conf"
    fi
    docker exec "$DNSMASQ_CONTAINER_NAME" sh -c "echo 'address=/beakerhub.internal/$INGRESS_IP' >> /etc/dnsmasq.d/beakerhub.conf"

    # Restart to pick up new config
    docker restart "$DNSMASQ_CONTAINER_NAME" >/dev/null

    echo "  ✓ dnsmasq configured: *.beakerhub.internal -> $INGRESS_IP"
}

# ============================================================================
# System Resolver Configuration
# ============================================================================

check_resolver_configured() {
    case "$OS" in
        macos)
            if [ -f /etc/resolver/beakerhub.internal ]; then
                if grep -q "port $DNSMASQ_PORT" /etc/resolver/beakerhub.internal 2>/dev/null; then
                    return 0
                fi
            fi
            return 1
            ;;
        linux)
            # Only consider "configured" if systemd-resolved is running and has our config
            if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
                if [ -f /etc/systemd/resolved.conf.d/beakerhub.conf ]; then
                    if grep -q "$DNSMASQ_PORT" /etc/systemd/resolved.conf.d/beakerhub.conf 2>/dev/null; then
                        return 0
                    fi
                fi
            fi
            # For non-systemd-resolved setups, always return 1 to show instructions
            return 1
            ;;
        *)
            return 1
            ;;
    esac
}

configure_resolver_macos() {
    echo ""
    echo "🔧 Configuring macOS resolver..."
    echo ""
    echo "This will create /etc/resolver/beakerhub.internal to route"
    echo "*.beakerhub.internal queries to the local dnsmasq server."
    echo ""
    read -p "Do you want to proceed? (y/N) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Resolver configuration skipped."
        return 0
    fi

    sudo mkdir -p /etc/resolver
    sudo tee /etc/resolver/beakerhub.internal >/dev/null <<EOF
nameserver 127.0.0.1
port $DNSMASQ_PORT
EOF

    echo "  ✓ macOS resolver configured"
}

configure_resolver_linux() {
    # Check if systemd-resolved is actually running
    if ! systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        echo ""
        echo "⚠️  systemd-resolved is not running."
        echo "   Please configure your DNS server to forward *.beakerhub.internal to 127.0.0.1:$DNSMASQ_PORT"
        echo ""
        echo "   For BIND9, add to named.conf:"
        echo "     zone \"beakerhub.internal\" {"
        echo "         type forward;"
        echo "         forward only;"
        echo "         forwarders { 127.0.0.1 port $DNSMASQ_PORT; };"
        echo "     };"
        echo ""
        echo "   For dnsmasq, add to /etc/dnsmasq.d/beakerhub.conf:"
        echo "     server=/beakerhub.internal/127.0.0.1#$DNSMASQ_PORT"
        echo ""
        echo "   For Unbound, add to unbound.conf:"
        echo "     forward-zone:"
        echo "         name: \"beakerhub.internal.\""
        echo "         forward-addr: 127.0.0.1@$DNSMASQ_PORT"
        echo ""
        return 0
    fi

    echo ""
    echo "🔧 Configuring systemd-resolved..."
    echo ""
    echo "This will create /etc/systemd/resolved.conf.d/beakerhub.conf to route"
    echo "*.beakerhub.internal queries to the local dnsmasq server."
    echo ""
    read -p "Do you want to proceed? (y/N) " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Resolver configuration skipped."
        return 0
    fi

    sudo mkdir -p /etc/systemd/resolved.conf.d
    sudo tee /etc/systemd/resolved.conf.d/beakerhub.conf >/dev/null <<EOF
[Resolve]
DNS=127.0.0.1:$DNSMASQ_PORT
Domains=~beakerhub.internal
EOF

    sudo systemctl restart systemd-resolved

    echo "  ✓ systemd-resolved configured"
}

configure_resolver() {
    if check_resolver_configured; then
        echo "  ✓ System resolver already configured"
        return 0
    fi

    case "$OS" in
        macos)
            configure_resolver_macos
            ;;
        linux)
            configure_resolver_linux
            ;;
        *)
            echo "⚠️  Unknown OS. Please configure DNS resolver manually."
            echo "   Point *.beakerhub.internal to 127.0.0.1:$DNSMASQ_PORT"
            ;;
    esac
}

# ============================================================================
# Main
# ============================================================================

echo ""
echo "🌐 BeakerHub Network Configuration"
echo "==================================="

# Update dnsmasq configuration
update_dnsmasq

# Configure system resolver
configure_resolver

echo ""
echo "✅ Network configuration complete!"

if [ "${DEFER_LOCAL_SUMMARY:-0}" != "1" ]; then
    echo ""
    echo "Access your services at:"
    echo "  BeakerHub:      https://beakerhub.internal"
    echo "  Vite server:    http://vite.beakerhub.internal"
    echo "  Registry:       https://$REGISTRY_URL"
    echo "  User sessions:  https://<session>.beakerhub.internal (when subdomain routing is enabled)"
    echo ""
    echo "To test DNS resolution:"
    echo "  dig @127.0.0.1 -p $DNSMASQ_PORT test.beakerhub.internal"
    echo ""
fi
