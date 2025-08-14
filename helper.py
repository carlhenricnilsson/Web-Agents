import os
import base64
from io import BytesIO
from PIL import Image
from IPython.display import display, HTML, Markdown
import pandas as pd
from tabulate import tabulate

def get_openai_api_key():
    """Get OpenAI API key from environment variable or .env file."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("Please set your OPENAI_API_KEY in the .env file")
    
    return api_key

async def visualizeCourses(result, screenshot, target_url, instructions, base_url):
    """Visualize scraped courses with screenshot and formatted data."""
    
    # Display the screenshot
    if screenshot:
        img = Image.open(BytesIO(screenshot))
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        img_base64 = base64.b64encode(img_buffer.read()).decode()
        img_html = f'<img src="data:image/png;base64,{img_base64}" style="max-width:100%; height:auto; border:1px solid #ddd; border-radius:4px; margin:20px 0;">'
        display(HTML(img_html))
    
    # Display the target URL and instructions
    display(Markdown(f"### 🌐 Target URL: {target_url}"))
    display(Markdown(f"### 📋 Instructions:\n{instructions}"))
    
    # Display the results
    if result and hasattr(result, 'courses'):
        display(Markdown(f"### ✅ Found {len(result.courses)} courses:"))
        
        # Create a DataFrame for better visualization
        courses_data = []
        for course in result.courses:
            # Ensure URLs are complete
            image_url = course.imageUrl
            if image_url and not image_url.startswith('http'):
                image_url = f"{base_url}{image_url}" if not image_url.startswith('/') else f"{base_url}{image_url}"
            
            course_url = course.courseURL
            if course_url and not course_url.startswith('http'):
                course_url = f"{base_url}{course_url}" if not course_url.startswith('/') else f"{base_url}{course_url}"
            
            courses_data.append({
                'Title': course.title,
                'Description': course.description[:100] + '...' if len(course.description) > 100 else course.description,
                'Presenter(s)': ', '.join(course.presenter) if course.presenter else 'N/A',
                'Course URL': f'<a href="{course_url}" target="_blank">View Course</a>' if course_url else 'N/A',
                'Image': f'<img src="{image_url}" style="width:100px; height:auto;">' if image_url else 'N/A'
            })
        
        if courses_data:
            df = pd.DataFrame(courses_data)
            
            # Display as HTML table with clickable links and images
            html_table = df.to_html(escape=False, index=False, 
                                   table_id='courses-table',
                                   classes='table table-striped table-bordered')
            
            # Add some CSS styling
            styled_html = f"""
            <style>
                #courses-table {{
                    width: 100%;
                    margin: 20px 0;
                    border-collapse: collapse;
                }}
                #courses-table th {{
                    background-color: #f2f2f2;
                    padding: 12px;
                    text-align: left;
                    border: 1px solid #ddd;
                }}
                #courses-table td {{
                    padding: 10px;
                    border: 1px solid #ddd;
                    vertical-align: top;
                }}
                #courses-table tr:hover {{
                    background-color: #f5f5f5;
                }}
                #courses-table a {{
                    color: #0066cc;
                    text-decoration: none;
                }}
                #courses-table a:hover {{
                    text-decoration: underline;
                }}
            </style>
            {html_table}
            """
            
            display(HTML(styled_html))
            
            # Also display as text table for terminal output
            text_data = []
            for course in result.courses:
                text_data.append([
                    course.title[:40] + '...' if len(course.title) > 40 else course.title,
                    course.description[:50] + '...' if len(course.description) > 50 else course.description,
                    ', '.join(course.presenter[:2]) if course.presenter else 'N/A'
                ])
            
            if text_data:
                print("\n" + tabulate(text_data, headers=['Title', 'Description', 'Presenter(s)'], tablefmt='grid'))
    else:
        display(Markdown("### ❌ No courses found or error in processing"))