#!/usr/bin/env python3
"""
Web Agent Frontend - Flask Application
"""

import asyncio
import json
import os
import base64
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
import nest_asyncio
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()

# Apply nest_asyncio for Flask compatibility
nest_asyncio.apply()

app = Flask(__name__)

# Data models
class ExtractedData(BaseModel):
    title: str
    description: str
    url: str
    image_url: str = ""

class ExtractionResult(BaseModel):
    items: list[ExtractedData]

# Web Scraper Class
class WebScraperAgent:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    async def init_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--no-zygote",
                "--disable-audio-output",
                "--disable-software-rasterizer",
                "--disable-webgl",
                "--disable-web-security",
                "--disable-features=LazyFrameLoading",
                "--disable-features=IsolateOrigins",
                "--disable-background-networking"
            ]
        )
        self.page = await self.browser.new_page()

    async def scrape_content(self, url):
        if not self.page or self.page.is_closed():
            await self.init_browser()
        await self.page.goto(url, wait_until="load", timeout=30000)
        await self.page.wait_for_timeout(3000)  # Wait for dynamic content
        return await self.page.content()

    async def screenshot_buffer(self):
        screenshot_bytes = await self.page.screenshot(type="png", full_page=False)
        return base64.b64encode(screenshot_bytes).decode()

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.playwright = None
        self.browser = None
        self.page = None

async def process_with_llm(client, html, instructions, custom_instructions=""):
    """Process HTML content with OpenAI LLM"""
    system_prompt = f"""
    You are an expert web scraping agent. Your task is to:
    Extract relevant information from this HTML content to JSON format.
    
    Instructions: {instructions}
    
    {custom_instructions if custom_instructions else ""}
    
    Extract structured data including titles, descriptions, URLs, and any relevant information.
    Return ONLY valid JSON, no markdown or extra text.
    """
    
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini-2024-07-18",
        messages=[{
            "role": "system",
            "content": system_prompt
        }, {
            "role": "user",
            "content": html[:150000]  # Truncate to stay under token limits
        }],
        temperature=0.1,
        response_format=ExtractionResult,
    )
    return completion.choices[0].message.parsed

@app.route('/')
def index():
    """Main page with the web scraping form"""
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape_website():
    """API endpoint to scrape a website"""
    try:
        data = request.json
        url = data.get('url', '').strip()
        instructions = data.get('instructions', 'Extract all relevant data from this webpage')
        custom_instructions = data.get('custom_instructions', '')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Get API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            # Fallback to hardcoded key (same as in test script)
            api_key = "YOUR_OPENAI_API_KEY_HERE"
        
        if not api_key or api_key == "your_openai_api_key_here":
            return jsonify({'error': 'OpenAI API key not configured'}), 500
        
        # Run the scraping process
        result = asyncio.run(scrape_process(api_key, url, instructions, custom_instructions))
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Scraping failed: {str(e)}'}), 500

async def scrape_process(api_key, url, instructions, custom_instructions):
    """Async function to handle the scraping process"""
    scraper = WebScraperAgent()
    client = OpenAI(api_key=api_key)
    
    try:
        # Scrape content
        html_content = await scraper.scrape_content(url)
        
        # Take screenshot
        screenshot = await scraper.screenshot_buffer()
        
        # Process with LLM
        result = await process_with_llm(client, html_content, instructions, custom_instructions)
        
        return {
            'success': True,
            'url': url,
            'screenshot': screenshot,
            'data': result.dict() if result else None,
            'raw_count': len(result.items) if result and result.items else 0
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        await scraper.close()

if __name__ == '__main__':
    print("🚀 Starting Web Agent Frontend...")
    print("📍 Open your browser and go to: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)