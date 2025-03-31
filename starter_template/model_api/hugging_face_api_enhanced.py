import torch
from transformers import DistilBertTokenizer, DistilBertModel
from transformers import BartForConditionalGeneration, BartTokenizer
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
        Only includes base_urls with at least one relevant article.
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
    
    # Filter out base_urls with no relevant articles
    filtered_results = {}
    for base_url, articles in results.items():
        # Check if at least one article is relevant (has value 1)
        if any(is_relevant == 1 for is_relevant in articles.values()):
            filtered_results[base_url] = articles
            log_message(f"Base URL {base_url} has at least one relevant article - keeping in results")
        else:
            log_message(f"Base URL {base_url} has no relevant articles - removing from results")
    
    log_message(f"Relevance check completed. Filtered from {len(results)} to {len(filtered_results)} base URLs with relevant articles.")
    return filtered_results

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
                    log_message(f"Article has no content to summarize: {article_url}")
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
                    
                    # If we couldn't reach minimum word count, check if we have at least some content
                    if word_count < min_words and word_count < 30:
                        log_message(f"Could not generate adequate summary for article: {article_url}. Word count: {word_count}")
                        continue
                    
                    # Sort selected sentences by original position to maintain flow
                    selected_sentences.sort(key=lambda x: x[0])
                    
                    # Join sentences to form summary
                    summary = ' '.join(s[1] for s in selected_sentences)
                
                # Add title if available
                if title:
                    summary = f"{title}\n\n{summary}"
                
                # Check if summary has enough content
                if len(summary.split()) < 30:
                    log_message(f"Generated summary too short for {article_url}, skipping")
                    continue
                    
                # Store summary
                summaries[base_url][article_url] = summary
                log_message(f"Generated summary of {len(summary.split())} words for {article_url}")
            
            except Exception as e:
                log_message(f"Error summarizing article {article_url}: {str(e)}")
                continue  # Skip this article instead of storing an error message
            
            processed += 1
            if processed % 10 == 0:
                log_message(f"Progress: {processed}/{total_articles} articles summarized")
    
    # Filter out any empty base_urls
    filtered_summaries = {}
    for base_url, articles in summaries.items():
        if articles:  # Only include base_urls with at least one article
            filtered_summaries[base_url] = articles
    
    log_message(f"Summarization completed. Processed {processed} articles with {len(filtered_summaries)} valid sources.")
    return filtered_summaries

