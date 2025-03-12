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

def summarize_articles(dataset: Dict[str, Dict[str, Union[List[str], str]]],
                      min_words: int = 100) -> Dict[str, Dict[str, str]]:
    """
    Summarize article content using extractive summarization based on DistilBERT embeddings.
    
    Args:
        dataset: Dictionary with structure {
            'base_url': {
                'article_url_1': [article_title, article_content],
                'article_url_2': 'Error message',
                ...
            }
        }
        min_words: Minimum number of words for the summary
        
    Returns:
        Dictionary with structure {base_url_0: {article_url_0: "summary text", ...}}
    """
    log_message("Starting article summarization")
    
    # Initialize DistilBERT processor
    try:
        bert = DistilBertProcessor()
    except Exception as e:
        log_message(f"Critical error initializing DistilBERT: {str(e)}")
        return {}
    
    summaries = {}
    total_articles = sum(len(articles) for articles in dataset.values())
    processed = 0
    
    def split_into_sentences(text):
        # Simple sentence splitting - handles common sentence endings
        text = re.sub(r'([.!?])\s+', r'\1SPLIT', text)
        sentences = text.split('SPLIT')
        return [s.strip() for s in sentences if s.strip()]
    
    for base_url, articles in dataset.items():
        log_message(f"Summarizing articles for base URL: {base_url} with {len(articles)} articles")
        summaries[base_url] = {}
        
        for article_url, content_data in articles.items():
            try:
                log_message(f"Summarizing article: {article_url}")
                
                # Handle error cases or missing content
                if isinstance(content_data, str) and content_data.startswith("Error"):
                    log_message(f"Skipping article with error: {content_data}")
                    summaries[base_url][article_url] = "Error: Could not summarize article"
                    continue
                
                # Extract title and content from the list
                if isinstance(content_data, list) and len(content_data) >= 2:
                    title = content_data[0]
                    content = content_data[1]
                else:
                    title = ""
                    content = str(content_data) if content_data else ""
                
                if not content.strip():
                    summaries[base_url][article_url] = "Error: No content to summarize"
                    continue
                
                # Split content into sentences
                sentences = split_into_sentences(content)
                
                if len(sentences) <= 3:
                    # If there are very few sentences, return the content as is
                    summary = content
                else:
                    # Get document embedding (using title and first paragraph)
                    first_para = ' '.join(sentences[:3])
                    doc_text = f"{title} {first_para}"
                    doc_embedding = bert.get_embedding(doc_text)
                    
                    # Score each sentence by similarity to document
                    sentence_scores = []
                    for i, sentence in enumerate(sentences):
                        # Skip very short sentences or sentences without alphabetic chars
                        if len(sentence.split()) < 3 or not re.search('[a-zA-Z]', sentence):
                            continue
                            
                        # Get embedding and calculate similarity
                        sent_embedding = bert.get_embedding(sentence)
                        similarity = bert.cosine_similarity(doc_embedding, sent_embedding)
                        
                        # Include position bias to favor earlier sentences
                        position_weight = 1.0 / (1 + 0.1 * i)
                        final_score = similarity * position_weight
                        
                        sentence_scores.append((i, sentence, final_score))
                    
                    # Sort by score
                    sentence_scores.sort(key=lambda x: x[2], reverse=True)
                    
                    # Select sentences until we reach minimum word count
                    selected_sentences = []
                    word_count = 0
                    
                    for i, sentence, _ in sentence_scores:
                        selected_sentences.append((i, sentence))
                        word_count += len(sentence.split())
                        
                        if word_count >= min_words:
                            break
                    
                    # Sort selected sentences by original position to maintain flow
                    selected_sentences.sort(key=lambda x: x[0])
                    
                    # Join sentences to form summary
                    summary = ' '.join(s[1] for s in selected_sentences)
                
                # Add title if available
                if title:
                    summary = f"{title}\n\n{summary}"
                
                # Store summary
                summaries[base_url][article_url] = summary
                log_message(f"Generated summary of {len(summary.split())} words for {article_url}")
            
            except Exception as e:
                log_message(f"Error summarizing article {article_url}: {str(e)}")
                summaries[base_url][article_url] = f"Error summarizing: {str(e)}"
            
            processed += 1
            if processed % 10 == 0:
                log_message(f"Progress: {processed}/{total_articles} articles summarized")
    
    log_message(f"Summarization completed. Processed {processed} articles.")
    return summaries

