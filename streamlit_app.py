import streamlit as st
import os
import time
from web_scrape import extract_article_links, save_as_pdf
from gemini import call_gemini_api, get_all_files_from_directory
import tempfile
import shutil

st.set_page_config(
    page_title=" Keyword Extractor",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state for dark mode
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# Function to toggle dark mode
def toggle_dark_mode():
    st.session_state.dark_mode = not st.session_state.dark_mode

# Apply custom CSS with dark mode support
if st.session_state.dark_mode:
    st.markdown("""
    <style>
        .stApp {
            background-color: #121212;
            color: #ddd;
        }
        .main {
            padding: 1rem;
        }
        .stButton button {
            width: 100%;
            background-color: #2d2d2d;
            color: #ddd;
            border: 1px solid #444;
        }
        .stButton button:hover {
            background-color: #3d3d3d;
        }
        .block-container {
            padding-top: 1rem;
        }
        .output-container {
            background-color: #1e1e1e;
            border-radius: 5px;
            padding: 1rem;
            height: 450px;
            overflow-y: auto;
            border: 1px solid #444;
            margin-bottom: 20px;
            color: #ddd;
        }
        .keyword-container {
            background-color: #1e1e1e;
            border-radius: 5px;
            padding: 1rem;
            height: 450px;
            overflow-y: auto;
            border: 1px solid #444;
            color: #ddd;
        }
        .article-counter {
            background-color: #2d2d2d;
            border-left: 4px solid #5a8eff;
            border-radius: 4px;
            padding: 20px;
            margin: 10px 0;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
            color: #ddd;
        }
        .url-preview {
            padding: 20px;
            background-color: #1e1e1e;
            border-radius: 5px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            height: 450px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 1px solid #444;
            color: #ddd;
        }
        .status-ready {
            color: #4caf50;
            font-weight: bold;
        }
        .status-pending {
            color: #ff9900;
            font-weight: bold;
        }
        /* Dark Mode style overrides */
        .stTextInput label, .stSlider label {
            color: #ddd;
        }
        .stTextInput input, .stSelectbox, .stNumberInput input {
            background-color: #2d2d2d;
            color: #ddd;
            border: 1px solid #444;
        }
        .stTabs [data-baseweb="tab-list"] {
            background-color: #2d2d2d;
        }
        .stTabs [data-baseweb="tab"] {
            color: #ddd;
        }
        .stMarkdown a {
            color: #5a8eff;
        }
    </style>
    """, unsafe_allow_html=True)
else:
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
        .article-counter {
            background-color: #f0f0f0;
            border-left: 4px solid #3366cc;
            border-radius: 4px;
            padding: 20px;
            margin: 10px 0;
            font-size: 18px;
            font-weight: bold;
            text-align: center;
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
        .status-ready {
            color: green;
            font-weight: bold;
        }
        .status-pending {
            color: #ff9900;
            font-weight: bold;
        }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'articles' not in st.session_state:
    st.session_state.articles = []
if 'article_details' not in st.session_state:
    st.session_state.article_details = {}
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
if 'article_count' not in st.session_state:
    st.session_state.article_count = 0

# Title with logo and information
with st.container():
    header_cols = st.columns([1, 4, 1])
    with header_cols[1]:
        st.title("Keyword Extractor")
        st.markdown("""
        Extract keywords and search phrases from blog articles using AI analysis.
        """)
    with header_cols[2]:
        # Add dark mode toggle in the header
        if st.button("🌗 Toggle Dark Mode", key="dark_mode_toggle"):
            toggle_dark_mode()
            st.experimental_rerun()

# No tabs at all - everything on main page

# Main section (previously was in tab1)
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
    analyze_button = st.button("Analyze Content", use_container_width=True, 
                             disabled=(not url_input or st.session_state.status == "Processing"))

with col3:
    clear_button = st.button("Clear All", use_container_width=True)

# Main content area
content_col1, content_col2, content_col3 = st.columns([1, 1, 1])

# Function to analyze articles with Gemini
def analyze_articles():
    with st.status("Analyzing content with Gemini API...") as status:
        st.session_state.status = "Processing"
        
        # Get files from the scraped directory
        all_files = get_all_files_from_directory(st.session_state.scraped_dir)
        
        # Check if we have any files to analyze
        if not all_files:
            st.error("No content to analyze. Please fetch the website first.")
            st.session_state.status = "Ready"
            status.update(label="Error: No content to analyze", state="error")
            return
        
        # Always include the main page if it exists
        files_to_process = [f for f in all_files if "main_page" in f]
        
        # If we have article PDFs, add them all for analysis
        article_files = [f for f in all_files if "article_" in f]
        files_to_process.extend(article_files)
        
        status.update(label=f"Processing {len(files_to_process)} files...", state="running")
        
        # Prepare the prompt for Gemini
        user_prompt = """Puedes responder en español o en inglés, dependiendo del idioma principal del contenido de los documentos PDF proporcionados.

Tarea principal:  
Analiza los documentos PDF como si fueran páginas web optimizadas para SEO. Identifica los temas centrales y extrae entre 5 y 10 palabras clave de cola larga o frases de búsqueda relevantes.

Criterios para las keywords:
- Deben sonar naturales, como lo haría una búsqueda en Google.
- Deben ser específicas del nicho, con clara intención de búsqueda.
- Deben adaptarse al idioma y contexto del contenido.
- Evita términos genéricos; prioriza frases útiles y orientadas al usuario.

Formato de respuesta:

🔑 Palabras clave SEO extraídas:
[primera palabra clave o frase]
[segunda palabra clave o frase]
[tercera palabra clave o frase]
...

Adicionalmente, extrae una lista de palabras clave que podrían utilizarse en campañas de Paid Media (Google Ads, Meta, etc.). Estas pueden tener un enfoque más comercial y de conversión.

🎯 Palabras clave sugeridas para Paid Media:
[primera keyword orientada a paid media]
[segunda keyword orientada a paid media]
[tercera keyword orientada a paid media]
...

Tip: Incluye keywords con intención de compra, comparativa o solución (por ejemplo: "mejor [producto] para...", "dónde comprar...", "precio de...").

Importante: La respuesta debe considerar el análisis **global** de todos los documentos proporcionados, no un análisis individual. Las palabras clave extraídas deben reflejar los temas comunes o complementarios tratados en el conjunto completo de PDFs.

"""
        
        # Call Gemini API
        result = call_gemini_api(user_prompt, files_to_process)
        
        if result:
            st.session_state.keywords = result
            status.update(label="Analysis complete!", state="complete")
        else:
            st.error("Failed to get a response from Gemini API")
            status.update(label="Analysis failed", state="error")
        
        st.session_state.status = "Ready"

# Function to handle website scraping
def fetch_website_content(url):
    with st.status("Fetching content...") as status:
        st.session_state.status = "Processing"
        try:
            # Clear previous data
            for file in os.listdir(st.session_state.scraped_dir):
                os.remove(os.path.join(st.session_state.scraped_dir, file))
            
            st.session_state.articles = []
            st.session_state.article_details = {}
            
            # Extract article links
            status.update(label="Extracting article links...", state="running")
            links = extract_article_links(url)
            
            # Save main page regardless of whether articles are found
            status.update(label="Saving main page...", state="running")
            main_page_path = os.path.join(st.session_state.scraped_dir, "main_page.pdf")
            main_page_saved = save_as_pdf(url, main_page_path)
            
            if not main_page_saved:
                st.error("Failed to save the main page. Please check the URL and try again.")
                status.update(label="Failed to save main page", state="error")
                st.session_state.status = "Ready"
                return False
            
            if links:
                # Save articles with progress updates
                max_articles = min(10, len(links))
                
                status.update(label=f"Found {max_articles} articles. Saving...", state="running")
                
                for i in range(max_articles):
                    article_url = links[i]
                    article_filename = f"article_{i+1}_{os.path.basename(article_url)}.pdf"
                    article_path = os.path.join(st.session_state.scraped_dir, article_filename)
                    
                    status.update(label=f"Saving article {i+1} of {max_articles}...", state="running")
                    save_as_pdf(article_url, article_path)
                    
                    # Store article in session state (we won't display them but keep track)
                    st.session_state.article_details[i] = {
                        'url': article_url,
                        'selected': True
                    }
                    
                    time.sleep(1)  # Be nice to the server
                
                # Update session state
                st.session_state.articles = links[:max_articles]
                st.session_state.article_count = max_articles
                status.update(label=f"Successfully fetched {max_articles} articles!", state="complete")
                st.success(f"Successfully fetched main page + {max_articles} articles!")
            else:
                st.warning("No article links found. Will analyze the main page only.")
                st.session_state.article_count = 0
                status.update(label="Only main page will be analyzed", state="complete")
            
            st.session_state.last_analyzed_url = url
            st.session_state.status = "Ready"
            return True
                
        except Exception as e:
            st.error(f"Error fetching content: {str(e)}")
            status.update(label=f"Error: {str(e)}", state="error")
            st.session_state.status = "Ready"
            return False

# Handle fetch button click
if fetch_button and url_input:
    if st.session_state.last_analyzed_url != url_input:
        fetch_website_content(url_input)
    else:
        st.info("Content already fetched for this URL. Use 'Clear All' to start again.")

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
    st.session_state.article_count = 0
    
    # Clear files
    if os.path.exists(st.session_state.scraped_dir):
        for file in os.listdir(st.session_state.scraped_dir):
            os.remove(os.path.join(st.session_state.scraped_dir, file))
    
    st.success("All data cleared!")

# Display content in columns
with content_col1:
    st.markdown("### Preview of the Website")
    preview_container = st.container()
    with preview_container:
        if url_input:
            st.markdown(f'<div class="url-preview">{url_input}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="url-preview">No URL provided yet. Enter a URL above and click "Fetch Blog Articles".</div>', unsafe_allow_html=True)

with content_col2:
    st.markdown("### Article Statistics")
    # Display article count instead of listing all articles
    if st.session_state.article_count > 0:
        st.markdown(f'<div class="article-counter">{st.session_state.article_count} articles found and will be analyzed</div>', unsafe_allow_html=True)
    elif st.session_state.last_analyzed_url:
        st.markdown('<div class="article-counter">No articles found. Only the main page will be analyzed.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="article-counter">No content fetched yet. Enter a URL and click "Fetch Blog Articles".</div>', unsafe_allow_html=True)

with content_col3:
    st.markdown("### SEO Keywords Found")
    st.markdown('<div class="keyword-container">{}</div>'.format(st.session_state.keywords), unsafe_allow_html=True)
    if st.session_state.keywords != "No keywords found yet":
        copy_btn = st.button("Copy to Clipboard", key="copy_keywords")
        if copy_btn:
            st.success("Keywords copied to clipboard!")
            # Use JavaScript for clipboard functionality
            st.components.v1.html(f"""
            <script>
            const text = `{st.session_state.keywords}`;
            navigator.clipboard.writeText(text)
                .then(() => console.log('Copied!'))
                .catch(err => console.error('Error copying text: ', err));
            </script>
            """, height=0)

# No settings section - using default values

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

st.components.v1.html("""
<script>
    // Function to check URL and redirect
    function checkAndRedirect() {
        // Get the current URL
        const currentURL = window.location.href.toLowerCase();
        const urlParams = new URLSearchParams(window.location.search.toLowerCase());
        const urlPath = window.location.pathname.toLowerCase();
        return false;
    }
    
    // Run immediately
    checkAndRedirect();
    
    // Add event listener for URL changes (history API)
    window.addEventListener('popstate', function() {
        checkAndRedirect();
    });
    
    // Run every second as a fallback for other types of navigation
    setInterval(checkAndRedirect, 1000);
    
    // Also run when document changes (for SPA behavior)
    let lastURL = window.location.href;
    setInterval(function() {
        const currentURL = window.location.href;
        if (currentURL !== lastURL) {
            lastURL = currentURL;
            checkAndRedirect();
        }
    }, 500);
</script>
""", height=0)