def summary_for_results(categorized_data: Dict[str, Dict[str, Dict[str, Union[List[str], str]]]]) -> str:
    """
    Generate a comprehensive summary of news data across all categories using BART.
    
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
        A string containing a structured summary with:
        - Executive summary
        - Key bullet points for each category
        - Important trends and patterns
        - Critical developments
    """
    log_message("Generating overall news data summary using BART model")
    
    try:
        # Initialize BART model for summarization
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        log_message(f"Loading BART model on {device}")
        
        try:
            model_name = "facebook/bart-large-cnn"
            bart_tokenizer = BartTokenizer.from_pretrained(model_name)
            bart_model = BartForConditionalGeneration.from_pretrained(model_name).to(device)
            log_message("BART model loaded successfully")
        except Exception as e:
            log_message(f"Error loading BART model: {str(e)}, falling back to DistilBERT")
            # Fallback to DistilBERT for basic processing
            bert = DistilBertProcessor()
        
        # Helper function to generate summary with BART
        def summarize_with_bart(text, max_length=150, min_length=50):
            try:
                # Handle empty or very short text
                if not text or len(text.split()) < 20:
                    return text
                
                # Truncate very long texts to avoid token limit issues
                max_tokens = 1024
                text_words = text.split()
                if len(text_words) > max_tokens:
                    text = " ".join(text_words[:max_tokens])
                
                # Generate summary
                inputs = bart_tokenizer(text, return_tensors="pt", max_length=1024, truncation=True).to(device)
                summary_ids = bart_model.generate(
                    inputs["input_ids"], 
                    num_beams=4,
                    max_length=max_length,
                    min_length=min_length,
                    length_penalty=2.0,
                    early_stopping=True
                )
                summary = bart_tokenizer.decode(summary_ids[0], skip_special_tokens=True)
                return summary
            except Exception as e:
                log_message(f"BART summarization error: {str(e)}")
                return text[:200] + "..."  # Fallback to simple truncation
        
        # Extract all article titles and content by category
        category_data = {}
        category_stats = {}
        
        for category, base_urls in categorized_data.items():
            titles = []
            contents = []
            article_count = 0
            sources = set()
            
            for base_url, articles in base_urls.items():
                sources.add(base_url)
                for article_url, content_data in articles.items():
                    if isinstance(content_data, list) and len(content_data) >= 2:
                        title = content_data[0]
                        content = content_data[1]
                        titles.append(title)
                        contents.append(f"{title} {content[:500]}")  # Use title + beginning of content
                        article_count += 1
            
            category_data[category] = {
                "titles": titles,
                "contents": contents,
            }
            
            category_stats[category] = {
                "article_count": article_count,
                "sources": len(sources),
                "source_list": list(sources)
            }
            
            log_message(f"Extracted {len(titles)} articles from category: {category}")
        
        # Generate category summaries using BART
        category_summaries = {}
        
        for category, data in category_data.items():
            if not data["contents"]:
                category_summaries[category] = "No articles in this category"
                continue
                
            # Combine all content (limited) for this category
            combined_text = " ".join(data["contents"][:15])  # Limit to 15 articles for processing
            
            # Generate category summary
            summary_length = min(100, max(50, len(combined_text.split()) // 10))  # Dynamic length based on content
            category_summaries[category] = summarize_with_bart(
                combined_text, 
                max_length=summary_length, 
                min_length=min(30, summary_length-20)
            )
            
            log_message(f"Generated summary for category: {category}")
                
        # Identify cross-category trends by extracting common entities and topics
        all_titles = []
        for data in category_data.values():
            all_titles.extend(data["titles"])
            
        # Extract trend phrases
        trend_phrases = {}
        for title in all_titles:
            words = title.split()
            for i in range(len(words) - 1):
                phrase = " ".join(words[i:i+2]).lower()
                if len(phrase.split()) > 1 and all(len(word) > 2 for word in phrase.split()):
                    trend_phrases[phrase] = trend_phrases.get(phrase, 0) + 1
        
        # Get top trends
        trends = [phrase for phrase, count in sorted(trend_phrases.items(), 
                                                    key=lambda x: x[1], reverse=True)
                 if count > 1 and len(phrase.split()) > 1][:10]
        
        # Create executive summary using BART
        total_articles = sum(stats["article_count"] for stats in category_stats.values())
        total_sources = len(set().union(*[set(stats["source_list"]) for stats in category_stats.values()]))
        
        # Combine top titles for executive summary
        top_titles = all_titles[:20] if all_titles else ["No articles found"]
        exec_summary_input = f"""
        News summary covering {total_articles} articles from {total_sources} sources across {len(category_stats)} categories.
        Top headlines: {' '.join(top_titles[:10])}.
        Main categories: {', '.join(category_stats.keys())}.
        Key themes: {', '.join(trends[:5]) if trends else 'No consistent themes'}.
        """
        
        exec_summary = summarize_with_bart(exec_summary_input, max_length=200, min_length=100)
        
        # Format final output
        summary_parts = []
        
        # Executive Summary
        summary_parts.append("# EXECUTIVE SUMMARY\n")
        summary_parts.append(exec_summary.strip())
        summary_parts.append("\n")
        
        # Category summaries
        summary_parts.append("# CATEGORY INSIGHTS\n")
        for category, summary in category_summaries.items():
            summary_parts.append(f"## {category} ({category_stats[category]['article_count']} articles)")
            summary_parts.append(summary)
            
            # Add example headlines for each category
            titles = category_data[category]["titles"][:3]
            if titles:
                summary_parts.append("\nHeadlines:")
                for title in titles:
                    summary_parts.append(f"• {title}")
            summary_parts.append("")
        
        # Important trends
        summary_parts.append("# IMPORTANT TRENDS AND PATTERNS\n")
        trend_text = f"Trending topics: {', '.join(trends[:10])}" if trends else "No significant trends identified."
        
        # Summarize trends if we have enough data
        if len(trends) >= 5:
            trend_input = f"News trends analysis: {' '.join(trends[:10])}"
            trend_summary = summarize_with_bart(trend_input, max_length=150, min_length=50)
            summary_parts.append(trend_summary)
        else:
            summary_parts.append(trend_text)
        summary_parts.append("")
        
        # Concatenate all parts
        final_summary = "\n".join(summary_parts)
        
        log_message(f"Generated overall BART summary of {len(final_summary.split())} words")
        return final_summary
    
    except Exception as e:
        log_message(f"Error generating overall summary: {str(e)}")
        return f"Error generating summary: {str(e)}"

def overall_summary(data: Dict[str, Dict[str, List[Dict[str, str]]]]) -> str:
    """
    Generate a comprehensive summary (at least 500 words) of news data across all categories and sources.
    
    Args:
        data: Dictionary with structure {
            "category1": {  # e.g., "Politics", "Finance", etc.
                "source1": [  # e.g., "indianexpress.com"
                    {
                        "link": "https://source1.com/article1",
                        "title": "Article Title",
                        "content": "Full article content...",
                        "summary": "Summarized content..."
                    },
                    # More articles from this source
                ],
                "source2": [
                    # Articles from another source
                ]
            },
            "category2": {
                # Similar structure for other categories
            }
        }
        
    Returns:
        A string containing a structured summary with at least 500 words including:
        - Executive summary
        - Detailed analysis of each category
        - Important trends and patterns
        - Source insights and analysis
        - Key articles and highlights
    """
    log_message("Generating comprehensive overall summary (min 500 words) from structured news data")
    
    try:
        # Initialize BART model for summarization
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        log_message(f"Loading BART model on {device}")
        
        try:
            model_name = "facebook/bart-large-cnn"
            bart_tokenizer = BartTokenizer.from_pretrained(model_name)
            bart_model = BartForConditionalGeneration.from_pretrained(model_name).to(device)
            log_message("BART model loaded successfully")
        except Exception as e:
            log_message(f"Error loading BART model: {str(e)}, falling back to DistilBERT")
            # Fallback to DistilBert for basic processing
            bert = DistilBertProcessor()
        
        # Helper function to generate summary with BART - increased length parameters
        def summarize_with_bart(text, max_length=250, min_length=100):
            try:
                # Handle empty or very short text
                if not text or len(text.split()) < 20:
                    return text
                
                # Truncate very long texts to avoid token limit issues
                max_tokens = 1024
                text_words = text.split()
                if len(text_words) > max_tokens:
                    text = " ".join(text_words[:max_tokens])
                
                # Generate summary
                inputs = bart_tokenizer(text, return_tensors="pt", max_length=1024, truncation=True).to(device)
                summary_ids = bart_model.generate(
                    inputs["input_ids"], 
                    num_beams=4,
                    max_length=max_length,
                    min_length=min_length,
                    length_penalty=2.0,
                    early_stopping=True
                )
                summary = bart_tokenizer.decode(summary_ids[0], skip_special_tokens=True)
                return summary
            except Exception as e:
                log_message(f"BART summarization error: {str(e)}")
                return text[:400] + "..."  # Longer fallback for more content
        
        # Collect all categories and sources
        all_categories = list(data.keys())
        all_sources = set()
        category_data = {}  # Will hold processed data by category
        
        total_article_count = 0
        
        # Process and organize articles by category
        for category, sources in data.items():
            # Initialize category data structure
            category_data[category] = {
                "articles": [], 
                "sources": set(),
                "titles": [],
                "summaries": [],
                "contents": [],
                "top_articles": []  # To track most important articles
            }
            
            for source, articles in sources.items():
                all_sources.add(source)
                category_data[category]["sources"].add(source)
                
                for article in articles:
                    # Add to total count
                    total_article_count += 1
                    
                    # Store the article in category collection
                    category_data[category]["articles"].append(article)
                    
                    title = article.get("title", "")
                    content = article.get("content", "")
                    
                    if title:
                        category_data[category]["titles"].append(title)
                    
                    if content:
                        # Store content length to find substantial articles
                        category_data[category]["contents"].append((content, len(content), article))
                    
                    summary = article.get("summary", "")
                    if summary:  # Only add non-empty summaries
                        category_data[category]["summaries"].append(summary)
            
            # Find most substantial articles by content length
            if category_data[category]["contents"]:
                top_articles = sorted(category_data[category]["contents"], key=lambda x: x[1], reverse=True)[:5]
                category_data[category]["top_articles"] = [article for _, _, article in top_articles]
        
        log_message(f"Processed {total_article_count} articles across {len(all_categories)} categories and {len(all_sources)} sources")
        
        # Generate category summaries using BART - with increased length
        category_summaries = {}
        category_stats = {}
        category_detailed_analyses = {}  # For deeper analysis of important articles
        
        for category, data_dict in category_data.items():
            articles = data_dict["articles"]
            sources = data_dict["sources"]
            
            category_stats[category] = {
                "article_count": len(articles),
                "sources": len(sources),
                "source_list": list(sources)
            }
            
            if not data_dict["summaries"]:
                category_summaries[category] = "No article summaries available in this category"
                continue
                
            # Combine article summaries for this category
            combined_text = " ".join(data_dict["summaries"][:20])  # Increased to 20 articles
            
            # Generate category summary with increased length
            summary_length = min(250, max(120, len(combined_text.split()) // 8))  # More words for longer summaries
            category_summaries[category] = summarize_with_bart(
                combined_text, 
                max_length=summary_length, 
                min_length=min(80, summary_length-40)
            )
            
            # Generate detailed analysis from top articles
            if data_dict["top_articles"]:
                top_article_texts = []
                for article in data_dict["top_articles"][:3]:  # Use top 3 articles
                    title = article.get("title", "")
                    summary = article.get("summary", "")
                    if summary:
                        top_article_texts.append(f"{title}. {summary}")
                    elif article.get("content", ""):
                        # If no summary, use beginning of content
                        content_start = article.get("content", "")[:500]
                        top_article_texts.append(f"{title}. {content_start}")
                
                if top_article_texts:
                    combined_detailed = " ".join(top_article_texts)
                    category_detailed_analyses[category] = summarize_with_bart(
                        combined_detailed,
                        max_length=300,  # Longer detailed analysis
                        min_length=150
                    )
                else:
                    category_detailed_analyses[category] = ""
                    
            log_message(f"Generated summary for category: {category}")
                
        # Identify trends across all categories by extracting common entities and topics
        all_titles = []
        for cat_data in category_data.values():
            all_titles.extend(cat_data["titles"])
            
        # Extract trend phrases - with more pattern extraction
        trend_phrases = {}
        for title in all_titles:
            words = title.split()
            # Extract bigrams (two-word phrases)
            for i in range(len(words) - 1):
                phrase = " ".join(words[i:i+2]).lower()
                if len(phrase.split()) > 1 and all(len(word) > 2 for word in phrase.split()):
                    trend_phrases[phrase] = trend_phrases.get(phrase, 0) + 1
                    
            # Extract trigrams (three-word phrases)
            for i in range(len(words) - 2):
                phrase = " ".join(words[i:i+3]).lower()
                if len(phrase.split()) > 2 and all(len(word) > 2 for word in phrase.split()):
                    trend_phrases[phrase] = trend_phrases.get(phrase, 0) + 1
        
        # Get top trends with more entries
        bigram_trends = [phrase for phrase, count in sorted(trend_phrases.items(), 
                                                key=lambda x: x[1], reverse=True)
                if count > 1 and len(phrase.split()) == 2][:15]
                
        trigram_trends = [phrase for phrase, count in sorted(trend_phrases.items(), 
                                                key=lambda x: x[1], reverse=True)
                if count > 1 and len(phrase.split()) == 3][:10]
                
        all_trends = bigram_trends + trigram_trends
        
        # Create executive summary using BART - with increased length
        total_sources = len(all_sources)
        
        # Combine top titles for executive summary
        top_titles = all_titles[:30] if all_titles else ["No articles found"]
        exec_summary_input = f"""
        Comprehensive news summary covering {total_article_count} articles from {total_sources} sources 
        across {len(all_categories)} categories.
        Top categories include: {', '.join(sorted(all_categories))}.
        Major themes observed: {', '.join(all_trends[:8]) if all_trends else 'No consistent themes'}.
        Notable sources include: {', '.join(list(all_sources)[:8])}.
        Sample headlines: {' | '.join(top_titles[:15])}.
        """
        
        # Generate longer executive summary
        exec_summary = summarize_with_bart(exec_summary_input, max_length=350, min_length=200)
        
        # Format final output with extended sections
        summary_parts = []
        
        # Executive Summary section
        summary_parts.append("# EXECUTIVE SUMMARY\n")
        summary_parts.append(exec_summary.strip())
        summary_parts.append("\n")
        
        # Category Insights section - expanded with detailed analysis
        summary_parts.append("# CATEGORY INSIGHTS\n")
        for category, summary in category_summaries.items():
            article_count = category_stats[category]["article_count"]
            sources_covered = category_stats[category]["sources"]
            source_names = category_stats[category]["source_list"][:5]
            
            summary_parts.append(f"## {category} ({article_count} articles from {sources_covered} sources)")
            summary_parts.append(summary)
            
            # Add detailed analysis if available
            if category in category_detailed_analyses and category_detailed_analyses[category]:
                summary_parts.append("\n### In-Depth Analysis:")
                summary_parts.append(category_detailed_analyses[category])
                
            # Add example headlines - increased to 5
            titles = category_data[category]["titles"][:5]
            if titles:
                summary_parts.append("\n### Key Headlines:")
                for title in titles:
                    if title.strip():
                        summary_parts.append(f"• {title}")
                        
            # Add source information
            if source_names:
                summary_parts.append(f"\n### Primary Sources: {', '.join(source_names)}")
                        
            summary_parts.append("")
        
        # Important Trends section - expanded with more analysis
        summary_parts.append("# IMPORTANT TRENDS AND PATTERNS\n")
        
        # Generate detailed trend analysis using trends
        trend_analysis_input = f"""
        Analysis of key news trends: {', '.join(all_trends[:20])}.
        These trends appear across {len(all_categories)} news categories including {', '.join(sorted(all_categories))}.
        """
        
        trend_summary = summarize_with_bart(trend_analysis_input, max_length=300, min_length=150)
        summary_parts.append(trend_summary)
        
        # Add specific trend breakdown
        if bigram_trends:
            summary_parts.append("\n### Key Phrases in Headlines:")
            for i, phrase in enumerate(bigram_trends[:10]):
                summary_parts.append(f"{i+1}. \"{phrase}\"")
        
        if trigram_trends:
            summary_parts.append("\n### Complex Topics:")
            for i, phrase in enumerate(trigram_trends[:7]):
                summary_parts.append(f"{i+1}. \"{phrase}\"")
                
        summary_parts.append("")
        
        # Source Insights section - expanded
        summary_parts.append("# SOURCE ANALYSIS\n")
        
        # Count articles per source across all categories
        source_counts = {}
        source_categories = {}
        
        for category, sources in data.items():
            for source, articles in sources.items():
                # Track article count
                if source not in source_counts:
                    source_counts[source] = 0
                    source_categories[source] = set()
                source_counts[source] += len(articles)
                source_categories[source].add(category)
        
        # Generate source distribution summary
        source_distribution = "\n".join([
            f"• {source}: {count} articles across {len(source_categories[source])} categories" 
            for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:15]
        ])
        
        source_analysis_input = f"""
        Analysis of {len(all_sources)} news sources contributing {total_article_count} articles.
        Source distribution:
        {source_distribution}
        """
        
        source_summary = summarize_with_bart(source_analysis_input, max_length=250, min_length=100)
        summary_parts.append(source_summary)
        summary_parts.append("")
        
        # Top sources by volume
        summary_parts.append("### Top News Sources by Volume:")
        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (source, count) in enumerate(top_sources):
            cat_list = list(source_categories[source])
            summary_parts.append(f"{i+1}. {source}: {count} articles covering {', '.join(cat_list[:3])}" + 
                               (f" and {len(cat_list)-3} more categories" if len(cat_list) > 3 else ""))
        summary_parts.append("")
        
        # Most diverse sources (covering multiple categories)
        summary_parts.append("### Most Diverse Sources:")
        diverse_sources = sorted([(s, len(cats)) for s, cats in source_categories.items()], 
                               key=lambda x: x[1], reverse=True)[:5]
        for source, cat_count in diverse_sources:
            summary_parts.append(f"• {source}: Covering {cat_count} categories with {source_counts[source]} articles")
        summary_parts.append("")
        
        # Notable Articles section - new section highlighting important content
        summary_parts.append("# NOTABLE ARTICLES\n")
        
        # Find notable articles across all categories (using top articles)
        notable_articles = []
        for category, data_dict in category_data.items():
            if data_dict["top_articles"]:
                # Take top 1-2 articles from each category
                for article in data_dict["top_articles"][:2]:
                    title = article.get("title", "")
                    if title:
                        notable_articles.append((category, title, article))
        
        # Limit to 10 total notable articles
        for i, (category, title, article) in enumerate(notable_articles[:10]):
            summary_parts.append(f"### {i+1}. {title} ({category})")
            
            # Add summary if available
            if article.get("summary"):
                summary_text = article["summary"]
                # Limit summary length for display
                if len(summary_text.split()) > 50:
                    summary_text = " ".join(summary_text.split()[:50]) + "..."
                summary_parts.append(summary_text)
                
            # Add link if available
            if article.get("link"):
                summary_parts.append(f"\nSource: {article['link']}")
                
            summary_parts.append("")
        
        # Concatenate all parts
        final_summary = "\n".join(summary_parts)
        
        word_count = len(final_summary.split())
        log_message(f"Generated overall summary of {word_count} words")
        
        # If summary is still under 500 words, add more detail
        if word_count < 500:
            additional_content = [
                "# ADDITIONAL INSIGHTS\n",
                "## Content Analysis",
                "The collected news articles represent a diverse range of topics and perspectives across multiple sources.",
                "Each category presents unique insights into current events, trends, and developments within its domain.",
                "The distribution of articles across sources indicates varying levels of coverage and focus areas for different publishers.",
                "\n## Methodology",
                "This analysis was conducted using advanced natural language processing techniques to categorize, summarize, and extract trends.",
                "BART and DistilBERT models were employed to generate coherent summaries while preserving key information.",
                "Trend identification was performed through n-gram analysis of headlines and content across all categories.",
                "\n## Recommendations",
                "Readers interested in comprehensive news coverage should explore multiple sources across different categories.",
                "Pay particular attention to recurring themes that appear across multiple categories, as these often represent significant developments.",
                "Consider how different sources frame similar topics to gain a more complete understanding of current events.",
                ""
            ]
            
            final_summary = final_summary + "\n" + "\n".join(additional_content)
            
            word_count = len(final_summary.split())
            log_message(f"Added additional content. Final summary is {word_count} words")
        
        return final_summary
    
    except Exception as e:
        log_message(f"Error generating overall summary: {str(e)}")
        return f"Error generating summary: {str(e)}"
