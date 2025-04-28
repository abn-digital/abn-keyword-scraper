import streamlit as st
import os
import time
import re
from gemini import call_gemini_api, get_all_files_from_directory
import tempfile
import shutil

# Set page config
st.set_page_config(
    page_title="SEO Keyword Extractor",
    page_icon="🔍",
    layout="wide"
)

# Apply custom CSS
st.markdown("""
<style>
    .main {
        padding: 1rem;
    }
    .stButton button {
        width: 100%;
    }
    .block-container {
        padding-top: 1rem;
    }
    .output-container {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 1rem;
        height: 450px;
        overflow-y: auto;
        border: 1px solid #ddd;
        margin-bottom: 20px;
    }
    .keyword-container {
        background-color: #f8f9fa;
        border-radius: 5px;
        padding: 1rem;
        height: 450px;
        overflow-y: auto;
        border: 1px solid #ddd;
    }
    .article-item {
        padding: 12px;
        margin: 8px 0;
        border-radius: 4px;
        background-color: #f0f0f0;
        border-left: 4px solid #3366cc;
        font-size: 16px;
    }
    .url-preview {
        padding: 20px;
        background-color: #f8f9fa;
        border-radius: 5px;
        text-align: center;
        font-size: 18px;
        font-weight: bold;
        height: 450px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid #ddd;
    }
    .copy-btn {
        position: absolute;
        bottom: 10px;
        right: 10px;
    }
    /* Fix for Streamlit container issues */
    .st-emotion-cache-1r6slb0 {
        width: 100%;
    }
    .stMarkdown div {
        width: 100% !important;
    }
    /* Status indicator styles */
    .status-ready {
        color: green;
        font-weight: bold;
    }
    .status-pending {
        color: #ff9900;
        font-weight: bold;
    }
    .article-selected {
        border-left: 4px solid #00cc66;
        background-color: #e6f7f2;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'articles' not in st.session_state:
    st.session_state.articles = []
if 'article_details' not in st.session_state:
    st.session_state.article_details = {}  # To store titles and selection status
if 'preview_image' not in st.session_state:
    st.session_state.preview_image = None
if 'keywords' not in st.session_state:
    st.session_state.keywords = "No keywords found yet"
if 'temp_dir' not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp()
if 'scraped_dir' not in st.session_state:
    st.session_state.scraped_dir = os.path.join(st.session_state.temp_dir, "scraped")
    os.makedirs(st.session_state.scraped_dir, exist_ok=True)
if 'screenshot_path' not in st.session_state:
    st.session_state.screenshot_path = None
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = None
if 'status' not in st.session_state:
    st.session_state.status = "Ready"
if 'last_analyzed_url' not in st.session_state:
    st.session_state.last_analyzed_url = None

# Title with logo and information
with st.container():
    col1, col2 = st.columns([1, 5])
    with col1:
        st.image("https://img.icons8.com/color/96/000000/search-engine-optimization.png", width=80)
    with col2:
        st.title("Blog SEO Keyword Extractor")
        st.markdown("""
        Extract long-tail keywords and search phrases from blog articles using AI analysis.
        """)

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["Extract Keywords", "How It Works", "Settings"])

with tab1:
    # Input URL
    url_input = st.text_input("Enter website URL:", placeholder="https://example.com/blog")

    # Status indicator
    status_class = "status-ready" if st.session_state.status == "Ready" else "status-pending"
    st.markdown(f'<div class="{status_class}">Status: {st.session_state.status}</div>', unsafe_allow_html=True)

    # Buttons row
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        fetch_button = st.button("Fetch Blog Articles", use_container_width=True, 
                                disabled=(st.session_state.status == "Processing"))

    with col2:
        analyze_button = st.button("Analyze Selected Articles", use_container_width=True, 
                                 disabled=(len(st.session_state.articles) == 0 or st.session_state.status == "Processing"))

    with col3:
        clear_button = st.button("Clear All", use_container_width=True)

    # Main content area
    content_col1, content_col2, content_col3 = st.columns([1, 1, 1])

# Function to toggle article selection
def toggle_article_selection(index):
    if index in st.session_state.article_details:
        st.session_state.article_details[index]['selected'] = not st.session_state.article_details[index]['selected']
        st.experimental_rerun()

# Function to copy text to clipboard using JavaScript
def copy_to_clipboard(text):
    # JavaScript to copy text to clipboard
    js = f"""
    <script>
    function copyToClipboard() {{
        const text = `{text}`;
        navigator.clipboard.writeText(text)
            .then(() => {{
                console.log('Text copied to clipboard');
            }})
            .catch(err => {{
                console.error('Error copying text: ', err);
            }});
    }}
    </script>
    <button onclick="copyToClipboard()">Copy to Clipboard</button>
    """
    return js

# Function to analyze selected articles with Gemini
def analyze_articles():
    with st.status("Analyzing articles with Gemini API...") as status:
        st.session_state.status = "Processing"
        
        # Get files from the scraped directory - only for selected articles
        all_files = get_all_files_from_directory(st.session_state.scraped_dir)
        
        # Always include the main page if it exists
        files_to_process = [f for f in all_files if "main_page" in f]
        
        # Add selected article files
        for index, article in enumerate(st.session_state.articles):
            if index in st.session_state.article_details and st.session_state.article_details[index]['selected']:
                article_files = [f for f in all_files if f"article_{index+1}_" in f]
                files_to_process.extend(article_files)
        
        if not files_to_process:
            st.error("No files selected for analysis. Please select at least one article.")
            st.session_state.status = "Ready"
            status.update(label="Error: No files selected", state="error")
            return
        
        status.update(label=f"Processing {len(files_to_process)} files...", state="running")
        
        # Prepare the prompt for Gemini
        user_prompt = """ Puedes responder en español o en inglés, dependiendo principalmente del idioma de los documentos PDF proporcionados. Analiza todos los documentos PDF proporcionados como si fueran páginas web optimizadas para SEO.

Extrae de 5 a 10 palabras clave de cola larga o frases de búsqueda implícitas a las que estas páginas probablemente estén orientadas. Enfócate en frases naturales y de nicho que un usuario podría buscar en Google, asegurándote de que estén adaptadas al idioma y contexto de los artículos.

Tu respuesta debe estar formateada de la siguiente manera:

[primera palabra clave/frase] (en español)

[segunda palabra clave/frase] (en español)

[tercera palabra clave/frase] (en español) ...

Asegúrate de que las palabras clave reflejen los temas principales tratados en todo el contenido analizado, con énfasis en la especificidad, la intención de búsqueda y la adecuación lingüística."""
        
        # Call Gemini API
        result = call_gemini_api(user_prompt, files_to_process)
        
        if result:
            st.session_state.keywords = result
            status.update(label="Analysis complete!", state="complete")
        else:
            st.error("Failed to get a response from Gemini API")
            status.update(label="Analysis failed", state="error")
        
        st.session_state.status = "Ready"

# Handle fetch button click
if fetch_button and url_input:
    if st.session_state.last_analyzed_url != url_input:
        with st.status("Fetching articles...") as status:
            st.session_state.status = "Processing"
            try:
                # Clear previous data
                for file in os.listdir(st.session_state.scraped_dir):
                    os.remove(os.path.join(st.session_state.scraped_dir, file))
                
                st.session_state.articles = []
                st.session_state.article_details = {}
                
                # Extract article links
                status.update(label="Extracting article links...", state="running")
                links = extract_article_links(url_input)
                
                if links:
                    # Save main page
                    status.update(label="Saving main page...", state="running")
                    main_page_path = os.path.join(st.session_state.scraped_dir, "main_page.pdf")
                    save_as_pdf(url_input, main_page_path)
                    
                    # Save articles with progress updates
                    max_articles = min(10, len(links))
                    for i in range(max_articles):
                        article_url = links[i]
                        article_filename = f"article_{i+1}_{os.path.basename(article_url)}.pdf"
                        article_path = os.path.join(st.session_state.scraped_dir, article_filename)
                        
                        status.update(label=f"Fetching article {i+1} of {max_articles}...", state="running")
                        save_as_pdf(article_url, article_path)
                        
                        # Extract title from filename for display
                        article_title = os.path.basename(article_url)
                        article_title = re.sub(r'\.html$|\.php$|\.asp$', '', article_title)
                        article_title = article_title.replace('-', ' ').replace('_', ' ')
                        article_title = ' '.join(word.capitalize() for word in article_title.split())
                        
                        # Initialize all articles as selected by default
                        st.session_state.article_details[i] = {
                            'title': article_title,
                            'url': article_url,
                            'selected': True
                        }
                        
                        time.sleep(1)  # Be nice to the server
                    
                    # Update session state
                    st.session_state.articles = links[:max_articles]
                    st.session_state.last_analyzed_url = url_input
                    status.update(label=f"Successfully fetched {max_articles} articles!", state="complete")
                    st.success(f"Successfully fetched {max_articles} articles!")
                    st.experimental_rerun()
                else:
                    st.error("No article links found on the provided URL")
                    status.update(label="No articles found", state="error")
            except Exception as e:
                st.error(f"Error fetching articles: {str(e)}")
                status.update(label=f"Error: {str(e)}", state="error")
            
            st.session_state.status = "Ready"
    else:
        st.info("Articles already fetched for this URL. Use 'Clear All' to start again.")

# Handle analyze button click
if analyze_button:
    analyze_articles()

# Handle clear button click
if clear_button:
    # Reset session state
    st.session_state.articles = []
    st.session_state.article_details = {}
    st.session_state.screenshot_path = None
    st.session_state.keywords = "No keywords found yet"
    st.session_state.last_analyzed_url = None
    
    # Clear files
    for file in os.listdir(st.session_state.scraped_dir):
        os.remove(os.path.join(st.session_state.scraped_dir, file))
    
    st.success("All data cleared!")
    st.experimental_rerun()

# Layout and display of articles with selection
def display_articles():
    if st.session_state.articles:
        for i, article in enumerate(st.session_state.articles):
            if i in st.session_state.article_details:
                details = st.session_state.article_details[i]
                title = details['title']
                selected = details['selected']
                
                col1, col2 = st.columns([9, 1])
                
                # Determine the CSS class based on selection state
                css_class = "article-item article-selected" if selected else "article-item"
                
                with col1:
                    st.markdown(f'<div class="{css_class}">{title}</div>', unsafe_allow_html=True)
                
                with col2:
                    if st.button("✓" if selected else "○", key=f"select_{i}"):
                        toggle_article_selection(i)
    else:
        st.markdown('<div style="padding: 20px; text-align: center;">No articles found. Enter a URL and click "Fetch Blog Articles".</div>', unsafe_allow_html=True)

# Display content in columns
with tab1:
    with content_col1:
        st.markdown("### Preview of the Website")
        preview_container = st.container()
        with preview_container:
            if url_input:
                st.markdown(f'<div class="url-preview">{url_input}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="url-preview">No URL provided yet. Enter a URL above and click "Fetch Blog Articles".</div>', unsafe_allow_html=True)

    with content_col2:
        st.markdown("### Blog Articles Found (Select to Analyze)")
        display_articles()

    with content_col3:
        st.markdown("### SEO Keywords Found")
        st.markdown('<div class="keyword-container">{}</div>'.format(st.session_state.keywords), unsafe_allow_html=True)
        if st.session_state.keywords != "No keywords found yet":
            copy_btn = st.button("Copy to Clipboard", key="copy_keywords")
            if copy_btn:
                st.success("Keywords copied to clipboard!")
                # In Streamlit Cloud, we need to use JavaScript for clipboard functionality
                st.components.v1.html(f"""
                <script>
                const text = `{st.session_state.keywords}`;
                navigator.clipboard.writeText(text)
                    .then(() => console.log('Copied!'))
                    .catch(err => console.error('Error copying text: ', err));
                </script>
                """, height=0)

# "How It Works" tab content
with tab2:
    st.header("How the SEO Keyword Extractor Works")
    
    st.markdown("""
    This tool helps you identify potential SEO keywords from blog content by:
    
    1. **Scraping Blog Content**: It fetches your blog's main page and individual articles
    2. **Content Conversion**: Converts HTML to clean text and saves as PDF
    3. **AI Analysis**: Uses Google's Gemini AI to identify long-tail keywords
    4. **Results Display**: Shows you a list of potential keywords to target
    
    ### Why Long-Tail Keywords?
    
    Long-tail keywords are specific phrases that visitors are more likely to use when they're closer to making a purchase or when they're using voice search. They often have less competition and higher conversion rates.
    
    ### Tips for Better Results
    
    - Use blogs with clear topics and well-structured content
    - Select articles that are thematically related for more coherent keywords
    - Compare results from different article selections to identify patterns
    """)

# Settings tab content
with tab3:
    st.header("Application Settings")
    
    st.warning("""
    **Important: API Key Required**
    
    This application requires a Google Gemini API key to function. 
    
    For Streamlit Cloud deployment:
    1. Get your API key from [Google MakerSuite](https://makersuite.google.com/app/apikey)
    2. Add it to your Streamlit secrets.toml file as:
       ```
       GEMINI_API_KEY = "your-api-key-here"
       ```
    
    For local development:
    1. Create a `.env` file in your project directory
    2. Add `GEMINI_API_KEY=your-api-key-here` to the file
    """)
    
    st.subheader("Analysis Settings")
    
    # Number of keywords to extract
    num_keywords = st.slider("Number of keywords to extract", min_value=3, max_value=15, value=8)
    
    # Temperature setting
    temperature = st.slider("AI creativity (temperature)", min_value=0.0, max_value=1.0, value=0.2, step=0.1)
    
    # Apply button
    if st.button("Apply Settings"):
        st.success("Settings applied successfully!")

# Cleanup function to be called when the app is closed
def cleanup():
    if hasattr(st.session_state, 'temp_dir') and os.path.exists(st.session_state.temp_dir):
        shutil.rmtree(st.session_state.temp_dir)

# Register cleanup function
import atexit
atexit.register(cleanup)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center;">
    Built with Streamlit, WebScrape, and Google Gemini AI • 
    <a href="https://github.com/yourusername/seo-keyword-extractor" target="_blank">GitHub</a>
</div>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501)