#!/usr/bin/env python3
"""
Claude Code - AI-powered code generation and assistance
"""

import os
import sys
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables
load_dotenv()

def setup_claude():
    """Initialize Claude client with API key."""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY not found in environment variables.")
        print("Please create a .env file with your API key:")
        print("ANTHROPIC_API_KEY=your_api_key_here")
        sys.exit(1)
    
    return Anthropic(api_key=api_key)

def generate_code(client, prompt):
    """Generate code using Claude."""
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": f"Please generate code for the following request: {prompt}"
                }
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f"❌ Error generating code: {e}")
        return None

def analyze_code(client, code):
    """Analyze code using Claude."""
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": f"Please analyze this code and provide suggestions for improvement:\n\n{code}"
                }
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f"❌ Error analyzing code: {e}")
        return None

def main():
    """Main function to run Claude Code."""
    print("🚀 Claude Code - AI-powered code generation and assistance")
    print("=" * 60)
    
    # Initialize Claude client
    client = setup_claude()
    print("✅ Claude client initialized successfully!")
    
    while True:
        print("\n" + "=" * 60)
        print("Choose an option:")
        print("1. Generate code from description")
        print("2. Analyze existing code")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            prompt = input("\nDescribe the code you want to generate: ")
            print("\n🔄 Generating code...")
            result = generate_code(client, prompt)
            if result:
                print("\n✅ Generated code:")
                print("-" * 40)
                print(result)
                print("-" * 40)
                
                save = input("\nSave to file? (y/n): ").lower().strip()
                if save == 'y':
                    filename = input("Enter filename: ")
                    try:
                        with open(filename, 'w') as f:
                            f.write(result)
                        print(f"✅ Code saved to {filename}")
                    except Exception as e:
                        print(f"❌ Error saving file: {e}")
        
        elif choice == "2":
            print("\nEnter your code (press Enter twice to finish):")
            lines = []
            while True:
                line = input()
                if line == "" and lines and lines[-1] == "":
                    break
                lines.append(line)
            
            code = "\n".join(lines[:-1])  # Remove the last empty line
            if code.strip():
                print("\n🔄 Analyzing code...")
                result = analyze_code(client, code)
                if result:
                    print("\n✅ Code analysis:")
                    print("-" * 40)
                    print(result)
                    print("-" * 40)
            else:
                print("❌ No code provided.")
        
        elif choice == "3":
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
