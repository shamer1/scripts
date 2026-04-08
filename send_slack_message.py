#!/usr/bin/env python3
"""
Simple script to send Slack messages from your Mac.

Two methods available:
1. Webhook URL (simpler, just for posting messages)
2. Bot OAuth Token (more features, can upload files, lookup users, etc.)
"""

import json
import os
import requests


def send_via_webhook(webhook_url: str, message: str):
    """
    Send a simple text message using a Slack webhook URL.

    Args:
        webhook_url: The full Slack webhook URL (e.g., from SLACK_WEBHOOK_STORAGE_OPERATIONS_LOG)
        message: The text message to send

    Returns:
        Response status code
    """
    headers = {"Content-Type": "application/json"}
    data = {"text": message}

    response = requests.post(
        webhook_url,
        headers=headers,
        data=json.dumps(data),
        timeout=30
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.status_code


def send_via_bot_token(bot_token: str, channel: str, message: str):
    """
    Send a message using Slack Bot OAuth Token.

    Args:
        bot_token: Your bot-user-oauth-token (starts with xoxb-)
        channel: Channel name (e.g., '#general') or channel ID
        message: The text message to send

    Returns:
        Response JSON
    """
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": channel,
        "text": message
    }

    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(data),
        timeout=30
    )

    result = response.json()
    print(f"Success: {result.get('ok')}")
    if not result.get('ok'):
        print(f"Error: {result.get('error')}")
    print(f"Response: {json.dumps(result, indent=2)}")
    return result


def send_file_via_bot_token(bot_token: str, channel: str, filepath: str, message: str = ""):
    """
    Upload a file to Slack using Bot OAuth Token.

    Args:
        bot_token: Your bot-user-oauth-token
        channel: Channel name (e.g., '#general') or channel ID
        filepath: Path to the file to upload
        message: Optional message to accompany the file

    Returns:
        Response status code
    """
    url = "https://slack.com/api/files.upload"
    headers = {
        "Authorization": f"Bearer {bot_token}",
    }

    with open(filepath, "rb") as f:
        payload = {
            "channels": channel,
            "file": f,
            "initial_comment": message,
        }
        response = requests.post(url, headers=headers, files=payload, timeout=30)

    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Success: {result.get('ok')}")
    if not result.get('ok'):
        print(f"Error: {result.get('error')}")
    return response.status_code


if __name__ == "__main__":
    # ============================================
    # METHOD 1: Using Webhook URL (Simplest!)
    # ============================================
    print("=" * 60)
    print("METHOD 1: Webhook URL")
    print("=" * 60)

    # Get your webhook URL from environment variable or paste it directly
    webhook = os.getenv("SLACK_WEBHOOK_STORAGE_OPERATIONS_LOG")

    if webhook:
        print("\n✓ Found webhook in environment variable")
        print(f"Webhook URL: {webhook[:50]}...")

        # Uncomment to send:
        send_via_webhook(webhook, "Testing")
        print("\nTo send a message, uncomment the line above and run again")
    else:
        print("\n✗ No webhook found in environment")
        print("\nTo use webhook method:")
        print("1. Export your webhook URL:")
        print("   export SLACK_WEBHOOK_STORAGE_OPERATIONS_LOG='https://hooks.slack.com/services/...'")
        print("\n2. Or paste it directly in the script:")
        print("   webhook = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'")

    # ============================================
    # METHOD 2: Using Bot OAuth Token
    # ============================================
    print("\n" + "=" * 60)
    print("METHOD 2: Bot OAuth Token")
    print("=" * 60)

    bot_token = os.getenv("SLACK_BOT_TOKEN")

    if bot_token:
        print("\n✓ Found bot token in environment variable")
        print(f"Token: {bot_token[:20]}...")

        # Uncomment to send:
        # send_via_bot_token(bot_token, "#your-channel-name", "Hello from bot! 🤖")
        print("\nTo send a message, uncomment the line above and specify your channel")
    else:
        print("\n✗ No bot token found in environment")
        print("\nTo use bot token method:")
        print("1. Export your bot token:")
        print("   export SLACK_BOT_TOKEN='xoxb-your-token-here'")
        print("\n2. Or paste it directly in the script:")
        print("   bot_token = 'xoxb-your-token-here'")

    print("\n" + "=" * 60)
    print("\nQuick comparison:")
    print("  Webhook URL:      Simple text messages only")
    print("  Bot OAuth Token:  Messages + file uploads + more features")
    print("=" * 60)
