# =============================================================================
# Temporal Client Configuration — Local Dev & Production
# =============================================================================
# Temporal 102 — "Deploying to Production":
#
# Moving a Temporal application between environments (local dev -> a
# self-hosted production Cluster -> Temporal Cloud) should only ever require
# changing how the Client connects — the target host:port, Namespace, and
# TLS/API-key credentials. Workflow and Activity code never needs to change.
#
# This module centralises that connection logic behind one function,
# `get_temporal_client()`, so both the Worker and the Client script
# (run_simulation.py) configure themselves identically.
#
# Configuration is read from environment variables so no code change is
# needed when deploying:
#
#   TEMPORAL_ADDRESS    host:port of the Frontend Service.
#                       Defaults to "localhost:7233" (local dev server).
#   TEMPORAL_NAMESPACE  Namespace to use. Defaults to "default".
#   TEMPORAL_API_KEY    Temporal Cloud API key. When set, the Client
#                       connects with API-key auth over TLS.
#   TEMPORAL_TLS_CERT   Path to a client certificate (mTLS), for self-hosted
#   TEMPORAL_TLS_KEY    Path to the matching private key (mTLS).
#
# Local development (no env vars set) works out of the box against:
#   temporal server start-dev
# =============================================================================

import os
from typing import Union

from temporalio.client import Client, TLSConfig


async def get_temporal_client() -> Client:
    """
    Connect to a Temporal Cluster using environment-driven configuration.

    Returns a Client wired for local dev by default, or for a secure
    self-hosted Cluster / Temporal Cloud when the relevant environment
    variables are set.
    """
    address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    api_key = os.getenv("TEMPORAL_API_KEY")
    tls_cert_path = os.getenv("TEMPORAL_TLS_CERT")
    tls_key_path = os.getenv("TEMPORAL_TLS_KEY")

    tls: Union[bool, TLSConfig] = False
    rpc_metadata: dict = {}

    if api_key:
        # Temporal Cloud (API-key auth) — requires TLS.
        tls = True
        rpc_metadata = {"temporal-namespace": namespace}
    elif tls_cert_path and tls_key_path:
        # Self-hosted Cluster secured with mutual TLS (mTLS).
        with open(tls_cert_path, "rb") as f:
            client_cert = f.read()
        with open(tls_key_path, "rb") as f:
            client_key = f.read()
        tls = TLSConfig(client_cert=client_cert, client_private_key=client_key)

    print(f"  [CLIENT CONFIG] address={address} namespace={namespace} "
          f"tls={'on' if tls else 'off'} api_key={'set' if api_key else 'unset'}")

    return await Client.connect(
        address,
        namespace=namespace,
        tls=tls,
        api_key=api_key,
        rpc_metadata=rpc_metadata,
    )
