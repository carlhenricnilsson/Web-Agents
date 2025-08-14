#!/usr/bin/env python3
"""
Enhanced Web Agent with Autonomous Capabilities
Combines scraping and autonomous interaction using MultiOn
"""

import asyncio
import json
import os
import base64
import time
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

# Data models for scraping
class ExtractedData(BaseModel):
    title: str
    description: str
    url: str
    image_url: str = ""

class ExtractionResult(BaseModel):
    items: list[ExtractedData]

# Data models for autonomous actions
class ActionStep(BaseModel):
    step_number: int
    action: str
    status: str
    screenshot: str = ""
    message: str = ""

class AutonomousResult(BaseModel):
    task: str
    steps: list[ActionStep]
    final_status: str
    total_steps: int

# Mock MultiOn Client (since we might not have API access)
class MockMultiOnClient:
    """A mock client that simulates MultiOn functionality using Playwright"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.session_id = None
        self.current_url = None
        self.screenshot = None
        self.step_count = 0

    async def init_browser(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Show browser for autonomous actions
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        self.page = await self.browser.new_page()

    async def create_session(self, url):
        """Create a new agent session"""
        if not self.page:
            await self.init_browser()
        
        await self.page.goto(url, wait_until="load", timeout=30000)
        await self.page.wait_for_timeout(2000)
        
        self.session_id = f"session_{int(time.time())}"
        self.current_url = url
        self.screenshot = await self.take_screenshot()
        
        return {
            "session_id": self.session_id,
            "url": self.current_url,
            "screenshot": self.screenshot,
            "status": "CONTINUE"
        }

    async def execute_task(self, task, openai_client):
        """Execute a task using AI to determine actions"""
        if not self.page:
            raise ValueError("No active session. Call create_session first.")
        
        # Take screenshot for current state
        screenshot = await self.take_screenshot()
        
        # Get page content for context
        page_content = await self.page.content()
        
        # Use OpenAI to determine what action to take
        action = await self.determine_action(task, page_content, openai_client)
        
        # Execute the determined action
        result = await self.execute_action(action)
        
        self.step_count += 1
        
        return {
            "step": self.step_count,
            "action": action,
            "url": self.current_url,
            "screenshot": await self.take_screenshot(),
            "status": result.get("status", "CONTINUE"),
            "message": result.get("message", "")
        }

    async def determine_action(self, task, page_content, openai_client):
        """Use OpenAI to determine what action to take"""
        
        # Extract key elements from the page for better decision making
        visible_text = await self.page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                let text = '';
                let node;
                while (node = walker.nextNode()) {
                    if (node.parentElement.offsetParent !== null) {
                        text += node.textContent.trim() + ' ';
                    }
                }
                return text.slice(0, 2000);
            }
        """)
        
        # Get interactive elements
        interactive_elements = await self.page.evaluate("""
            () => {
                const elements = [];
                const selectors = ['button', 'a', 'input', 'select', 'textarea'];
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach((el, i) => {
                        if (el.offsetParent !== null && i < 10) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                text: el.textContent?.trim() || el.value || el.placeholder || '',
                                type: el.type || '',
                                name: el.name || '',
                                id: el.id || '',
                                href: el.href || ''
                            });
                        }
                    });
                });
                return elements;
            }
        """)
        
        prompt = f"""
        You are an AUTONOMOUS web agent. Your goal: "{task}"
        
        Current step: {self.step_count}
        URL: {self.current_url}
        
        VISIBLE PAGE CONTENT:
        {visible_text[:1500]}
        
        INTERACTIVE ELEMENTS FOUND:
        {json.dumps(interactive_elements[:15], indent=2)}
        
        BE PROACTIVE! Think step-by-step:
        1. What does the task require?
        2. What information is visible on this page?
        3. What action will help complete the task?
        4. Should I scroll to see more content?
        5. Should I click something to navigate?
        
        AVAILABLE ACTIONS:
        - CLICK button 'Text' - Click a button with specific text
        - CLICK link 'Text' - Click a link with specific text  
        - FILL field_name value - Fill a form field
        - SCROLL - Scroll down to see more content
        - NAVIGATE url - Go to a specific URL
        - SEARCH text - Look for specific text/content
        - TASK_COMPLETE - Task is finished successfully
        - TASK_FAILED - Cannot complete task
        
        DECISION RULES:
        - If task asks to "find" or "get" information: ACTIVELY look around the page, scroll if needed
        - If you don't see what you need: SCROLL down to explore more
        - If task involves courses/products: Look for navigation links, click relevant sections
        - If task asks for specific content: Search the page thoroughly before giving up
        - If you find relevant links: CLICK them to explore
        - If page has limited content: SCROLL to see more
        - Only say TASK_COMPLETE when you've actually found/done what was requested
        
        EXAMPLES:
        Task: "Get list of courses" → SCROLL (to see more courses) or CLICK link 'View All Courses'
        Task: "Find RAG course" → SCROLL or CLICK link containing 'RAG' or 'Retrieval'
        Task: "Subscribe to newsletter" → Look for email field, FILL it, then CLICK subscribe
        
        Choose the MOST HELPFUL action to progress toward completing: "{task}"
        Be PROACTIVE and EXPLORATORY, not passive!
        """
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.1
            )
            action = response.choices[0].message.content.strip()
            
            # Encourage exploration, but prevent infinite loops
            if self.step_count >= 8 and "TASK_COMPLETE" not in action and "TASK_FAILED" not in action:
                return "TASK_COMPLETE"
            
            return action
        except Exception as e:
            return "TASK_FAILED"

    async def execute_action(self, action):
        """Execute the determined action"""
        try:
            action_upper = action.upper()
            
            if "TASK_COMPLETE" in action_upper:
                return {"status": "COMPLETE", "message": "Task completed successfully"}
            
            elif "TASK_FAILED" in action_upper:
                return {"status": "FAILED", "message": "Task failed - could not complete"}
            
            elif action_upper.startswith("CLICK"):
                # Parse click command: "CLICK button 'Submit'" or "CLICK link 'Courses'"
                try:
                    # Try to find and click the specific element
                    if "button" in action.lower():
                        # Extract button text if specified
                        if "'" in action:
                            button_text = action.split("'")[1]
                            buttons = await self.page.query_selector_all("button")
                            for button in buttons:
                                text = await button.text_content()
                                if button_text.lower() in text.lower():
                                    await button.click()
                                    await self.page.wait_for_timeout(2000)
                                    return {"status": "CONTINUE", "message": f"Clicked button: {button_text}"}
                        
                        # Fallback: click first button
                        button = await self.page.query_selector("button")
                        if button:
                            await button.click()
                            await self.page.wait_for_timeout(2000)
                            return {"status": "CONTINUE", "message": "Clicked first button"}
                    
                    elif "link" in action.lower():
                        # Extract link text if specified
                        if "'" in action:
                            link_text = action.split("'")[1]
                            links = await self.page.query_selector_all("a")
                            for link in links:
                                text = await link.text_content()
                                if link_text.lower() in text.lower():
                                    await link.click()
                                    await self.page.wait_for_timeout(3000)
                                    return {"status": "CONTINUE", "message": f"Clicked link: {link_text}"}
                        
                        # Fallback: click first link
                        link = await self.page.query_selector("a")
                        if link:
                            await link.click()
                            await self.page.wait_for_timeout(3000)
                            return {"status": "CONTINUE", "message": "Clicked first link"}
                    
                    return {"status": "CONTINUE", "message": "No suitable element found to click"}
                    
                except Exception as e:
                    return {"status": "ERROR", "message": f"Click failed: {str(e)}"}
            
            elif action_upper.startswith("FILL"):
                # Parse fill command: "FILL email test@example.com"
                try:
                    parts = action.split()
                    if len(parts) >= 3:
                        field_name = parts[1]
                        value = " ".join(parts[2:])
                        
                        # Try to find field by name, id, or type
                        selectors = [
                            f"input[name='{field_name}']",
                            f"input[id='{field_name}']",
                            f"input[type='{field_name}']",
                            "input[type='email']" if field_name == "email" else "",
                            "input[type='text']" if field_name in ["text", "name"] else ""
                        ]
                        
                        for selector in selectors:
                            if selector:
                                element = await self.page.query_selector(selector)
                                if element:
                                    await element.fill(value)
                                    await self.page.wait_for_timeout(1000)
                                    return {"status": "CONTINUE", "message": f"Filled {field_name} with {value}"}
                        
                        # Fallback: fill first input
                        input_field = await self.page.query_selector("input[type='text'], input[type='email'], textarea")
                        if input_field:
                            await input_field.fill(value)
                            await self.page.wait_for_timeout(1000)
                            return {"status": "CONTINUE", "message": f"Filled field with {value}"}
                    
                    return {"status": "CONTINUE", "message": "Could not parse fill command"}
                    
                except Exception as e:
                    return {"status": "ERROR", "message": f"Fill failed: {str(e)}"}
            
            elif action_upper.startswith("SCROLL"):
                await self.page.evaluate("window.scrollBy(0, 500)")
                await self.page.wait_for_timeout(2000)
                return {"status": "CONTINUE", "message": "Scrolled down to explore more content"}
            
            elif action_upper.startswith("NAVIGATE"):
                # Parse navigate command: "NAVIGATE https://example.com"
                try:
                    if "http" in action:
                        url = action.split("http")[1]
                        if not url.startswith("://"):
                            url = "http" + url
                        await self.page.goto(url, wait_until="load", timeout=30000)
                        await self.page.wait_for_timeout(3000)
                        self.current_url = url
                        return {"status": "CONTINUE", "message": f"Navigated to {url}"}
                    else:
                        return {"status": "CONTINUE", "message": "Invalid navigation URL"}
                except Exception as e:
                    return {"status": "ERROR", "message": f"Navigation failed: {str(e)}"}
            
            elif action_upper.startswith("SEARCH"):
                # Parse search command: "SEARCH machine learning"
                try:
                    search_text = action[6:].strip()  # Remove "SEARCH"
                    
                    # Look for search input and fill it
                    search_input = await self.page.query_selector("input[type='search'], input[name*='search'], input[placeholder*='search']")
                    if search_input:
                        await search_input.fill(search_text)
                        await self.page.keyboard.press("Enter")
                        await self.page.wait_for_timeout(3000)
                        return {"status": "CONTINUE", "message": f"Searched for: {search_text}"}
                    else:
                        # If no search box, just scroll to look for the text
                        await self.page.evaluate("window.scrollBy(0, 300)")
                        await self.page.wait_for_timeout(1000)
                        return {"status": "CONTINUE", "message": f"Looking for: {search_text}"}
                        
                except Exception as e:
                    return {"status": "ERROR", "message": f"Search failed: {str(e)}"}
            
            else:
                # Unknown action - be more exploratory
                if self.step_count <= 3:
                    # Early steps: explore by scrolling
                    await self.page.evaluate("window.scrollBy(0, 400)")
                    await self.page.wait_for_timeout(1500)
                    return {"status": "CONTINUE", "message": f"Exploring page: {action}"}
                else:
                    # Later steps: just wait
                    await self.page.wait_for_timeout(1000)
                    return {"status": "CONTINUE", "message": f"Executed: {action}"}
                
        except Exception as e:
            return {"status": "ERROR", "message": f"Action execution failed: {str(e)}"}

    async def take_screenshot(self):
        """Take a screenshot and return as base64"""
        if self.page:
            screenshot_bytes = await self.page.screenshot(type="png", full_page=False)
            return base64.b64encode(screenshot_bytes).decode()
        return ""

    async def close_session(self):
        """Close the current session"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.playwright = None
        self.browser = None
        self.page = None

# Original WebScraper for data extraction
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
                "--disable-setuid-sandbox"
            ]
        )
        self.page = await self.browser.new_page()

    async def scrape_content(self, url):
        if not self.page or self.page.is_closed():
            await self.init_browser()
        await self.page.goto(url, wait_until="load", timeout=30000)
        await self.page.wait_for_timeout(3000)
        return await self.page.content()

    async def screenshot_buffer(self):
        screenshot_bytes = await self.page.screenshot(type="png", full_page=False)
        return base64.b64encode(screenshot_bytes).decode()

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

async def process_with_llm(client, html, instructions):
    """Process HTML content with OpenAI LLM for data extraction"""
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini-2024-07-18",
        messages=[{
            "role": "system",
            "content": f"""
            You are an expert web scraping agent. Extract relevant information 
            from this HTML content to JSON format.
            
            Instructions: {instructions}
            
            Extract structured data including titles, descriptions, URLs, and any relevant information.
            Return ONLY valid JSON, no markdown or extra text.
            """
        }, {
            "role": "user",
            "content": html[:150000]
        }],
        temperature=0.1,
        response_format=ExtractionResult,
    )
    return completion.choices[0].message.parsed

@app.route('/')
def index():
    """Main page with both scraping and autonomous options"""
    return render_template('autonomous_index.html')

@app.route('/scrape', methods=['POST'])
def scrape_website():
    """API endpoint to scrape a website (original functionality)"""
    try:
        data = request.json
        url = data.get('url', '').strip()
        instructions = data.get('instructions', 'Extract all relevant data from this webpage')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Get API key
        api_key = os.getenv('OPENAI_API_KEY') or "YOUR_OPENAI_API_KEY_HERE"
        
        if not api_key or api_key == "your_openai_api_key_here":
            return jsonify({'error': 'OpenAI API key not configured'}), 500
        
        # Run the scraping process
        result = asyncio.run(scrape_process(api_key, url, instructions))
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Scraping failed: {str(e)}'}), 500

@app.route('/autonomous', methods=['POST'])
def autonomous_task():
    """API endpoint to execute autonomous tasks"""
    try:
        data = request.json
        url = data.get('url', '').strip()
        task = data.get('task', '')
        max_steps = data.get('max_steps', 5)
        
        if not url or not task:
            return jsonify({'error': 'URL and task are required'}), 400
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Get API key
        api_key = os.getenv('OPENAI_API_KEY') or "YOUR_OPENAI_API_KEY_HERE"
        
        if not api_key:
            return jsonify({'error': 'OpenAI API key not configured'}), 500
        
        # Run the autonomous process
        result = asyncio.run(autonomous_process(api_key, url, task, max_steps))
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'Autonomous task failed: {str(e)}'}), 500

async def scrape_process(api_key, url, instructions):
    """Async function to handle the scraping process"""
    scraper = WebScraperAgent()
    client = OpenAI(api_key=api_key)
    
    try:
        html_content = await scraper.scrape_content(url)
        screenshot = await scraper.screenshot_buffer()
        result = await process_with_llm(client, html_content, instructions)
        
        return {
            'success': True,
            'type': 'scraping',
            'url': url,
            'screenshot': screenshot,
            'data': result.dict() if result else None,
            'raw_count': len(result.items) if result and result.items else 0
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        await scraper.close()

async def autonomous_process(api_key, url, task, max_steps):
    """Async function to handle autonomous task execution"""
    agent = MockMultiOnClient()
    client = OpenAI(api_key=api_key)
    steps = []
    
    try:
        # Create session
        session = await agent.create_session(url)
        
        # Initial screenshot
        steps.append({
            "step_number": 0,
            "action": f"Started session on {url}",
            "status": "CONTINUE",
            "screenshot": session["screenshot"],
            "message": "Session initialized"
        })
        
        # Execute task steps
        step = 1
        status = "CONTINUE"
        last_action = ""
        repeated_actions = 0
        
        while status == "CONTINUE" and step <= max_steps:
            try:
                result = await agent.execute_task(task, client)
                
                # Check for repeated actions (prevent loops) - but allow some exploration
                if result["action"] == last_action:
                    repeated_actions += 1
                    # Only stop if same action repeated 3+ times (more lenient for exploration)
                    if repeated_actions >= 3 and "SCROLL" not in result["action"]:
                        result["status"] = "COMPLETE"
                        result["message"] = "Stopping due to repeated actions"
                    # Allow more scrolling for exploration
                    elif repeated_actions >= 4 and "SCROLL" in result["action"]:
                        result["status"] = "COMPLETE"
                        result["message"] = "Finished exploring page content"
                else:
                    repeated_actions = 0
                    last_action = result["action"]
                
                steps.append({
                    "step_number": step,
                    "action": result["action"],
                    "status": result["status"],
                    "screenshot": result["screenshot"],
                    "message": result["message"]
                })
                
                status = result["status"]
                step += 1
                
                # Break on completion or failure
                if status in ["COMPLETE", "FAILED", "ERROR"]:
                    break
                
                # Wait between steps
                await asyncio.sleep(2)
                
            except Exception as e:
                steps.append({
                    "step_number": step,
                    "action": "ERROR",
                    "status": "ERROR",
                    "screenshot": "",
                    "message": f"Error: {str(e)}"
                })
                status = "ERROR"
                break
        
        return {
            'success': True,
            'type': 'autonomous',
            'task': task,
            'url': url,
            'steps': steps,
            'final_status': status,
            'total_steps': len(steps) - 1
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        await agent.close_session()

if __name__ == '__main__':
    print("🚀 Starting Enhanced Web Agent (Scraping + Autonomous)...")
    print("📍 Open your browser and go to: http://localhost:5002")
    app.run(debug=True, host='0.0.0.0', port=5002)