#!/usr/bin/env python3
"""
Helper script to update the .env file with your OpenAI API key
"""

import os

print("=" * 60)
print("🔐 OpenAI API Key Configuration")
print("=" * 60)

# Get the API key from user
api_key = input("\nPlease enter your OpenAI API key (starts with sk-): ").strip()

if not api_key.startswith("sk-"):
    print("⚠️  Warning: OpenAI API keys typically start with 'sk-'")
    confirm = input("Continue anyway? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        exit()

# Create the .env content
env_content = f"""# OpenAI API Key (required for web scraping agent)
OPENAI_API_KEY={api_key}

# Anthropic API Key (optional, for main.py)
ANTHROPIC_API_KEY=your_anthropic_api_key_here
"""

# Write to .env file
with open('.env', 'w') as f:
    f.write(env_content)

print(f"\n✅ API key has been saved to .env file")
print(f"   Key starts with: {api_key[:10]}...")
print("\n📝 You can now run: python3 test_web_agent.py")