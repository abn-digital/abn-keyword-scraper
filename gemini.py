import google.generativeai as genai
import os
from pathlib import Path
import mimetypes
import time
import requests.exceptions
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable or Streamlit secrets
def get_api_key():
    # First check for secret in Streamlit secrets
    if hasattr(st, 'secrets') and 'GEMINI_API_KEY' in st.secrets:
        return st.secrets['GEMINI_API_KEY']
    
    # Then check for environment variable
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # If API key is not found, provide clear instructions
    if not api_key:
        st.error("""
        ⚠️ No API key found. Please set your GEMINI_API_KEY using one of these methods:
        
        1. For local development: Create a .env file with GEMINI_API_KEY=your_key
        2. For Streamlit Cloud: Add GEMINI_API_KEY to your app secrets
        
        Get your API key from: https://makersuite.google.com/app/apikey
        """)
        return None
    
    return api_key

# Configure Gemini API
def initialize_genai():
    api_key = get_api_key()
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

def get_file_mimetype(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        if file_path.lower().endswith('.pdf'):
            return 'application/pdf'
        return 'application/octet-stream'
    return mime_type

def get_all_files_from_directory(directory_path):
    files_list = []
    dir_path = Path(directory_path)
    
    if not dir_path.exists():
        st.error(f"Error: Directory {directory_path} does not exist.")
        return files_list
    
    if not dir_path.is_dir():
        st.error(f"Error: {directory_path} is not a directory.")
        return files_list
    
    for file_path in dir_path.glob('*'):
        if file_path.is_file():
            files_list.append(str(file_path))
    
    return files_list

def prepare_files(file_paths):
    files = []
    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            st.warning(f"Warning: File {file_path} not found, skipping.")
            continue
            
        mime_type = get_file_mimetype(file_path)
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                
            files.append({
                "data": content,
                "mime_type": mime_type
            })
        except Exception as e:
            st.error(f"Error reading file {file_path}: {e}")
    
    return files

def call_gemini_api(prompt, file_paths, model_name="gemini-2.0-flash-lite"):
    try:
        # Make sure the API is initialized
        if not initialize_genai():
            return "Unable to initialize Gemini API. Please check your API key."
            
        # Process files in smaller batches if there are many
        if len(file_paths) > 5:
            # Process only the main page and a few articles
            file_paths = file_paths[:5]  # Take only the first 5 files
            st.info(f"Processing only the first 5 files to avoid timeout issues.")
        
        files = prepare_files(file_paths)
        
        if not files:
            raise ValueError("No valid files to process")
        
        st.info(f"Analyzing {len(files)} files with Gemini AI...")
        
        model = genai.GenerativeModel(model_name)
        
        # Prepare the request
        request_content = [
            {
                "parts": [
                    {"text": prompt},
                    *[{"inline_data": file} for file in files]
                ]
            }
        ]
        
        # Set generation config with reasonable parameters
        generation_config = {
            "temperature": 0.2,  # Lower temperature for more deterministic results
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 1024,  # Limit output size
        }
        
        # Call the API with retries
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    contents=request_content,
                    generation_config=generation_config
                )
                return response.text
            
            except requests.exceptions.Timeout as e:
                st.warning(f"Timeout error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise
            
            except Exception as e:
                st.warning(f"API error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
        
    except Exception as e:
        st.error(f"Error calling Gemini API: {e}")
        return None

if __name__ == "__main__":
    print("This module is designed to be imported, not run directly.")