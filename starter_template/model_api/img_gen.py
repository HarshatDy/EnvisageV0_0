from openai import OpenAI
import os
import base64
from dotenv import load_dotenv
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image
import logging

try:
    from .logging_scripts import create_log_file, append_to_log
except ImportError:
    from logging_scripts import create_log_file, append_to_log

class ImageGenerator:
    def __init__(self):
        """
        Initialize the ImageGenerator with OpenAI client
        """
        load_dotenv()
        self.client = OpenAI(
            organization=os.getenv('ORG'),
            project=os.getenv('PROJ'),
            api_key=os.getenv('OPENAI_API_KEY')
        )
        self.today = datetime.today().strftime('%Y_%m_%d_%H_%M_%S')
        self.log_file = f"img_gen_{self.today}_log.txt"
        create_log_file(self.log_file)
        self.image_dir = self._ensure_image_directory()

    def _ensure_image_directory(self):
        """
        Ensure the directory for saving images exists
        """
        img_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'img', 'generated')
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)
            append_to_log(self.log_file, f"[IMG_GEN][INF][{datetime.now().strftime('%H:%M:%S')}][_ensure_image_directory] Created directory: {img_dir}")
        return img_dir

    def generate_image(self, prompt, size="1024x1024", quality="standard", n=1):
        """
        Generate an image based on the provided text prompt
        
        Args:
            prompt (str): The text description for the image to generate
            size (str): Size of the image (256x256, 512x512, or 1024x1024)
            quality (str): Quality of the image (standard or hd)
            n (int): Number of images to generate
            
        Returns:
            str: Path to the saved image file or URL of the generated image
        """
        append_to_log(self.log_file, f"[IMG_GEN][DBG][{datetime.now().strftime('%H:%M:%S')}][generate_image] Generating image with prompt: {prompt}")
        
        try:
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=size,
                quality=quality,
                n=n
            )
            
            image_url = response.data[0].url
            append_to_log(self.log_file, f"[IMG_GEN][INF][{datetime.now().strftime('%H:%M:%S')}][generate_image] Image generated successfully: {image_url}")
            
            # Save the image to disk
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            image_path = self._save_image_from_url(image_url, f"img_{timestamp}.png")
            
            return {
                'url': image_url,
                'local_path': image_path,
                'relative_path': os.path.relpath(image_path, os.path.join(os.path.dirname(__file__), '..', 'static'))
            }
            
        except Exception as e:
            append_to_log(self.log_file, f"[IMG_GEN][ERR][{datetime.now().strftime('%H:%M:%S')}][generate_image] Error generating image: {str(e)}")
            return {'error': str(e)}

    def _save_image_from_url(self, url, filename):
        """
        Download and save an image from a URL
        
        Args:
            url (str): URL of the image
            filename (str): Filename to save as
            
        Returns:
            str: Path to the saved image file
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            img = Image.open(BytesIO(response.content))
            save_path = os.path.join(self.image_dir, filename)
            
            img.save(save_path)
            append_to_log(self.log_file, f"[IMG_GEN][INF][{datetime.now().strftime('%H:%M:%S')}][_save_image_from_url] Image saved to {save_path}")
            
            return save_path
            
        except Exception as e:
            append_to_log(self.log_file, f"[IMG_GEN][ERR][{datetime.now().strftime('%H:%M:%S')}][_save_image_from_url] Error saving image: {str(e)}")
            return None

    def generate_variation(self, image_path, n=1, size="1024x1024"):
        """
        Generate variations of the provided image
        
        Args:
            image_path (str): Path to the source image
            n (int): Number of variations to generate
            size (str): Size of the output images
            
        Returns:
            list: Paths to the saved variation images
        """
        append_to_log(self.log_file, f"[IMG_GEN][DBG][{datetime.now().strftime('%H:%M:%S')}][generate_variation] Generating variation of image: {image_path}")
        
        try:
            with open(image_path, "rb") as image_file:
                response = self.client.images.create_variation(
                    image=image_file,
                    n=n,
                    size=size
                )
                
            variation_paths = []
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for i, image_data in enumerate(response.data):
                image_url = image_data.url
                variation_path = self._save_image_from_url(image_url, f"var_{timestamp}_{i}.png")
                variation_paths.append(variation_path)
                
            append_to_log(self.log_file, f"[IMG_GEN][INF][{datetime.now().strftime('%H:%M:%S')}][generate_variation] Generated {len(variation_paths)} variations")
            return variation_paths
            
        except Exception as e:
            append_to_log(self.log_file, f"[IMG_GEN][ERR][{datetime.now().strftime('%H:%M:%S')}][generate_variation] Error generating variations: {str(e)}")
            return []

    def enhance_prompt(self, basic_prompt):
        """
        Enhance a basic prompt to generate better images
        
        Args:
            basic_prompt (str): The basic user prompt
            
        Returns:
            str: Enhanced prompt for better image generation
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a prompt engineering expert. Your job is to convert a simple image description into a detailed, creative prompt for DALL-E to generate high-quality images. Include specific details about style, lighting, composition, mood, and other relevant aspects. Don't change the main subject."},
                    {"role": "user", "content": f"Enhance this basic image description for DALL-E: {basic_prompt}"}
                ]
            )
            
            enhanced_prompt = response.choices[0].message.content
            append_to_log(self.log_file, f"[IMG_GEN][INF][{datetime.now().strftime('%H:%M:%S')}][enhance_prompt] Enhanced prompt: {enhanced_prompt}")
            return enhanced_prompt
            
        except Exception as e:
            append_to_log(self.log_file, f"[IMG_GEN][ERR][{datetime.now().strftime('%H:%M:%S')}][enhance_prompt] Error enhancing prompt: {str(e)}")
            return basic_prompt  # Return original prompt if enhancement fails

# Example usage
if __name__ == "__main__":
    generator = ImageGenerator()
    
    # Basic usage
    # result = generator.generate_image("A serene landscape with mountains and a lake at sunset")
    
    # Enhanced prompt usage
    basic_prompt = "News about climate change impact on agriculture"
    enhanced_prompt = generator.enhance_prompt(basic_prompt)
    result = generator.generate_image(enhanced_prompt)
    
    print(f"Image generated: {result}")
