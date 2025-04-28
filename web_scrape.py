import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import random
import re
import html2text
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import streamlit as st

def create_output_directory(directory_name="scraped"):
    if not os.path.exists(directory_name):
        os.makedirs(directory_name)
    return directory_name

def get_safe_filename(url, prefix=""):
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = urlparse(url).netloc.replace(".", "_")
    
    # Ensure filename is valid and safe
    filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
    if not filename:
        filename = "webpage"
    
    if prefix:
        filename = f"{prefix}_{filename}"
    
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename

def get_article_title(html_content):
    """Extract the most likely article title from HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Try multiple selectors that commonly contain the article title
    selectors = [
        'h1.entry-title', 'h1.post-title', 'h1.title', 
        'article h1', 'header h1', '.post-header h1',
        'h1', '.article-title', '.post-title', '.entry-title'
    ]
    
    for selector in selectors:
        title_elem = soup.select_one(selector)
        if title_elem and title_elem.text.strip():
            return title_elem.text.strip()
    
    # Fallback to the page title if no article title is found
    if soup.title:
        return soup.title.text.strip()
    
    return "Untitled Article"

def clean_html_content(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Get title from the article content if possible
    title = get_article_title(html_content)
    
    # Remove unwanted elements that aren't typically part of the main content
    for element in soup.select('nav, footer, aside, .sidebar, .comments, .footer, .nav, .menu, .social, .widget, script, style, [class*="cookie"], [class*="popup"], [id*="popup"], [class*="banner"], [id*="banner"], .ad, .ads, [class*="advertisement"], [class*="-ad-"]'):
        element.decompose()
    
    # Try to find the main content using common CSS selectors
    content_selectors = [
        'article', 'main', '.content', '.post', '.article', '.entry', 
        '.blog-post', '.blog-content', '.main-content', '.post-content',
        '.entry-content', '#content', '.page-content', '.article-content'
    ]
    
    main_content = None
    for selector in content_selectors:
        main_content = soup.select_one(selector)
        if main_content and len(main_content.get_text(strip=True)) > 500:
            break
    
    # Fallback to the body if no specific content container is found or content is too short
    if not main_content or len(main_content.get_text(strip=True)) < 500:
        main_content = soup.body
    
    # Convert HTML to markdown for better readability in the PDF
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0  # Disable line wrapping
    converter.unicode_snob = True  # Use Unicode instead of ASCII
    converter.images_to_alt = True  # Convert images to alt text
    converter.protect_links = True  # Don't append link targets
    
    markdown_content = converter.handle(str(main_content))
    
    return {
        'title': title,
        'content': markdown_content
    }

def save_as_pdf(url, output_path):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }
        
        session = requests.Session()
        try:
            # Try with a timeout first
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            # If timeout or HTTP error occurs, try once more with a longer timeout
            st.warning(f"Initial request failed, retrying: {str(e)}")
            response = session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
        
        processed_content = clean_html_content(response.text)
        
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        title_style = ParagraphStyle(
            'TitleStyle',
            fontSize=16,
            leading=20,
            textColor=colors.darkblue,
            spaceAfter=12
        )
        
        normal_style = ParagraphStyle(
            'NormalStyle',
            fontSize=11,
            leading=14,
            spaceAfter=6
        )
        
        url_style = ParagraphStyle(
            'URLStyle',
            fontSize=9,
            leading=12,
            textColor=colors.darkblue,
            spaceAfter=12
        )
        
        story = []
        
        story.append(Paragraph(processed_content['title'], title_style))
        story.append(Spacer(1, 0.25*inch))
        
        story.append(Paragraph(f"Source: {url}", url_style))
        story.append(Spacer(1, 0.25*inch))
        
        paragraphs = processed_content['content'].split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Skip image placeholders with no useful text
                if '![' in para and len(para.replace('![', '').strip()) < 5:
                    continue
                
                # Fix encoding issues that might occur
                para = para.encode('utf-8', 'ignore').decode('utf-8')
                
                if para.startswith('# '):
                    header_style = ParagraphStyle(
                        'Header1Style',
                        fontSize=14,
                        leading=18,
                        textColor=colors.darkblue,
                        spaceAfter=10
                    )
                    story.append(Paragraph(para.replace('# ', ''), header_style))
                elif para.startswith('## '):
                    header_style = ParagraphStyle(
                        'Header2Style',
                        fontSize=12,
                        leading=16,
                        textColor=colors.darkblue,
                        spaceAfter=8
                    )
                    story.append(Paragraph(para.replace('## ', ''), header_style))
                else:
                    # Clean up markdown formatting for better PDF display
                    para = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', para)  # Remove hyperlinks but keep text
                    para = para.replace('**', '').replace('*', '').replace('__', '').replace('_', '')
                    
                    # Wrap paragraphs in try/except to handle any PDF generation errors
                    try:
                        story.append(Paragraph(para, normal_style))
                    except Exception as e:
                        st.warning(f"Error adding paragraph to PDF: {e}")
                        # Try a simplified version without special characters
                        simplified = re.sub(r'[^\x00-\x7F]+', ' ', para)
                        story.append(Paragraph(simplified, normal_style))
        
        doc.build(story)
        return True
    except Exception as e:
        st.error(f"Error saving {url} as PDF: {e}")
        return False

def extract_article_links(main_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        session = requests.Session()
        try:
            response = session.get(main_url, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            st.warning(f"Initial request failed, retrying: {str(e)}")
            # If the first attempt fails, try with a longer timeout
            response = session.get(main_url, headers=headers, timeout=30)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        article_links = []
        
        # Common CSS selectors for blog articles
        article_selectors = [
            'article a', '.post a', '.article a', '.entry a', 
            'a.article', 'a.post', '.news-item a', '.blog-post a',
            '.content a', '.card a', '.entry-title a', 
            'h2 a', 'h3 a', '.blog-entry a', '.post-title a',
            '.blog-list__item a', '.blog-card a',
            '.resource-card a', '.blog-content a',
            '.title a', '.headline a'
        ]
        
        # Try each selector to find article links
        for selector in article_selectors:
            links = soup.select(selector)
            for link in links:
                if 'href' in link.attrs:
                    full_url = urljoin(main_url, link['href'])
                    # Only include links from the same domain and not already in our list
                    if urlparse(full_url).netloc == urlparse(main_url).netloc and full_url not in article_links:
                        # Exclude category, tag, author, and common non-article pages
                        excluded_patterns = ['/category/', '/tag/', '/author/', '/page/', '/wp-content/', 
                                           '/feed/', '/comments/', '/trackback/', '/wp-json/', 
                                           '/wp-admin/', '/login/', '/register/', '/search/']
                        
                        if not any(pattern in full_url for pattern in excluded_patterns):
                            article_links.append(full_url)
        
        # If no links found with selectors, try a more generic approach
        if not article_links:
            all_links = soup.find_all('a')
            base_domain = urlparse(main_url).netloc
            
            # Look for URLs that match common blog post patterns
            blog_patterns = [
                r'/(blog|article|post|news)/',  # Common blog URL patterns
                r'/\d{4}/\d{2}/',  # Date-based archives (common in WordPress)
                r'/[^/]+/[^/]+/$',  # Simple slug pattern (for blogs with direct slugs)
            ]
            
            for link in all_links:
                if 'href' in link.attrs:
                    full_url = urljoin(main_url, link['href'])
                    if urlparse(full_url).netloc == base_domain:
                        path = urlparse(full_url).path
                        
                        # Check if the URL matches any of our blog patterns
                        if any(re.search(pattern, path) for pattern in blog_patterns):
                            # Don't add duplicates
                            if full_url not in article_links:
                                # Exclude common non-article pages
                                excluded_patterns = ['/category/', '/tag/', '/author/', '/page/', '/wp-content/',
                                                   '/feed/', '/comments/', '/trackback/', '/wp-json/',
                                                   '/wp-admin/', '/login/', '/register/', '/search/']
                                
                                if not any(pattern in full_url for pattern in excluded_patterns):
                                    article_links.append(full_url)
        
        return list(set(article_links))
    
    except Exception as e:
        st.error(f"Error extracting article links: {e}")
        return []

def scrape_website_and_articles(main_url, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    main_page_filename = f"main_{get_safe_filename(main_url)}"
    if not main_page_filename.endswith('.pdf'):
        main_page_filename += '.pdf'
    main_page_path = os.path.join(output_dir, main_page_filename)
    
    main_page_saved = save_as_pdf(main_url, main_page_path)
    if not main_page_saved:
        st.warning("Failed to save the main webpage, but will attempt to continue with articles.")
    
    article_links = extract_article_links(main_url)
    
    # Filter out category and tag links
    article_links = [url for url in article_links if '/category/' not in url and '/tag/' not in url]
    
    st.info(f"Found {len(article_links)} article links.")
    
    # Process a limited number of articles to avoid timeouts
    max_to_process = min(10, len(article_links))
    successful_articles = 0
    
    for i in range(max_to_process):
        try:
            article_url = article_links[i]
            
            article_filename = f"article_{i+1}_{get_safe_filename(article_url)}"
            if not article_filename.endswith('.pdf'):
                article_filename += '.pdf'
            article_path = os.path.join(output_dir, article_filename)
            
            success = save_as_pdf(article_url, article_path)
            if success:
                successful_articles += 1
            
            # Add a small delay between requests to be respectful to the server
            time.sleep(random.uniform(1, 2))
        except Exception as e:
            st.error(f"Error processing article {i+1}: {e}")
            continue
    
    return successful_articles

if __name__ == "__main__":
    print("This module is designed to be imported, not run directly.")