def generate_overall_summary(categorized_data: Dict[str, Dict[str, Dict[str, Union[List[str], str]]]]) -> str:
    """
    Generate a comprehensive summary of news data across all categories.
    
    Args:
        categorized_data: Dictionary with structure {
            category: {
                base_url: {
                    article_url: [title, content], 
                    ...
                },
                ...
            },
            ...
        }
        
    Returns:
        A string containing a ~1000-word summary with:
        - Executive summary
        - Key bullet points for each category
        - Important trends and patterns
        - Critical developments
    """
    log_message("Generating overall news data summary")
    
    try:
        # Initialize DistilBERT processor for text analysis
        bert = DistilBertProcessor()
        
        # Extract all article titles by category
        category_titles = {}
        category_stats = {}
        
        for category, base_urls in categorized_data.items():
            titles = []
            article_count = 0
            sources = set()
            
            for base_url, articles in base_urls.items():
                sources.add(base_url)
                for article_url, content_data in articles.items():
                    if isinstance(content_data, list) and len(content_data) >= 1:
                        title = content_data[0]
                        titles.append(title)
                        article_count += 1
            
            category_titles[category] = titles
            category_stats[category] = {
                "article_count": article_count,
                "sources": len(sources),
                "source_list": list(sources)
            }
            
            log_message(f"Extracted {len(titles)} titles from category: {category}")
        
        # Generate key bullet points for each category
        category_bullet_points = {}
        
        for category, titles in category_titles.items():
            if not titles:
                category_bullet_points[category] = ["No articles in this category"]
                continue
                
            # Join titles and extract key phrases
            combined_text = " ".join(titles[:50])  # Limit to 50 titles for processing
            
            # Use frequency and position to identify important terms
            words = re.findall(r'\b[a-zA-Z]{3,}\b', combined_text.lower())
            word_freq = {}
            
            for word in words:
                if word not in ['the', 'and', 'for', 'that', 'this', 'with', 'from', 'have']:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Get top topics based on frequency
            top_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            
            # Create bullet points based on titles containing top topics
            bullets = []
            for topic, _ in top_topics:
                relevant_titles = [t for t in titles if topic in t.lower()][:2]
                if relevant_titles:
                    bullet = f"{topic.title()}: " + " / ".join(relevant_titles)
                    bullets.append(bullet)
            
            # Ensure we have at least 3 bullet points
            if len(bullets) < 3 and len(titles) >= 3:
                for title in titles[:3-len(bullets)]:
                    bullets.append(title)
                    
            category_bullet_points[category] = bullets[:5]  # Limit to 5 bullet points
                
        # Find cross-category trends
        all_titles = []
        for titles in category_titles.values():
            all_titles.extend(titles)
            
        # Simple trend detection based on common phrases
        trend_phrases = {}
        for title in all_titles:
            # Extract 2-3 word phrases
            words = title.split()
            for i in range(len(words) - 1):
                phrase = " ".join(words[i:i+2]).lower()
                if len(phrase.split()) > 1:  # Ensure it's actually a phrase
                    trend_phrases[phrase] = trend_phrases.get(phrase, 0) + 1
        
        # Get top trends
        trends = [phrase for phrase, count in sorted(trend_phrases.items(), 
                                                    key=lambda x: x[1], reverse=True)
                 if count > 1 and len(phrase.split()) > 1][:10]
        
        # Identify critical developments (articles with high engagement across categories)
        critical_developments = []
        
        # Build the overall summary
        total_articles = sum(stats["article_count"] for stats in category_stats.values())
        total_sources = len(set().union(*[set(stats["source_list"]) for stats in category_stats.values()]))
        
        # Create executive summary
        exec_summary = f"""
        This summary analyzes {total_articles} articles from {total_sources} different sources across {len(category_stats)} categories.
        The data shows that {max(category_stats.items(), key=lambda x: x[1]['article_count'])[0]} is the most active category with {max(category_stats.values(), key=lambda x: x['article_count'])['article_count']} articles.
        Key themes emerging across categories include {', '.join(trends[:3]) if trends else 'no consistent themes'}.
        """
        
        # Format final output
        summary_parts = []
        
        # Executive Summary
        summary_parts.append("# EXECUTIVE SUMMARY\n")
        summary_parts.append(exec_summary.strip())
        summary_parts.append("\n")
        
        # Key bullet points by category
        summary_parts.append("# KEY POINTS BY CATEGORY\n")
        for category, bullets in category_bullet_points.items():
            summary_parts.append(f"## {category} ({category_stats[category]['article_count']} articles)")
            for bullet in bullets:
                summary_parts.append(f"• {bullet}")
            summary_parts.append("")
        
        # Important trends
        summary_parts.append("# IMPORTANT TRENDS AND PATTERNS\n")
        for i, trend in enumerate(trends[:7], 1):
            summary_parts.append(f"{i}. {trend.title()}")
        summary_parts.append("")
        
        # Critical developments
        summary_parts.append("# CRITICAL DEVELOPMENTS\n")
        if not critical_developments:
            # If no specific critical developments identified, use top titles from largest category
            top_category = max(category_stats.items(), key=lambda x: x[1]['article_count'])[0]
            if category_titles[top_category]:
                for title in category_titles[top_category][:3]:
                    summary_parts.append(f"• {title}")
        else:
            for dev in critical_developments:
                summary_parts.append(f"• {dev}")
                
        # Concatenate all parts
        final_summary = "\n".join(summary_parts)
        
        log_message(f"Generated overall summary of {len(final_summary.split())} words")
        return final_summary
    
    except Exception as e:
        log_message(f"Error generating overall summary: {str(e)}")
        return f"Error generating summary: {str(e)}"
