import torch
from transformers import DistilBertTokenizer, DistilBertModel
import re
import numpy as np
from typing import Dict, List, Any, Union, Tuple
from datetime import datetime
import os
import sys

# Add parent directory to path to import logging_scripts
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from model_api.logging_scripts import create_log_file, append_to_log

# Initialize log file
log_filename = f"hugging_face_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
create_log_file(log_filename)

def log_message(message):
    """Helper function to log messages with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    append_to_log(log_filename, log_entry)
    print(log_entry)  # Also print to console

class DistilBertProcessor:
    def __init__(self):
        """Initialize DistilBERT model with CUDA if available."""
        log_message("Initializing DistilBERT model")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        log_message(f"Using device: {self.device}")
        
        # Load tokenizer and model
        try:
            self.tokenizer = DistilBertTokenizer.from_pretrained('distilbert-base-uncased')
            self.model = DistilBertModel.from_pretrained('distilbert-base-uncased').to(self.device)
            log_message("DistilBERT model loaded successfully")
        except Exception as e:
            log_message(f"Error loading DistilBERT model: {str(e)}")
            raise
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Convert text to embedding vector using DistilBERT."""
        try:
            # Handle empty text
            if not text.strip():
                return np.zeros(768)  # Return zero vector for empty text
                
            # Truncate long text to prevent tokenizer overflow
            max_length = 512
            if len(text.split()) > max_length:
                text = ' '.join(text.split()[:max_length])
                
            # Tokenize and get embeddings
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
            
            # Use [CLS] token embedding as sentence representation
            embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            return embeddings[0]
        except Exception as e:
            log_message(f"Error generating embedding: {str(e)}")
            return np.zeros(768)  # Return zeros if embeddings fail
    
    def cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0
            
        return np.dot(embedding1, embedding2) / (norm1 * norm2)
    
    def extract_url_keywords(self, url: str) -> str:
        """Extract meaningful keywords from URL."""
        # Remove protocol and common prefixes
        url = re.sub(r'https?://(www\.)?', '', url)
        # Remove file extensions and query params
        url = re.sub(r'\.(html|php|aspx).*$', '', url)
        # Replace non-alphanumeric characters with spaces
        url = re.sub(r'[^a-zA-Z0-9]', ' ', url)
        # Split into words
        return ' '.join(word for word in url.split() if len(word) > 1)

def check_url_content_relevance(dataset: Dict[str, Dict[str, Union[List[str], str]]], 
                              threshold: float = 0.4) -> Dict[str, Dict[str, int]]:
    """
    Check relevance between article URLs and their content using DistilBERT.
    
    Args:
        dataset: Dictionary with structure {
            'base_url': {
                'article_url_1': [article_title, article_content],
                'article_url_2': 'Error message',
                ...
            }
        }
        threshold: Similarity threshold to determine relevance (between 0 and 1)
        
    Returns:
        Dictionary with structure {base_url_0: {article_url_0: 1, article_url_1: 0, ...}}
    """
    log_message("Starting relevance check for dataset")
    
    # Initialize DistilBERT processor
    try:
        bert = DistilBertProcessor()
    except Exception as e:
        log_message(f"Critical error initializing DistilBERT: {str(e)}")
        return {}
    
    results = {}
    total_articles = sum(len(articles) for articles in dataset.values())
    processed = 0
    
    for base_url, articles in dataset.items():
        log_message(f"Processing base URL: {base_url} with {len(articles)} articles")
        results[base_url] = {}
        
        for article_url, content_data in articles.items():
            log_message(f"Processing article: {article_url}")
            
            try:
                # Handle error cases or missing content
                if isinstance(content_data, str) and content_data.startswith("Error"):
                    log_message(f"Skipping article with error: {content_data}")
                    results[base_url][article_url] = 0  # Mark as not relevant
                    continue
                
                # Extract title and content from the list
                if isinstance(content_data, list) and len(content_data) >= 2:
                    title = content_data[0]
                    content = content_data[1]
                else:
                    title = ""
                    content = str(content_data) if content_data else ""
                
                # Extract keywords from URL
                url_keywords = bert.extract_url_keywords(article_url)
                
                # Combine title and content (limited for efficiency)
                article_text = f"{title} {content[:500]}" if content else title
                
                # Get embeddings
                url_embedding = bert.get_embedding(url_keywords)
                article_embedding = bert.get_embedding(article_text)
                
                # Calculate similarity
                similarity = bert.cosine_similarity(url_embedding, article_embedding)
                
                # Determine relevance
                is_relevant = int(similarity > threshold)
                results[base_url][article_url] = is_relevant
                
                log_message(f"Article {article_url} relevance: {is_relevant} (similarity: {similarity:.4f})")
            except Exception as e:
                log_message(f"Error processing article {article_url}: {str(e)}")
                results[base_url][article_url] = 0  # Default to not relevant in case of error
            
            processed += 1
            if processed % 10 == 0:
                log_message(f"Progress: {processed}/{total_articles} articles processed")
    
    log_message(f"Relevance check completed. Processed {processed} articles.")
    return results

