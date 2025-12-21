"""
GitHub webhook handler.

This module handles incoming GitHub webhooks for automated deployment
triggers, including signature verification and update script execution.

Author: Matthew Picone (mail@matthewpicone.com)
Date: 2025-12-17
"""

import asyncio
import hashlib
import hmac
import json
import os
import subprocess

from fastapi import APIRouter, Request, HTTPException, Header

router = APIRouter()

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
UPDATE_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts",
                                  "update_and_restart.sh")


def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify the GitHub webhook signature using HMAC-SHA256.

    Args:
        payload_body: Raw request body bytes.
        signature_header: X-Hub-Signature-256 header value.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not WEBHOOK_SECRET:
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    hash_object = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    return hmac.compare_digest(expected_signature, signature_header)


async def trigger_update():
    """Trigger the update script in the background.

    Validates the script exists and is executable before running it in a
    detached process.
    """
    try:
        # Validate the update script exists and is executable
        if not os.path.isfile(UPDATE_SCRIPT_PATH):
            msg = f"Error: Update script not found at {UPDATE_SCRIPT_PATH}"
            print(msg)
            return

        if not os.access(UPDATE_SCRIPT_PATH, os.X_OK):
            msg = f"Error: Update script not executable: {UPDATE_SCRIPT_PATH}"
            print(msg)
            return

        # Run the update script in the background
        subprocess.Popen(
            [UPDATE_SCRIPT_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        print(f"Update script triggered: {UPDATE_SCRIPT_PATH}")
    except Exception as e:
        print(f"Error triggering update script: {e}")


@router.post("/webhook/github")
async def github_webhook(
        request: Request,
        x_hub_signature_256: str = Header(None),
        x_github_event: str = Header(None),
):
    """Handle GitHub webhook events.

    Validates the payload signature using HMAC-SHA256 and triggers deployment
    updates when code is pushed to the main branch.

    Args:
        request: FastAPI request object.
        x_hub_signature_256: GitHub webhook signature header.
        x_github_event: GitHub event type header.

    Returns:
        Dictionary with status and message.

    Raises:
        HTTPException: If signature is invalid or payload cannot be parsed.
    """
    # Read the raw payload
    payload_body = await request.body()

    # Verify the webhook signature
    if not verify_webhook_signature(payload_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse the JSON payload
    try:
        payload = json.loads(payload_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Check if this is a push event to the main branch
    if x_github_event == "push":
        ref = payload.get("ref", "")
        if ref == "refs/heads/main":
            print("Received push event to main branch")
            # Trigger update in background
            asyncio.create_task(trigger_update())
            return {"status": "success", "message": "Update triggered for main branch"}

    # For other events, just acknowledge receipt
    return {
        "status": "ok",
        "message": f"Event {x_github_event} received but not processed",
    }
