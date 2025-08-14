#!/usr/bin/env python3
"""
Test script for the Web Scraper Agent
"""

import asyncio
import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from helper import get_openai_api_key
import nest_asyncio
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()

# Apply nest_asyncio to allow running in Jupyter or other nested event loops
nest_asyncio.apply()

# Define the data models
class DeeplearningCourse(BaseModel):
    title: str
    description: str
    presenter: list[str]
    imageUrl: str
    courseURL: str

class DeeplearningCourseList(BaseModel):
    courses: list[DeeplearningCourse]

# WebScraper Agent Class
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
        await self.page.goto(url, wait_until="load")
        await self.page.wait_for_timeout(2000)  # Wait for dynamic content
        return await self.page.content()

    async def take_screenshot(self, path="screenshot.png"):
        await self.page.screenshot(path=path, full_page=True)
        return path
    
    async def screenshot_buffer(self):
        screenshot_bytes = await self.page.screenshot(type="png", full_page=False)
        return screenshot_bytes

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.playwright = None
        self.browser = None
        self.page = None

async def process_with_llm(client, html, instructions):
    """Process HTML content with OpenAI LLM"""
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini-2024-07-18",
        messages=[{
            "role": "system",
            "content": f"""
            You are an expert web scraping agent. Your task is to:
            Extract relevant information from this HTML to JSON 
            following these instructions:
            {instructions}
            
            Extract the title, description, presenter, 
            the image URL and course URL for each of 
            all the courses for the deeplearning.ai website

            Return ONLY valid JSON, no markdown or extra text."""
        }, {
            "role": "user",
            "content": html[:150000]  # Truncate to stay under token limits
        }],
        temperature=0.1,
        response_format=DeeplearningCourseList,
    )
    return completion.choices[0].message.parsed

async def webscraper(client, scraper, target_url, instructions):
    """Main web scraping function"""
    result = None
    screenshot = None
    try:
        # Scrape content and capture screenshot
        print("🔍 Extracting HTML Content...")
        html_content = await scraper.scrape_content(target_url)
        
        print("📸 Taking Screenshot...")
        screenshot = await scraper.screenshot_buffer()
        
        # Save screenshot to file for verification
        with open("test_screenshot.png", "wb") as f:
            f.write(screenshot)
        print("   Screenshot saved as test_screenshot.png")
        
        # Process content
        print("🤖 Processing with LLM...")
        result = await process_with_llm(client, html_content, instructions)
        print("✅ Generated Structured Response")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    return result, screenshot

async def main():
    """Main test function"""
    print("=" * 60)
    print("🚀 Web Scraper Agent Test")
    print("=" * 60)
    
    # Check for API key
    try:
        api_key = get_openai_api_key()
        print("✅ OpenAI API key loaded successfully")
    except ValueError as e:
        print(f"❌ {e}")
        print("\nPlease create a .env file with your OpenAI API key:")
        print("OPENAI_API_KEY=your_api_key_here")
        return
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Initialize scraper
    scraper = WebScraperAgent()
    
    # Test parameters
    target_url = "https://www.deeplearning.ai/courses"
    base_url = "https://deeplearning.ai"
    
    print(f"\n🌐 Target URL: {target_url}")
    
    # Test 1: Get all courses
    print("\n" + "=" * 60)
    print("📋 Test 1: Fetching all courses")
    print("=" * 60)
    
    instructions = "Get all the courses"
    result, screenshot = await webscraper(client, scraper, target_url, instructions)
    
    if result and hasattr(result, 'courses'):
        print(f"\n✅ Successfully found {len(result.courses)} courses!")
        print("\n📚 First 3 courses:")
        for i, course in enumerate(result.courses[:3], 1):
            print(f"\n{i}. {course.title}")
            print(f"   Presenter(s): {', '.join(course.presenter) if course.presenter else 'N/A'}")
            print(f"   Description: {course.description[:100]}...")
    else:
        print("❌ No courses found")
    
    # Test 2: Filter for RAG courses
    print("\n" + "=" * 60)
    print("📋 Test 2: Filtering for RAG courses")
    print("=" * 60)
    
    subject = "Retrieval Augmented Generation (RAG)"
    instructions = f"""
    Read the description of the courses and only 
    provide the three courses that are about {subject}. 
    Make sure that we don't have any other
    courses in the output
    """
    
    result2, screenshot2 = await webscraper(client, scraper, target_url, instructions)
    
    if result2 and hasattr(result2, 'courses'):
        print(f"\n✅ Found {len(result2.courses)} RAG-related courses!")
        for i, course in enumerate(result2.courses, 1):
            print(f"\n{i}. {course.title}")
            print(f"   Presenter(s): {', '.join(course.presenter) if course.presenter else 'N/A'}")
    else:
        print("❌ No RAG courses found")
    
    # Clean up
    await scraper.close()
    print("\n" + "=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())