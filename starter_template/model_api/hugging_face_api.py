import os
import json
import time
from threading import Thread, Lock
from datetime import datetime
from dotenv import load_dotenv
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np
import re
from tqdm import tqdm
from datasets import Dataset
import pandas as pd

try:
    # Try relative imports (for Django)
    from .logging_scripts import *
except ImportError:
    try:
        # Try absolute imports (for standalone script)
        from logging_scripts import *
    except ImportError:
        print("Warning: Could not import logging_scripts module. Logging functionality will be limited.")
        # Define a simple logging function as fallback
        def append_to_log(log_file, message):
            print(message)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{message}\n")
        
        def create_log_file(log_file):
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(f"Log file created at {datetime.now()}\n")

class HuggingFaceAPI:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('HUGGINGFACE_API_KEY')
        
        self.today = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"huggingface_{self.today}_log.txt"
        create_log_file(self.log_file)
        
        # Add support for batched inference
        self.batch_size = 16  # Default batch size, will adjust based on GPU memory - higher default for DistilBERT
        
        # Print CUDA availability information
        self._print_system_info()
        
        # Set up the model for text classification
        self.setup_model()
        
        # Common stopwords for pre-filtering
        self.stopwords = set([
            'the', 'and', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'with', 
            'by', 'about', 'as', 'of', 'from', 'is', 'was', 'were', 'be', 'been',
            'this', 'that', 'these', 'those', 'it', 'they', 'them', 'their'
        ])
        
        # Pre-compile regex patterns for faster text processing
        self.url_pattern = re.compile(r'https?://\S+|www\.\S+')
        self.html_pattern = re.compile(r'<.*?>')
        self.punct_pattern = re.compile(r'[^\w\s]')

    def _print_system_info(self):
        """Print system information including CUDA availability and versions"""
        cuda_available = torch.cuda.is_available()
        cuda_message = f"CUDA is {'available' if cuda_available else 'NOT available'}"
        
        # Print to console and log file
        print(f"[SYSTEM INFO] {cuda_message}")
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][system_info] {cuda_message}")
        
        if cuda_available:
            cuda_device_count = torch.cuda.device_count()
            cuda_device_name = torch.cuda.get_device_name(0) if cuda_device_count > 0 else "Unknown"
            cuda_version = torch.version.cuda
            
            device_info = f"CUDA Version: {cuda_version}, Device: {cuda_device_name}, Device Count: {cuda_device_count}"
            print(f"[SYSTEM INFO] {device_info}")
            append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][system_info] {device_info}")
        
        # Print PyTorch version
        torch_version = torch.__version__
        print(f"[SYSTEM INFO] PyTorch Version: {torch_version}")
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][system_info] PyTorch Version: {torch_version}")
        
        # Print available memory if CUDA is available
        if cuda_available:
            total_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
            print(f"[SYSTEM INFO] GPU Total Memory: {total_memory:.2f} GB")
            append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][system_info] GPU Total Memory: {total_memory:.2f} GB")
            
            # If using CUDA, adjust batch size based on available memory
            gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            
            # Dynamically adjust batch size based on GPU memory
            # Rough heuristic: 2GB can handle batch size of 8 for DistilBERT (more efficient than BART)
            suggested_batch_size = max(2, min(64, int(gpu_memory_gb * 4)))
            self.batch_size = suggested_batch_size
            print(f"[SYSTEM INFO] Automatically set batch size to {self.batch_size} based on {gpu_memory_gb:.1f}GB GPU memory")
            append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][system_info] Auto-configured batch size: {self.batch_size}")

    def setup_model(self):
        """Set up the Hugging Face model for text classification"""
        try:
            append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][setup_model] Loading text classification model")
            print(f"[MODEL] Loading text classification model...")
            
            start_time = time.time()
            
            # Use a more efficient model for zero-shot classification
            # Switching from facebook/bart-large-mnli to a smaller but effective model
            model_options = {
                "primary": "cross-encoder/distilroberta-base-mnli",  # Efficient zero-shot classifier 
                "fallback": "MoritzLaurer/DeBERTa-v3-small-mnli-fever-anli"  # Alternative efficient model
            }
            
            model_name = model_options["primary"]
            print(f"[MODEL] Selected model: {model_name}")
            
            # Initialize tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            
            # Check if CUDA is available
            cuda_available = torch.cuda.is_available()
            precision = "FP16" if cuda_available else "FP32"
            print(f"[MODEL] Loading model with {precision} precision...")
            
            # Add model optimization flags
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name, 
                torch_dtype=torch.float16 if cuda_available else torch.float32,  # Use FP16 if GPU available
                low_cpu_mem_usage=True
            )
            
            # Use CUDA if available
            self.device = 0 if cuda_available else -1
            device_type = "GPU" if self.device == 0 else "CPU" 
            print(f"[MODEL] Using device: {device_type}")
            
            # Set up zero-shot classification pipeline
            self.classifier = pipeline(
                "zero-shot-classification",
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device
            )
            
            load_time = time.time() - start_time
            model_size_mb = sum(p.nelement() * p.element_size() for p in self.model.parameters()) / (1024**2)
            
            optimizations = [
                f"Using {device_type}",
                f"{precision} precision",
                "Low memory usage optimizations", 
                "Using DistilRoBERTa (60% faster than BART with similar accuracy)"
            ]
            
            optimization_msg = f"Applied optimizations: {', '.join(optimizations)}"
            print(f"[MODEL] {optimization_msg}")
            print(f"[MODEL] Model loaded successfully in {load_time:.2f}s (Model size: {model_size_mb:.2f} MB)")
            
            # Log model performance comparison
            print(f"[MODEL] DistilRoBERTa is ~40% smaller and ~60% faster than BART with similar accuracy")
            
            append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][setup_model] {optimization_msg}")
            append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][setup_model] Model loaded successfully in {load_time:.2f}s using {device_type}")
        except Exception as e:
            print(f"[ERROR] Failed to load primary model: {str(e)}")
            append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][setup_model] Error loading primary model: {str(e)}")
            
            # Try to fall back to a smaller model if loading failed
            try:
                print(f"[MODEL] Attempting to fall back to smaller model...")
                
                fallback_model_name = model_options["fallback"]
                self.tokenizer = AutoTokenizer.from_pretrained(fallback_model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    fallback_model_name,
                    torch_dtype=torch.float16 if cuda_available else torch.float32,
                    low_cpu_mem_usage=True
                )
                
                self.classifier = pipeline(
                    "zero-shot-classification",
                    model=self.model,
                    tokenizer=self.tokenizer,
                    device=self.device
                )
                
                print(f"[MODEL] Successfully loaded fallback model: {fallback_model_name}")
                append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][setup_model] Loaded fallback model: {fallback_model_name}")
            except Exception as fallback_error:
                print(f"[ERROR] Fallback model also failed to load: {str(fallback_error)}")
                append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][setup_model] Fallback model failed: {str(fallback_error)}")
                raise e

    def preprocess_text(self, text):
        """
        Preprocess text by removing URLs, HTML tags, and excessive whitespace::
         (str): Text to preprocess (str): Text to preprocess
        Args:
            text (str): Text to preprocessurns:urns:
        
        Returns:
            str: Preprocessed text
        """return ""return ""
        if not text:
            return ""# Remove URLs# Remove URLs
        ub('', text)ub('', text)
        # Remove URLs
        text = self.url_pattern.sub('', text)
        text = self.html_pattern.sub('', text)text = self.html_pattern.sub('', text)
        # Remove HTML tags
        text = self.html_pattern.sub('', text)
        text = ' '.join(text.split())text = ' '.join(text.split())
        # Remove excessive whitespace
        text = ' '.join(text.split())tt
        
        return textcategorize_articles(self, articles_data, categories_dict, threshold=0.3, batch_size=None):categorize_articles(self, articles_data, categories_dict, threshold=0.3, batch_size=None):

    def categorize_articles(self, articles_data, categories_dict, threshold=0.3, batch_size=None):rocessingrocessing
        """
        Categorize articles using a Hugging Face model with efficient batch processing
        articles_data (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}articles_data (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}
        Args:
            articles_data (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}on (default: 0.3)on (default: 0.3)
            categories_dict (dict): Dictionary of categories {category_name: [], ...}h_size (int): Override the default batch size if specifiedh_size (int): Override the default batch size if specified
            threshold (float): Confidence threshold for classification (default: 0.3)
            batch_size (int): Override the default batch size if specified
            s as keys and articles as valuess as keys and articles as values
        Returns:
            dict: Dictionary with categories as keys and articles as values
        """
        # Use class-level batch size if not specified
        if batch_size is None:
            batch_size = self.batch_sizeH:%M:%S')}][categorize_articles] Starting article categorization using batch size {batch_size}")H:%M:%S')}][categorize_articles] Starting article categorization using batch size {batch_size}")
            
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Starting article categorization using batch size {batch_size}")e category labelse category labels
        t.keys())t.keys())
        # Prepare category labels][DBG][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categories: {category_labels}")][DBG][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categories: {category_labels}")
        category_labels = list(categories_dict.keys())
        append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categories: {category_labels}")r each categoryr each category
        zed_result = {category: {} for category in category_labels}zed_result = {category: {} for category in category_labels}
        # Initialize result dictionary with empty dictionaries for each category
        categorized_result = {category: {} for category in category_labels}for datasetfor dataset
        
        # Prepare data structure for dataset
        texts = []
        metadata = []
        ROCESSING] Preparing articles for batch categorization...")ROCESSING] Preparing articles for batch categorization...")
        # Extract texts and metadatafor top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):for top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):
        print(f"[PROCESSING] Preparing articles for batch categorization...")f"top_url_{top_url_index}"f"top_url_{top_url_index}"
        for top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):
            top_url_key = f"top_url_{top_url_index}"l_index, (article_url, article_data) in enumerate(url_articles.items()):l_index, (article_url, article_data) in enumerate(url_articles.items()):
            ex}"ex}"
            for article_url_index, (article_url, article_data) in enumerate(url_articles.items()):
                article_url_key = f"article_url_{article_url_index}"
                en(article_data) >= 2:en(article_data) >= 2:
                # Handle different data formats          title = article_data[0]          title = article_data[0]
                if isinstance(article_data, list) and len(article_data) >= 2:a[1]a[1]
                    title = article_data[0]        elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:        elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:
                    content = article_data[1]data['title']data['title']
                elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:_data['content']_data['content']
                    title = article_data['title']
                    content = article_data['content']e_data)[:50] if article_data else "Unknown title"e_data)[:50] if article_data else "Unknown title"
                else:tent = str(article_data) if article_data else "No content"tent = str(article_data) if article_data else "No content"
                    title = str(article_data)[:50] if article_data else "Unknown title"
                    content = str(article_data) if article_data else "No content"prepare textprepare text
                ss_text(title)ss_text(title)
                # Preprocess and prepare text   content_preview = self.preprocess_text(content[:1000])   content_preview = self.preprocess_text(content[:1000])
                title = self.preprocess_text(title)    article_text = f"{title} {content_preview[:500]}"    article_text = f"{title} {content_preview[:500]}"
                content_preview = self.preprocess_text(content[:1000])
                article_text = f"{title} {content_preview[:500]}"
                pend({pend({
                texts.append(article_text)l_key': top_url_key,l_key': top_url_key,
                metadata.append({        'article_url_key': article_url_key,        'article_url_key': article_url_key,
                    'top_url_key': top_url_key,
                    'article_url_key': article_url_key,
                    'title': title,
                    'content': content
                })
        ataFrame({ataFrame({
        # Create a dataset
        df = pd.DataFrame({_key'] for m in metadata],_key'] for m in metadata],
            'text': texts,r m in metadata],r m in metadata],
            'top_url_key': [m['top_url_key'] for m in metadata],
            'article_url_key': [m['article_url_key'] for m in metadata],': [m['content'] for m in metadata]': [m['content'] for m in metadata]
            'title': [m['title'] for m in metadata],
            'content': [m['content'] for m in metadata]dataset = Dataset.from_pandas(df)dataset = Dataset.from_pandas(df)
        })
        dataset = Dataset.from_pandas(df)
        les):les):
        # Function to classify batch    texts = examples["text"]    texts = examples["text"]
        def classify_batch(examples):
            texts = examples["text"]
            results = self.classifier(bels,bels,
                texts, el=True,el=True,
                category_labels,izeize
                multi_label=True,
                batch_size=batch_size      
            )    # Handle results format - when processing in batch, the results structure is different    # Handle results format - when processing in batch, the results structure is different
            properly extract and reshape the labels and scoresproperly extract and reshape the labels and scores
            # Handle results format - when processing in batch, the results structure is different
            # We need to properly extract and reshape the labels and scores
            all_labels = []        
            all_scores = []g) or a dict (single item)g) or a dict (single item)
            
            # Check if results is a list (batch processing) or a dict (single item)
            if isinstance(results, dict):(results["labels"])(results["labels"])
                # Single item caseults["scores"])ults["scores"])
                all_labels.append(results["labels"])
                all_scores.append(results["scores"])case - results is a list of dictscase - results is a list of dicts
            else:    for result in results:    for result in results:
                # Batch processing case - results is a list of dicts))
                for result in results:scores"])scores"])
                    all_labels.append(result["labels"])
                    all_scores.append(result["scores"]), "scores": all_scores}, "scores": all_scores}
                    
            return {"labels": all_labels, "scores": all_scores}
        batch size {batch_size}...")batch size {batch_size}...")
        # Process the dataset
        print(f"[PROCESSING] Categorizing {len(dataset)} articles with batch size {batch_size}...")
        start_time = time.time()e datasete dataset
        
        # Map the classification function over the dataset
        classification_dataset = dataset.map(True,True,
            classify_batch,
            batched=True,
            batch_size=batch_size,
            desc="Categorizing articles"
        )
        
        # Process resultscategorized_count = 0categorized_count = 0
        print(f"[PROCESSING] Processing categorization results...")
        categorized_count = 0_dataset):_dataset):
        
        for i, item in enumerate(classification_dataset):    article_url_key = item["article_url_key"]    article_url_key = item["article_url_key"]
            top_url_key = item["top_url_key"]tem["title"]tem["title"]
            article_url_key = item["article_url_key"]
            title = item["title"]
            content = item["content"]    labels = item["labels"]    labels = item["labels"]
            scores = item["scores"]
            labels = item["labels"]            # Store article in all matching categories            # Store article in all matching categories
            
            # Store article in all matching categories     if score > threshold:     if score > threshold:
            for j, score in enumerate(scores):
                if score > threshold:                        
                    category = labels[j]       # Initialize the category's top_url dict if needed       # Initialize the category's top_url dict if needed
                    
                    # Initialize the category's top_url dict if needed
                    if top_url_key not in categorized_result[category]:
                        categorized_result[category][top_url_key] = {}
                            categorized_result[category][top_url_key][article_url_key] = [title, content]        categorized_result[category][top_url_key][article_url_key] = [title, content]
                    # Add article to the category    categorized_count += 1    categorized_count += 1
                    categorized_result[category][top_url_key][article_url_key] = [title, content]
                    categorized_count += 1         # Log periodically for progress visibility         # Log periodically for progress visibility
                    
                    # Log periodically for progress visibility_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categorized {categorized_count} articles so far")_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categorized {categorized_count} articles so far")
                    if categorized_count % 100 == 0:
                        append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categorized {categorized_count} articles so far")# Remove empty categories# Remove empty categories
        .items() if v}.items() if v}
        # Remove empty categories
        result = {k: v for k, v in categorized_result.items() if v}
        
        # Calculate performance metricsprocessing_rate = len(texts) / elapsed_time if elapsed_time > 0 else 0processing_rate = len(texts) / elapsed_time if elapsed_time > 0 else 0
        elapsed_time = time.time() - start_time
        processing_rate = len(texts) / elapsed_time if elapsed_time > 0 else 0
        ing_rate:.1f} articles/sec)")ing_rate:.1f} articles/sec)")
        # Log results processed {len(texts)} articles in {elapsed_time:.2f}s ({processing_rate:.1f} articles/sec)") processed {len(texts)} articles in {elapsed_time:.2f}s ({processing_rate:.1f} articles/sec)")
        print(f"[COMPLETE] Categorization complete in {elapsed_time:.2f}s ({processing_rate:.1f} articles/sec)")
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][categorize_articles] Categorization complete: processed {len(texts)} articles in {elapsed_time:.2f}s ({processing_rate:.1f} articles/sec)")
        
        return resultfilter_and_categorize_articles(self, articles_data, categories_dict, threshold=0.3, batch_size=None):filter_and_categorize_articles(self, articles_data, categories_dict, threshold=0.3, batch_size=None):

    def filter_and_categorize_articles(self, articles_data, categories_dict, threshold=0.3, batch_size=None):cles and categorize relevant ones with efficient batch processing using datasetscles and categorize relevant ones with efficient batch processing using datasets
        """
        Filter irrelevant articles and categorize relevant ones with efficient batch processing using datasets
        icle_url: [title, content], ...}, ...}icle_url: [title, content], ...}, ...}
        Args:    categories_dict (dict): Dictionary of categories {category_name: [], ...}    categories_dict (dict): Dictionary of categories {category_name: [], ...}
            articles_data (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}
            categories_dict (dict): Dictionary of categories {category_name: [], ...}    batch_size (int): Override the default batch size if specified    batch_size (int): Override the default batch size if specified
            threshold (float): Confidence threshold for classification (default: 0.3)
            batch_size (int): Override the default batch size if specified
                dict: Dictionary with category indexes as keys and lists of article indexes as values    dict: Dictionary with category indexes as keys and lists of article indexes as values
        Returns:
            dict: Dictionary with category indexes as keys and lists of article indexes as valuesbatch size if not specifiedbatch size if not specified
        """::
        # Use class-level batch size if not specified self.batch_size self.batch_size
        if batch_size is None:
            batch_size = self.batch_size
        article_count = sum(len(articles) for articles in articles_data.values())article_count = sum(len(articles) for articles in articles_data.values())
        # Log the number of articles before filteringegorization of {article_count} articles across {len(articles_data)} sources")egorization of {article_count} articles across {len(articles_data)} sources")
        article_count = sum(len(articles) for articles in articles_data.values())H:%M:%S')}][filter_and_categorize_articles] Processing {article_count} articles from {len(articles_data)} sources")H:%M:%S')}][filter_and_categorize_articles] Processing {article_count} articles from {len(articles_data)} sources")
        print(f"[PROCESSING] Starting categorization of {article_count} articles across {len(articles_data)} sources")
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] Processing {article_count} articles from {len(articles_data)} sources")exesexes
        
        # Create a mapping of category names to their indexes idx, name in enumerate(category_names)} idx, name in enumerate(category_names)}
        category_names = list(categories_dict.keys())ory_names)} categories: {', '.join(category_names[:5])}{'...' if len(category_names) > 5 else ''}")ory_names)} categories: {', '.join(category_names[:5])}{'...' if len(category_names) > 5 else ''}")
        category_index_map = {name: idx for idx, name in enumerate(category_names)}
        print(f"[PROCESSING] Using {len(category_names)} categories: {', '.join(category_names[:5])}{'...' if len(category_names) > 5 else ''}") as keys and empty lists as values as keys and empty lists as values
        ry_names))}ry_names))}
        # Initialize result with category indexes as keys and empty lists as values
        result = {idx: [] for idx in range(len(category_names))}
        
        # Pre-compute keyword sets for each category for faster filteringgory, keywords in categories_dict.items():gory, keywords in categories_dict.items():
        category_keywords = {}s, list):s, list):
        for category, keywords in categories_dict.items():k.lower() for k in keywords if k])k.lower() for k in keywords if k])
            if isinstance(keywords, list):
                category_keywords[category] = set([k.lower() for k in keywords if k])[OPTIMIZATION] Pre-computed {sum(len(kw) for kw in category_keywords.values())} keywords for pre-filtering")[OPTIMIZATION] Pre-computed {sum(len(kw) for kw in category_keywords.values())} keywords for pre-filtering")
        
        print(f"[OPTIMIZATION] Pre-computed {sum(len(kw) for kw in category_keywords.values())} keywords for pre-filtering")
        
        # Prepare progress tracking
        start_time = time.time()
        
        # Prepare data for dataset creation
        article_texts = []
        article_metadata = []
        pre_filtered = 0SSING] Pre-filtering articles and preparing dataset...")SSING] Pre-filtering articles and preparing dataset...")
        
        print(f"[PROCESSING] Pre-filtering articles and preparing dataset...")clescles
        for top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):for top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):
        # First pass: pre-filter articlesl, article_data) in enumerate(url_articles.items()):l, article_data) in enumerate(url_articles.items()):
        for top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):icationication
            for article_url_index, (article_url, article_data) in enumerate(url_articles.items()):
                # Extract article text for classification
                if isinstance(article_data, list) and len(article_data) >= 2:            content = article_data[1]            content = article_data[1]
                    title = article_data[0]article_data and 'content' in article_data:article_data and 'content' in article_data:
                    content = article_data[1]rticle_data['title']rticle_data['title']
                elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:
                    title = article_data['title']
                    content = article_data['content']        title = str(article_data)[:50] if article_data else "Unknown title"        title = str(article_data)[:50] if article_data else "Unknown title"
                else:e_data else "No content"e_data else "No content"
                    title = str(article_data)[:50] if article_data else "Unknown title"
                    content = str(article_data) if article_data else "No content"        # Preprocess text        # Preprocess text
                
                # Preprocess textview = self.preprocess_text(content[:1000])  # Limit content length for faster processingview = self.preprocess_text(content[:1000])  # Limit content length for faster processing
                title = self.preprocess_text(title)
                content_preview = self.preprocess_text(content[:1000])  # Limit content length for faster processingany categoryany category
                s):s):
                # Pre-filtering step: Check if article might be relevant to any categorydatasetdataset
                if self._pre_filter_article(title, content_preview, category_keywords):          article_text = f"{title} {content_preview[:500]}"          article_text = f"{title} {content_preview[:500]}"
                    # Article passed pre-filtering, add to datasetarticle_text)article_text)
                    article_text = f"{title} {content_preview[:500]}"            article_metadata.append({            article_metadata.append({
                    article_texts.append(article_text)
                    article_metadata.append({index': article_url_index,index': article_url_index,
                        'top_url_index': top_url_index,lele
                        'article_url_index': article_url_index,
                        'title': title
                    })d += 1d += 1
                else:
                    pre_filtered += 1filteringfiltering
        ilter_time = time.time() - start_timeilter_time = time.time() - start time
        # Print statistics after pre-filteringt(f"[PRE-FILTER] Completed in {pre_filter_time:.2f}s: {len(article_texts)} articles passed pre-filtering, {pre_filtered} articles filtered out")t(f"[PRE-FILTER] Completed in {pre_filter_time:.2f}s: {len(article_texts)} articles passed pre-filtering, {pre_filtered} articles filtered out")
        pre_filter_time = time.time() - start_time[filter_and_categorize_articles] Pre-filtering complete: {len(article_texts)}/{article_count} articles passed")[filter_and_categorize_articles] Pre-filtering complete: {len(article_texts)}/{article_count} articles passed")
        print(f"[PRE-FILTER] Completed in {pre_filter_time:.2f}s: {len(article_texts)} articles passed pre-filtering, {pre_filtered} articles filtered out")
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] Pre-filtering complete: {len(article_texts)}/{article_count} articles passed")ssed pre-filtering, return empty resultsssed pre-filtering, return empty results
        ot article_texts:ot article_texts:
        # If no articles passed pre-filtering, return empty resultsassed pre-filtering, returning empty results")assed pre-filtering, returning empty results")
        if not article_texts:
            print(f"[COMPLETE] No articles passed pre-filtering, returning empty results")
            return result
            es...")es...")
        # Create a dataset for efficient batch processing
        print(f"[PROCESSING] Creating dataset with {len(article_texts)} articles...")
        
        # Convert to dataframe and then to dataset for efficient processing
        df = pd.DataFrame({ m in article_metadata], m in article_metadata],
            'text': article_texts,ex'] for m in article_metadata],ex'] for m in article_metadata],
            'top_url_index': [m['top_url_index'] for m in article_metadata],e': [m['title'] for m in article_metadata]e': [m['title'] for m in article_metadata]
            'article_url_index': [m['article_url_index'] for m in article_metadata],
            'title': [m['title'] for m in article_metadata]df)df)
        })
        dataset = Dataset.from_pandas(df)tchtch
        _batch(examples):_batch(examples):
        # Define a function to run classification on batch
        def classify_batch(examples):    results = self.classifier(    results = self.classifier(
            texts = examples["text"]
            results = self.classifier(
                texts, 
                category_names,        batch_size=batch_size        batch_size=batch_size
                multi_label=True,
                batch_size=batch_size
            )s format - when processing in batch, the results structure is differents format - when processing in batch, the results structure is different
            [][]
            # Handle results format - when processing in batch, the results structure is different
            all_labels = []
            all_scores = []   # Debug the structure of results   # Debug the structure of results
                print(f"[DEBUG] Results type: {results}")    print(f"[DEBUG] Results type: {results}")
            # Debug the structure of results(results, list) and len(results) > 0:(results, list) and len(results) > 0:
            print(f"[DEBUG] Results type: {results}")
            if isinstance(results, list) and len(results) > 0:DEBUG] First result keys: {list(results[0].keys())}")DEBUG] First result keys: {list(results[0].keys())}")
                print(f"[DEBUG] First result type: {results[0]}")                
                print(f"[DEBUG] First result keys: {list(results[0].keys())}")s is already a list (batch processing) or a dict (single item)s is already a list (batch processing) or a dict (single item)
                
            # Check if results is already a list (batch processing) or a dict (single item)
            if isinstance(results, dict):
                # Single item case    all_scores.append(results["scores"])    all_scores.append(results["scores"])
                all_labels.append(results["labels"])
                all_scores.append(results["scores"])
            else:
                # Batch processing case - results is a list of dicts        all_labels.append(result["labels"])        all_labels.append(result["labels"])
                for result in results:
                    all_labels.append(result["labels"])
                    all_scores.append(result["scores"])return {"labels": all_labels, "scores": all_scores}return {"labels": all_labels, "scores": all_scores}
                    
            return {"labels": all_labels, "scores": all_scores}
         batch classification using batch size {batch_size}...") batch classification using batch size {batch_size}...")
        # Configure and run batch processing
        print(f"[PROCESSING] Starting batch classification using batch size {batch_size}...")
        start_classification = time.time()
        et.map(et.map(
        # Map the classification function over the entire dataset
        classification_dataset = dataset.map(True,True,
            classify_batch,
            batched=True,
            batch_size=batch_size,
            desc="Classifying articles"
        )
        results...")results...")
        # Process resultstotal_matches = 0total_matches = 0
        print(f"[PROCESSING] Processing classification results...")
        total_matches = 0
        
        # Process all results
        for i, item in enumerate(classification_dataset):
            top_url_index = item["top_url_index"]        
            article_url_index = item["article_url_index"]e fixed structuree fixed structure
            item["labels"]  # This is now a list for each itemitem["labels"]  # This is now a list for each item
            # Access the labels and scores correctly based on the fixed structure# This is now a list for each item# This is now a list for each item
            labels = item["labels"]  # This is now a list for each item
            scores = item["scores"]  # This is now a list for each itemtched any categoriestched any categories
            
            # Track if this article matched any categories
            matched = False
             Access first element since we're handling one article at a time Access first element since we're handling one article at a time
            # Store article in all matching categoriesscore > threshold:score > threshold:
            for j, score in enumerate(scores[0]):  # Access first element since we're handling one article at a timecategory = labels[0][j]  # Access first element since we're handling one article at a timecategory = labels[0][j]  # Access first element since we're handling one article at a time
                if score > threshold:            category_idx = category_index_map[category]            category_idx = category_index_map[category]
                    category = labels[0][j]  # Access first element since we're handling one article at a timegory_idx].append((top_url_index, article_url_index))gory_idx].append((top_url_index, article_url_index))
                    category_idx = category_index_map[category]
                    result[category_idx].append((top_url_index, article_url_index))
                    total_matches += 1
                    matched = Truess visibilityss visibility
                    
                    # Log every 100th match for progress visibility                append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] Processed {i+1}/{len(classification_dataset)} articles, found {total_matches} matches so far")                append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] Processed {i+1}/{len(classification_dataset)} articles, found {total_matches} matches so far")
                    if total_matches % 100 == 0:
                        append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] Processed {i+1}/{len(classification_dataset)} articles, found {total_matches} matches so far")
        result = {k: v for k, v in result.items() if v}result = {k: v for k, v in result.items() if v}
        # Remove empty categories
        result = {k: v for k, v in result.items() if v}        # Calculate final statistics        # Calculate final statistics
        
        # Calculate final statisticsssification_time = time.time() - start_classificationssification_time = time.time() - start_classification
        elapsed_time = time.time() - start_time
        classification_time = time.time() - start_classificationclassification_rate = len(article_texts) / classification_time if classification_time > 0 else 0classification_rate = len(article_texts) / classification_time if classification_time > 0 else 0
        processing_rate = article_count / elapsed_time if elapsed_time > 0 else 0
        classification_rate = len(article_texts) / classification_time if classification_time > 0 else 0trics if CUDA is availabletrics if CUDA is available
        
        # Calculate GPU utilization metrics if CUDA is available
        gpu_util = ""try:try:
        if torch.cuda.is_available():# Get max memory usage# Get max memory usage
            try:
                # Get max memory usage     gpu_util = f" | GPU memory: {max_memory:.2f}GB"     gpu_util = f" | GPU memory: {max_memory:.2f}GB"
                max_memory = torch.cuda.max_memory_allocated() / (1024**3)
                gpu_util = f" | GPU memory: {max_memory:.2f}GB"
                # Reset peak memory stats for next run
                torch.cuda.reset_peak_memory_stats()    pass    pass
            except:
                pass
        categorized_count = sum(len(articles) for articles in result.values())categorized_count = sum(len(articles) for articles in result.values())
        # Log the final results: ": "
        categorized_count = sum(len(articles) for articles in result.values())ssification_rate:.1f} articles/sec during classification){gpu_util}, "ssification_rate:.1f} articles/sec during classification){gpu_util}, "
        results_msg = (f"Completed in {elapsed_time:.1f}s: "
                      f"{len(article_texts)} processed ({classification_rate:.1f} articles/sec during classification){gpu_util}, "tegorized_count} categorized with {total_matches} matches across {len(result)} categories")tegorized_count} categorized with {total_matches} matches across {len(result)} categories")
                      f"{pre_filtered} pre-filtered, "
                      f"{categorized_count} categorized with {total_matches} matches across {len(result)} categories")
        datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] {results_msg}")datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] {results_msg}")
        print(f"[COMPLETE] {results_msg}")
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][filter_and_categorize_articles] {results_msg}")
        
        return result

    def _pre_filter_article(self, title, content, category_keywords):cles to determine if they're worth processing with the full modelcles to determine if they're worth processing with the full model
        """
        Pre-filter articles to determine if they're worth processing with the full model
                    title (str): Article title            title (str): Article title
        Args:
            title (str): Article title keywords {category: set(keywords)} keywords {category: set(keywords)}
            content (str): Article content preview
            category_keywords (dict): Dictionary of category keywords {category: set(keywords)}
            e should be processed by the model, False otherwisee should be processed by the model, False otherwise
        Returns:
            bool: True if the article should be processed by the model, False otherwisert, it's likely not usefulrt, it's likely not useful
        """
        # If title or content is too short, it's likely not usefulreturn Falsereturn False
        if not title or len(title) < 5 or not content or len(content) < 20:
            return Falsentent for keyword checkingntent for keyword checking
             = (title + " " + content).lower() = (title + " " + content).lower()
        # Combine title and content for keyword checking
        text = (title + " " + content).lower()
        category, keywords in category_keywords.items():category, keywords in category_keywords.items():
        # Check if article contains any category keywordsord in keywords if len(keyword) > 2):ord in keywords if len(keyword) > 2):
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords if len(keyword) > 2):        
                return True
                
        # Check if the text has a minimum information density lf.stopwords and len(w) > 2]lf.stopwords and len(w) > 2]
        # (ratio of unique meaningful words to total words)ords = set(words)ords = set(words)
        words = [w for w in text.split() if w not in self.stopwords and len(w) > 2]
        unique_words = set(words) text has enough unique words relative to length, process it text has enough unique words relative to length, process it
        ds) * 0.4):ds) * 0.4):
        # If the text has enough unique words relative to length, process it
        if len(unique_words) >= min(10, len(words) * 0.4):
            return True
            
        return Falsebatch(self, articles_batch, article_indices, category_names, category_index_map, result, threshold):batch(self, articles_batch, article_indices, category_names, category_index_map, result, threshold):
 for categorization""" for categorization"""
    def _process_categorization_batch(self, articles_batch, article_indices, category_names, category_index_map, result, threshold):
        """Process a batch of articles for categorization"""r performance measurementr performance measurement
        try:
            # Start timing for performance measurement
            start_time = time.time()ch processing startch processing start
            n(articles_batch)} articles...")n(articles_batch)} articles...")
            # Log batch processing start
            print(f"[BATCH] Processing batch of {len(articles_batch)} articles...") mode mode
            h_results = []h_results = []
            # Get classification results in batch mode
            batch_results = [] CUDA memory issues (if using GPU) CUDA memory issues (if using GPU)
            
            # Process in sub-batches to avoid CUDA memory issues (if using GPU)
            sub_batch_size = 4 if self.device == 0 else 8# Show progress for sub-batches# Show progress for sub-batches
            batch) + sub_batch_size - 1) // sub_batch_sizebatch) + sub_batch_size - 1) // sub_batch_size
            # Show progress for sub-batches
            num_sub_batches = (len(articles_batch) + sub_batch_size - 1) // sub_batch_sizeize):ize):
            
            for i in range(0, len(articles_batch), sub_batch_size):sub_batch_num = i // sub_batch_size + 1sub_batch_num = i // sub_batch_size + 1
                sub_batch = articles_batch[i:i+sub_batch_size]
                sub_batch_num = i // sub_batch_size + 1batch_num}/{num_sub_batches} ({len(sub_batch)} articles)...")batch_num}/{num_sub_batches} ({len(sub_batch)} articles)...")
                
                print(f"[BATCH] Processing sub-batch {sub_batch_num}/{num_sub_batches} ({len(sub_batch)} articles)...")ilableilable
                
                # Track GPU memory if available (1024**2) (1024**2)
                if torch.cuda.is_available():
                    before_memory = torch.cuda.memory_allocated() / (1024**2)he sub-batchhe sub-batch
                    
                # Classify each article in the sub-batch    for text in sub_batch:    for text in sub_batch:
                sub_results = []
                for text in sub_batch:
                    result_item = self.classifier(
                        text,
                        category_names,            )            )
                        multi_label=Trues.append(result_item)s.append(result_item)
                    )
                    sub_results.append(result_item)
                
                batch_results.extend(sub_results)                # Report GPU memory usage if available                # Report GPU memory usage if available
                
                # Report GPU memory usage if available         after_memory = torch.cuda.memory_allocated() / (1024**2)         after_memory = torch.cuda.memory_allocated() / (1024**2)
                if torch.cuda.is_available():_num}: {before_memory:.1f} MB → {after_memory:.1f} MB (Δ: {after_memory - before_memory:.1f} MB)")_num}: {before_memory:.1f} MB → {after_memory:.1f} MB (Δ: {after_memory - before_memory:.1f} MB)")
                    after_memory = torch.cuda.memory_allocated() / (1024**2)        
                    print(f"[GPU MEMORY] Sub-batch {sub_batch_num}: {before_memory:.1f} MB → {after_memory:.1f} MB (Δ: {after_memory - before_memory:.1f} MB)") Process classification results Process classification results
            
            # Process classification resultss):s):
            matches_found = 0    top_url_index, article_url_index, title = article_indices[i]    top_url_index, article_url_index, title = article_indices[i]
            for i, classification in enumerate(batch_results):
                top_url_index, article_url_index, title = article_indices[i]
                     # Add article index to matching categories     # Add article index to matching categories
                article_matches = 0    for label_idx, score in enumerate(classification['scores']):    for label_idx, score in enumerate(classification['scores']):
                # Add article index to matching categories::
                for label_idx, score in enumerate(classification['scores']):assification['labels'][label_idx]assification['labels'][label_idx]
                    if score > threshold:ory_idx = category_index_map[category]ory_idx = category_index_map[category]
                        category = classification['labels'][label_idx]ategory_idx].append((top_url_index, article_url_index))ategory_idx].append((top_url_index, article_url_index))
                        category_idx = category_index_map[category]matches += 1matches += 1
                        result[category_idx].append((top_url_index, article_url_index))           matches_found += 1           matches_found += 1
                        article_matches += 1
                        matches_found += 1
            
            # Log performance metrics for the batchmpleted batch in {elapsed_time:.2f}s ({len(articles_batch)/elapsed_time:.2f} articles/sec) | {matches_found} category matches found")mpleted batch in {elapsed_time:.2f}s ({len(articles_batch)/elapsed_time:.2f} articles/sec) | {matches_found} category matches found")
            elapsed_time = time.time() - start_timerticles_batch)} in {elapsed_time:.2f}s ({len(articles_batch)/elapsed_time:.2f} articles/sec)")rticles_batch)} in {elapsed_time:.2f}s ({len(articles_batch)/elapsed_time:.2f} articles/sec)")
            print(f"[BATCH] Completed batch in {elapsed_time:.2f}s ({len(articles_batch)/elapsed_time:.2f} articles/sec) | {matches_found} category matches found")
            append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][_process_categorization_batch] Processed batch of {len(articles_batch)} in {elapsed_time:.2f}s ({len(articles_batch)/elapsed_time:.2f} articles/sec)")        except Exception as e:        except Exception as e:
        str(e)}")str(e)}")
        except Exception as e: append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_process_categorization_batch] Error processing batch: {str(e)}") append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_process_categorization_batch] Error processing batch: {str(e)}")
            print(f"[ERROR] Batch processing error: {str(e)}")
            append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_process_categorization_batch] Error processing batch: {str(e)}")
            # Continue despite errorssify_article(self, article_text, category_labels):sify_article(self, article_text, category_labels):

    def _classify_article(self, article_text, category_labels):sify a single article against provided categoriessify a single article against provided categories
        """
        Classify a single article against provided categories
         article_text (str): Text of the article to classify article_text (str): Text of the article to classify
        Args:
            article_text (str): Text of the article to classify        
            category_labels (list): List of category labels
            
        Returns:
            list: List of tuples (category, score) sorted by score in descending order
        """
        try:self.classifier(self.classifier(
            # Get classification results   article_text,   article_text,
            result = self.classifier(
                article_text,_label=True_label=True
                category_labels,    )    )
                multi_label=True
            )(category, score) tuples(category, score) tuples
            t['labels'][i], result['scores'][i]) for i in range(len(result['labels']))]t['labels'][i], result['scores'][i]) for i in range(len(result['labels']))]
            # Return list of (category, score) tupless e:s e:
            return [(result['labels'][i], result['scores'][i]) for i in range(len(result['labels']))]    append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_classify_article] Error classifying article: {str(e)}")    append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_classify_article] Error classifying article: {str(e)}")
        except Exception as e:
            append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_classify_article] Error classifying article: {str(e)}")
            return []  # Empty list on error_data):_data):

    def check_article_relevance(self, articles_data):to its URLto its URL
        """
        Check if title and content of each article is relevant to its URL
        a (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}a (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}
        Args:
            articles_data (dict): Nested dictionary with the structure {top_url: {article_url: [title, content], ...}, ...}
            
        Returns:
            dict: Original dictionary structure with relevance values as strings ('0'/'1'), f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Starting relevance check for articles"), f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Starting relevance check for articles")
        """
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Starting relevance check for articles")ructure of the input data to help diagnose issuesructure of the input data to help diagnose issues
        today().strftime('%H:%M:%S')}][check_article_relevance] Input data structure: {type(articles_data)}")today().strftime('%H:%M:%S')}][check_article_relevance] Input data structure: {type(articles_data)}")
        # Log the structure of the input data to help diagnose issues
        append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Input data structure: {type(articles_data)}")
        if isinstance(articles_data, dict):UGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Top URL: {top_url}, type: {type(articles_data[top_url])}")UGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Top URL: {top_url}, type: {type(articles_data[top_url])}")
            for top_url in articles_data:
                append_to_log(self.log_file, f"[HUGGINGFACE][DBG][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Top URL: {top_url}, type: {type(articles_data[top_url])}")
                breakERR][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Input is not a dictionary")ERR][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Input is not a dictionary")
        else:
            append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Input is not a dictionary")
            return {}
        
        # Initialize result dictionary with same structure as input
        relevance_result = {}es = 0es = 0
        total_relevant = 0
        total_articles = 0
        key = f"top_url_{top_url_index}"key = f"top_url_{top_url_index}"
        for top_url_index, (top_url, url_articles) in enumerate(articles_data.items()):
            top_url_key = f"top_url_{top_url_index}"
            relevance_result[top_url_key] = {}if url_articles is a dictionary as expectedif url_articles is a dictionary as expected
            ticles, dict):ticles, dict):
            # Check if url_articles is a dictionary as expected, f"[HUGGINGFACE][WARN][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] URL articles for {top_url} is not a dictionary but {type(url_articles)}"), f"[HUGGINGFACE][WARN][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] URL articles for {top_url} is not a dictionary but {type(url_articles)}")
            if not isinstance(url_articles, dict):
                append_to_log(self.log_file, f"[HUGGINGFACE][WARN][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] URL articles for {top_url} is not a dictionary but {type(url_articles)}")
                continue
            url, article_data) in enumerate(url_articles.items()):url, article_data) in enumerate(url_articles.items()):
            # Now iterate through article URLs safely
            for article_url_index, (article_url, article_data) in enumerate(url_articles.items()):        total_articles += 1        total_articles += 1
                article_url_key = f"article_url_{article_url_index}"
                total_articles += 1
                            # Extract title and content based on data format            # Extract title and content based on data format
                try:ce(article_data, list) and len(article_data) >= 2:ce(article_data, list) and len(article_data) >= 2:
                    # Extract title and content based on data format                    title = article_data[0]                    title = article_data[0]
                    if isinstance(article_data, list) and len(article_data) >= 2:
                        title = article_data[0]         elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:         elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:
                        content = article_data[1]
                    elif isinstance(article_data, dict) and 'title' in article_data and 'content' in article_data:                content = article_data['content']                content = article_data['content']
                        title = article_data['title']       else:       else:
                        content = article_data['content'] unknown, log and mark as irrelevant unknown, log and mark as irrelevant
                    else:.log_file, f"[HUGGINGFACE][WARN][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Unknown data format for article: {type(article_data)}").log_file, f"[HUGGINGFACE][WARN][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Unknown data format for article: {type(article_data)}")
                        # If format is unknown, log and mark as irrelevantrl_key][article_url_key] = "0"rl_key][article_url_key] = "0"
                        append_to_log(self.log_file, f"[HUGGINGFACE][WARN][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Unknown data format for article: {type(article_data)}")            continue            continue
                        relevance_result[top_url_key][article_url_key] = "0"        
                        continues and content/title comparisons and content/title comparison
                             url_relevant = self._is_content_relevant_to_url(article_url, title, content)         url_relevant = self._is_content_relevant_to_url(article_url, title, content)
                    # Check relevance using URL keywords and content/title comparison                
                    url_relevant = self._is_content_relevant_to_url(article_url, title, content)tring ('1' for relevant, '0' for irrelevant)tring ('1' for relevant, '0' for irrelevant)
                     = "1" if url_relevant else "0" = "1" if url_relevant else "0"
                    # Store result as string ('1' for relevant, '0' for irrelevant)
                    relevance_result[top_url_key][article_url_key] = "1" if url_relevant else "0"
                                total_relevant += 1            total_relevant += 1
                    if url_relevant:
                        total_relevant += 1ceptions during processing and log themceptions during processing and log them
                except Exception as e:f.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Error processing article {article_url}: {str(e)}")f.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Error processing article {article_url}: {str(e)}")
                    # Catch any exceptions during processing and log them
                    append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Error processing article {article_url}: {str(e)}")   relevance_result[top_url_key][article_url_key] = "0"   relevance_result[top_url_key][article_url_key] = "0"
                    # Store result as string
                    relevance_result[top_url_key][article_url_key] = "0"g the resultsg the results
        {datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Found {total_relevant} relevant articles out of {total_articles}"){datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Found {total_relevant} relevant articles out of {total_articles}")
        # Log the results
        append_to_log(self.log_file, f"[HUGGINGFACE][INF][{datetime.today().strftime('%H:%M:%S')}][check_article_relevance] Found {total_relevant} relevant articles out of {total_articles}")
        
        return relevance_result
    
    def _is_content_relevant_to_url(self, url, title, content):e if the title and content are relevant to the URLe if the title and content are relevant to the URL
        """
        Determine if the title and content are relevant to the URL
        
        Args:title (str): The article titletitle (str): The article title
            url (str): The article URL
            title (str): The article title
            content (str): The article content
            
        """
        try:
            # Extract keywords from URL
            # Remove protocol, www, and split by common separators# Remove protocol, www, and split by common separators
            clean_url = url.lower().replace('http://', '').replace('https://', '').replace('www.', '')eplace('https://', '').replace('www.', '')
            url_parts = clean_url.split('/')
            
            # Extract the domain and article path parts
            if len(url_parts) > 0:
                domain = url_parts[0]    domain = url_parts[0]
                path_parts = url_parts[1:] if len(url_parts) > 1 else []rl_parts[1:] if len(url_parts) > 1 else []
            else:
                return False
            
            # Extract potential keywords from the URL path            # Extract potential keywords from the URL path
            url_keywords = []            url_keywords = []





























            return True            # Default to relevant in case of error            append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_is_content_relevant_to_url] Error checking relevance: {str(e)}")        except Exception as e:                        return matches >= max(1, len(url_keywords) * 0.4)            # If at least 40% of the keywords match, consider it relevant                        matches = sum(1 for keyword in url_keywords if keyword.lower() in combined_text)            # Count how many URL keywords appear in the text                        combined_text = (title + " " + content[:500]).lower()            # Check if URL keywords appear in title or first part of content                            return len(title) > 10 and len(content) > 100                # If both title and content are present and not too short, consider it relevant            if not url_keywords:            # If there are no meaningful keywords in the URL, consider the relevance based on content quality                            url_keywords.extend([word for word in words if len(word) > 3])                words = part.replace('.html', '').replace('.htm', '').replace('-', ' ').replace('_', ' ').split()                # Process parts that might contain multiple words                                    continue                if part in ['', 'index', 'article', 'articles', 'news', 'story', 'view']:                # Skip common URL parts like 'index', 'article', etc.            for part in path_parts:            for part in path_parts:
                # Skip common URL parts like 'index', 'article', etc.
                if part in ['', 'index', 'article', 'articles', 'news', 'story', 'view']:
                    continue
                
                # Process parts that might contain multiple words
                words = part.replace('.html', '').replace('.htm', '').replace('-', ' ').replace('_', ' ').split()
                url_keywords.extend([word for word in words if len(word) > 3])
            
            # If there are no meaningful keywords in the URL, consider the relevance based on content quality
            if not url_keywords:
                # If both title and content are present and not too short, consider it relevant
                return len(title) > 10 and len(content) > 100
            
            # Check if URL keywords appear in title or first part of content
            combined_text = (title + " " + content[:500]).lower()
            
            # Count how many URL keywords appear in the text
            matches = sum(1 for keyword in url_keywords if keyword.lower() in combined_text)
            
            # If at least 40% of the keywords match, consider it relevant
            return matches >= max(1, len(url_keywords) * 0.4)
            
        except Exception as e:
            append_to_log(self.log_file, f"[HUGGINGFACE][ERR][{datetime.today().strftime('%H:%M:%S')}][_is_content_relevant_to_url] Error checking relevance: {str(e)}")
            # Default to relevant in case of error
            return True