def categorize_content(dataset: Dict[str, Dict[str, Union[List[str], str]]], 
                     categories: Dict[str, List[str]]) -> Dict[str, Dict[str, Dict[str, Union[List[str], str]]]]:
    """
    Categorize articles from dataset into provided categories using DistilBERT.
    
    Args:
        dataset: Dictionary with structure {
            'base_url': {
                'article_url_1': [article_title, article_content],
                'article_url_2': 'Error message',
                ...
            }
        }
        categories: Dictionary with structure {"Politics": [], "Business": []}
        
    Returns:
        Dictionary with structure {cat_0: {base_url_0: {article_url_0: [title, content]}, ...}, cat_1: {...}}
    """
    log_message("Starting content categorization")
    
    # Initialize DistilBERT processor
    try:
        bert = DistilBertProcessor()
    except Exception as e:
        log_message(f"Critical error initializing DistilBERT: {str(e)}")
        return {}
    
    # Initialize results dictionary
    categorized_results = {cat: {} for cat in categories}
    total_articles = sum(len(articles) for articles in dataset.values())
    processed = 0
    
    # Prepare category embeddings
    log_message("Generating category embeddings")
    category_embeddings = {}
    for category, keywords in categories.items():
        if keywords:
            # If keywords provided, use them
            category_text = ' '.join(keywords)
        else:
            # Otherwise just use the category name
            category_text = category
            
        category_embeddings[category] = bert.get_embedding(category_text)
        log_message(f"Generated embedding for category: {category}")
    
    # Process each article
    for base_url, articles in dataset.items():
        for article_url, content_data in articles.items():
            try:
                log_message(f"Categorizing article: {article_url}")
                
                # Handle error cases or missing content
                if isinstance(content_data, str) and content_data.startswith("Error"):
                    log_message(f"Skipping article with error: {content_data}")
                    continue
                
                # Extract title and content from the list
                if isinstance(content_data, list) and len(content_data) >= 2:
                    title = content_data[0]
                    content = content_data[1]
                else:
                    title = ""
                    content = str(content_data) if content_data else ""
                
                # Combine title and content
                article_text = f"{title} {content[:1000]}" if content else title
                
                # Get article embedding
                article_embedding = bert.get_embedding(article_text)
                
                # Find best matching category
                best_category = None
                best_similarity = -1
                
                for category, cat_embedding in category_embeddings.items():
                    similarity = bert.cosine_similarity(article_embedding, cat_embedding)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_category = category
                
                # Add article to best matching category
                if best_category:
                    if base_url not in categorized_results[best_category]:
                        categorized_results[best_category][base_url] = {}
                    
                    categorized_results[best_category][base_url][article_url] = content_data
                    log_message(f"Article {article_url} categorized as '{best_category}' with similarity {best_similarity:.4f}")
                
            except Exception as e:
                log_message(f"Error categorizing article {article_url}: {str(e)}")
            
            processed += 1
            if processed % 10 == 0:
                log_message(f"Progress: {processed}/{total_articles} articles categorized")
    
    # Log category statistics
    for category, data in categorized_results.items():
        article_count = sum(len(articles) for articles in data.values())
        log_message(f"Category '{category}' has {article_count} articles")
    
    log_message(f"Categorization completed. Processed {processed} articles.")
    return categorized_results
